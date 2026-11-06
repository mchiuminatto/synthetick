# ADR-0002: The worker holds the row lock from claim to PROCESSED, without a visible STARTED state

- **Status:** Proposed
- **Date:** 2026-11-06
- **Deciders:** Marcello Chiuminatto
- **Consulted:** n/a
- **Informed:** n/a
- **Tags:** worker, queue, lifecycle, postgresql

## Context

The API records a request as `REQUESTED` (with the `TickRangeRequested` event) and a separate worker takes it from PostgreSQL with `FOR UPDATE SKIP LOCKED`. There is no message broker (see [tech-stack.md](../design/tech-stack.md), TS-5).

The domain analysis defines the lifecycle `REQUESTED → STARTED → PROCESSED`, or `STARTED → FAILED`, with the events `TickRangeStarted`, `TickRangeProcessed` and `TickRangeFailed` ([domain-analysis.md](../design/domain-analysis.md)). Two things are different in SYN-41:

- The story limits event recording to the request event. Lifecycle and download events are SYN-55.
- The story leaves the stuck-job requeue and the retry limit out of scope: "the restart policy comes with the worker; the recovery rule is refined later".

The worker has to decide how it claims a range, and what happens when it dies half way. Writing to MinIO and to the database cannot be one transaction, so the order matters: objects first, then the database update (see "Aggregate data model" in the domain analysis).

## Decision Drivers

- No stuck ranges: a worker that dies must not leave a range that nobody takes again, because the recovery rule is not designed yet.
- No broker and no extra queue table; the queue is the `tick_range` table.
- The smallest worker that satisfies SYN-41, without events beyond the request.
- The lifecycle in the domain analysis must remain reachable later without a rewrite.

## Considered Options

1. **Claim in a short transaction and mark `STARTED`**, generate outside the transaction, then mark `PROCESSED`
2. **Claim and hold the row lock until `PROCESSED`**, in one transaction, without a visible `STARTED`

## Decision

We will **claim a `REQUESTED` range with `FOR UPDATE SKIP LOCKED` and keep that transaction open until the range is marked `PROCESSED`**, because a worker that dies releases the lock and the row is still `REQUESTED`, so the recovery rule is not needed yet. The worker writes the Parquet objects while it holds the lock, then updates the row to `PROCESSED` and records the result in the same transaction.

Scope: this covers how the worker claims and completes a range in SYN-41. In this story the worker writes no `TickRangeStarted` or `TickRangeProcessed` event, and the status `STARTED` is not used. It does not cover the `FAILED` path, the retry limit, a stuck-job rule, or the behaviour with several workers beyond what `SKIP LOCKED` gives.

## Options Analysis

### Option 1 — Short claim transaction with `STARTED`
- ✅ Pro: follows the lifecycle of the domain analysis; `STARTED` is visible to the status endpoint.
- ✅ Pro: no long-lived database transaction.
- ❌ Con: a worker that dies leaves the range in `STARTED` for ever; it needs the stuck-job requeue and the retry limit, which the story leaves out.
- ❌ Con: `STARTED` should come with its event (`TickRangeStarted`), which is SYN-55.

### Option 2 — Hold the lock until `PROCESSED`
- ✅ Pro: crash-safe by construction: no commit, no state change, and the range goes back to the queue.
- ✅ Pro: one transaction to reason about; no event is needed.
- ✅ Pro: the other workers skip the row (`SKIP LOCKED`), so a range is not generated twice.
- ❌ Con: one database connection and one transaction stay open for the whole generation.
- ❌ Con: while a range is being generated the status is still `REQUESTED`, so the data endpoint answers 409 with `REQUESTED`.
- ❌ Con: objects of a crashed run stay in MinIO as orphans; the retention TTL removes them (already accepted in the domain analysis).

## Consequences

### Positive
- No stuck-job handling is needed for SYN-41.
- The worker is a single function (`process_next_tick_range()`), easy to call from a test.

### Negative / Trade-offs accepted
- The `STARTED` status exists in the schema but nothing sets it for now.
- A long transaction per worker. With a few long jobs and no broker (the load assumed in TS-5) this is acceptable.
- A restarted worker repeats the generation from the start, and writes the same objects again with the same names. The seed is stored, so the result is the same.

### Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Very long generations hold a connection and may hit a database or proxy idle timeout | Low | Med | Keep generation in memory and fast; revisit with Option 1 if jobs grow |
| A range that always crashes the worker is retried for ever | Med | Low | Container `on-failure` policy; the retry limit is refined in a later story |
| Users expect `STARTED` in the status | Low | Low | SYN-42 can report `REQUESTED` while processing; adopt Option 1 when SYN-55 adds the events |

## Implementation Notes

- The claim query selects the oldest `REQUESTED` range ordered by `created_at`, with `FOR UPDATE SKIP LOCKED`, `LIMIT 1`.
- Objects are written before the update, so a `PROCESSED` range always has its data.
- Superseding: when stuck-job recovery and SYN-55 are designed, a new ADR can move to Option 1 and mark this one as superseded.

## Validation

- Test: `process_next_marks_requested_range_processed_and_records_result` (SYN-41, test 2c).
- Manual: stop the worker during a generation and check the range is `REQUESTED` after restart.

**Revisit when:** SYN-55 (lifecycle events) is started, the stuck-job rule is defined, or a generation takes longer than the connection idle timeouts.

## References

- [domain-analysis.md](../design/domain-analysis.md), lifecycle, "Aggregate data model"
- [tech-stack.md](../design/tech-stack.md), TS-5 (job queue)
- Jira SYN-41 (out of scope: stuck-job requeue), SYN-55
