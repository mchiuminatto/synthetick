# ADR-0003: Generate ticks in blocks sized by TICKS_PER_OBJECT, with one random stream per block

- **Status:** Accepted
- **Date:** 2026-11-10
- **Deciders:** Marcello Chiuminatto
- **Consulted:** n/a
- **Informed:** n/a
- **Tags:** worker, generation, memory, determinism

## Context

The worker generates the whole tick range in memory, then writes it to MinIO:

```text
TODAY
  generate ALL ticks  ───────────────►  write objects
  (memory = whole range)                (part-1, part-2, ...)
```

A large but legitimate range fails with an out-of-memory error (`np.repeat` for 4.5 billion ticks tried to allocate 33.5 GiB). Jira: SYN-61.

The fix looks simple: generate a piece, write it, repeat.

```text
WANTED
  generate block ─► write ─► generate block ─► write ─► ...
  (memory = about one object)
```

Two things make it harder than it looks.

**1. The same range must always give the same ticks (SYN-45).**

The generator uses a random number generator (RNG): a function that gives the same "random" numbers for the same seed. Today there is one RNG, used in phases (all counts first, then all positions, then all price steps). Each number depends on how many numbers were taken before it. If the pieces are cut differently, the numbers are taken in a different order and the ticks change.

```text
ONE shared RNG, pieces of 2 units      pieces of 4 units
  numbers are taken in one order  vs   numbers are taken in another order
                          = DIFFERENT TICKS for the same seed
```

**2. Objects must have exactly `ticks_per_object` ticks** (the last one may have fewer). The row stores `ticks_per_object`, and the download relies on it. But a piece of time units produces a variable number of ticks, because each unit has a random tick count. So one block is not one object.

Today the worker reads `TICKS_PER_OBJECT` from the environment each time it processes a range. If the block size came from a setting that can change, a restart with another value would cut the range differently and give other ticks.

## Decision Drivers

- Memory depends on the size of one object, not on the size of the range (the SYN-61 wording).
- Same seed and spec always give the same dataset, so a restart or a repeated generation gives the same ticks (SYN-45).
- The dataset is defined by the seed and the spec alone, not by a deployment setting.
- Objects keep the documented size (`ticks_per_object`).
- Smallest change: the random walk and the tick timing model do not change, and no new dependency.

## Considered Options

1. **`TICKS_PER_OBJECT` is a constant in code; the block size is derived from it and from `max_ticks`; one RNG per block** (plain numpy)
2. **A separate fixed `BLOCK_UNITS` constant** in code, unrelated to the object size
3. **Block size driven by `TICKS_PER_OBJECT` read from the environment** (or frozen on the row at request time)
4. **One RNG per time unit**, derived from `(seed, unit index)`
5. **Dask** with chunks of a fixed size
6. **One shared RNG, keep its state between pieces of any size**

## Decision

We will make **`TICKS_PER_OBJECT` a constant in code** (the environment variable goes away) and derive the block from it (option 1):

```text
units_per_block = max(1, TICKS_PER_OBJECT // max_ticks)
```

`max_ticks` is the largest number of ticks one time unit can have, and it is part of the request spec. So the block size depends only on a code constant and on the spec. Each block has its own RNG, seeded from `(seed, block index)`.

### The terms

- **Time unit:** the range is cut into slices of `time_unit_seconds` each (for example 1 second). Each time unit gets a random number of ticks, between `min_ticks` and `max_ticks`, with a mean of `mean_ticks`.
- **`TICKS_PER_OBJECT`:** counts **ticks**. It is the size of one output file in MinIO: each `part-<n>.parquet` holds exactly this many ticks, except the last one, which holds the remainder. It is a constant in code.
- **`units_per_block`:** counts **time units**. It is how many time units the generator makes in one step (one block). Because a unit has at most `max_ticks` ticks, `TICKS_PER_OBJECT // max_ticks` units can never produce more than about one object's worth of ticks.

In one line: `TICKS_PER_OBJECT` is the size of the output file (in ticks), and `units_per_block` is the size of the generation step (in time units). One is derived from the other so that memory stays about one object.

### Example

| | Value |
|---|---|
| `TICKS_PER_OBJECT` | 100,000 |
| `max_ticks` (per time unit, from the request) | 50 |
| `units_per_block` | `100,000 // 50` = 2,000 time units |

```text
block   = 2,000 time units  →  at most 2,000 × 50 = 100,000 ticks
                               (usually fewer: about mean_ticks × 2,000)
object  = exactly 100,000 ticks

block 0 (~20,000 ticks) ─┐
block 1 (~20,000 ticks) ─┼─► buffer ─► 100,000 ticks ─► part-000001.parquet
block 2 (~20,000 ticks) ─┤                              (the rest stays in the buffer)
block 3 ...             ─┘
```

A block does not produce exactly one object, because the tick count of each unit is random. That is why the writer buffers the blocks and cuts them into objects of exactly `TICKS_PER_OBJECT`.

```text
units_per_block = max(1, TICKS_PER_OBJECT // max_ticks)      (a block is at most about one object)

seed ──► block 0 : RNG(seed, 0) ──► counts, positions, price steps, spreads for units 0..B-1
    ├──► block 1 : RNG(seed, 1) ──► ... for units B..2B-1
    ├──► block 2 : RNG(seed, 2) ──► ...
    └──► ...                        (the last block may be shorter)

Same seed and spec, any worker, any restart  ──►  same blocks  ──►  same ticks
```

Inside a block the generation works as it does today (counts, positions, steps, spreads, with the redraw of out-of-limit counts). The block is the unit of randomness, so none of that changes.

The generator gives one block at a time. The writer cuts the stream of blocks into objects of exactly `TICKS_PER_OBJECT` ticks:

```text
generator (blocks)                          writer
  block 0 (3 000 ticks) ─┐
  block 1 (4 100 ticks) ─┼─► buffer ─► enough? ──► part-000001.parquet  (TICKS_PER_OBJECT ticks)
  block 2 (3 500 ticks) ─┘           └─ keep the rest in the buffer
  block 3 ...           ──────────►  ...  ──► part-000002.parquet
  (end)                 ──────────►  flush the remainder ──► part-00000N.parquet
```

How the rest works:

- **Price walk:** the last bid of a block is carried into the next block, so the price continues without a jump. The `cumsum` of a block starts from the carried bid.
- **Counts:** `records_produced` and `objects_produced` are counted while writing, not from the length of one big array.
- **Memory:** about one block plus one object, so it follows the object size.
- **Stored value:** the row keeps storing `ticks_per_object`, as now. A range that is already `PROCESSED` keeps downloading correctly even if the constant changes later, because the download reads the value from the row.
- **`write_ticks`** keeps its `ticks_per_object` parameter. Only the worker passes the constant.

Scope: this covers how the worker generates and writes ticks. It does not change the tick model (arithmetic random walk, negative-binomial timing), the Parquet schema, the claim and lock rules of ADR-0002, or the request size limit (raised in a separate change after this one).

**Rule:** `TICKS_PER_OBJECT` and the formula above are part of the definition of the dataset. Changing either one changes the ticks for new ranges, so they are changed only on purpose, with a new ADR or an update to this one.

## Options Analysis

### Option 1 — Code constant `TICKS_PER_OBJECT`, block derived from it, one RNG per block (chosen)
- ✅ Pro: the dataset depends only on the seed and the spec. The constant is the same for every call and every consumer.
- ✅ Pro: one knob, and memory follows the object size, as the story asks.
- ✅ Pro: few RNGs to create (one per block), so it is fast.
- ✅ Pro: plain numpy, no new dependency, and numpy documents the `SeedSequence` streams as stable.
- ❌ Con: the constant is frozen in practice: changing it changes the datasets of new ranges.
- ❌ Con: the object size is no longer a deployment setting.
- ❌ Con: if `max_ticks` is bigger than the constant, the block is 1 unit and memory is bounded by `max_ticks`; the request limit has to keep it reasonable.
- ❌ Con: the dataset for a given seed differs from today's. Nothing stored depends on it yet.

### Option 2 — A separate fixed `BLOCK_UNITS` constant
- ✅ Pro: the same determinism as option 1.
- ❌ Con: a second constant to choose and keep, and memory is not tied to the object size (it depends on `BLOCK_UNITS × max_ticks`).

### Option 3 — Block size driven by `TICKS_PER_OBJECT` from the environment
- ✅ Pro: memory is tunable per deployment.
- ❌ Con: the dataset would depend on the setting. A worker restart with another value gives other ticks for the same range.
- ❌ Con: freezing the value on the row at request time fixes the restart, but then the seed and spec alone no longer define the dataset (a client-supplied seed in SYN-45 would give different ticks under different settings), and the request flow has to change.

### Option 4 — One RNG per time unit
- ✅ Pro: any block size gives the same ticks, by construction; nothing to freeze.
- ❌ Con: creating an RNG per unit has a cost (roughly tens of microseconds, not measured yet).
- ❌ Con: it protects against a risk we avoid anyway with a constant.

### Option 5 — Dask with chunks of a fixed size
- ✅ Pro: bounded memory, and it can use several cores.
- ✅ Pro: deterministic for a fixed chunk layout (checked: the same chunks gave identical output).
- ❌ Con: a different chunk size gives different numbers (checked: chunks of 100, 250 and 1000 with seed 42 all differ). The result is tied to Dask's way of splitting the seed, so the Dask version would have to be pinned.
- ❌ Con: heavy new dependency (scheduler, task graph) in a worker designed as a single function (ADR-0002).
- ❌ Con: the tick count per unit is random, so chunk lengths are unknown, and the exact cut into objects is awkward.

### Option 6 — One shared RNG, keep its state between pieces
- ✅ Pro: one RNG, the cheapest to run.
- ❌ Con: the numbers depend on the order of draws, so pieces of another size give other ticks.
- ❌ Con: the redraw loop depends on the piece shape.

## Consequences

### Positive
- Memory no longer grows with the size of the range.
- Same seed and spec, same dataset, also after a worker restart (ADR-0002 relies on this).
- One constant to reason about, and no environment setting that can change the data.
- The "keep generation in memory" mitigation in ADR-0002 is no longer needed for the data.
- No new dependency.

### Negative / Trade-offs accepted
- The datasets for existing seeds change once. SYN-45 is built on the new scheme.
- `TICKS_PER_OBJECT` and the formula are frozen in practice.
- `generate_ticks` and `write_ticks` change signature (stream instead of one `Ticks`), so their callers and tests are adapted.
- A little more code: a buffer in the writer that cuts blocks into exact objects.

### Risks and Mitigations
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Someone changes the constant or the formula (or makes it configurable) and datasets change silently | Med | High | Constant in code with a comment; a "golden" test with a fixed seed and expected first ticks fails if the constant or the scheme changes |
| A block is too big for the worker memory (large `max_ticks`) | Med | Med | The request limit bounds `max_ticks`; choose the constant with the largest allowed `max_ticks` in mind |
| Floating point differences when the price walk is split in blocks | Low | Med | Start each block's `cumsum` from the carried bid; test the result against a single-block run |
| A worker crash mid-write leaves some objects in MinIO | Med | Low | Same as ADR-0002: a restart rewrites the same names with the same content |

## Implementation Notes

- Test first (TDD): the same seed and spec give the same ticks across repeated runs.
- Test: a fixed seed gives known first ticks (a "golden" test) that fails if the scheme or the constant changes.
- Test: the price is continuous across block boundaries, and a range shorter than one block works.
- Test: objects have exactly `ticks_per_object` rows, and the last one has the remainder.
- Existing generator, storage and worker tests stay green (adapted to the new signatures, not removed).
- Replace `os.environ.get("TICKS_PER_OBJECT", ...)` in the worker with the code constant; keep writing `ticks_per_object` to the row.
- Manual check: peak memory of the worker stays flat as the range grows.
- Follow-up: raise the request size limit (the related oversized request bug) once this is done.
- Rollback: revert the change; nothing in the database or the storage layout changes.

## Validation

- Test: same seed and spec, same ticks, on repeated runs.
- Test: objects have exactly `ticks_per_object` rows, and the last one has the remainder.
- Manual: generate a range far larger than before and watch the worker memory stay about constant.

**Revisit when:** generation speed becomes the bottleneck (then Dask or several workers per range is worth a new look), the tick model changes (SYN-45 and later), or the object size has to change.

## References

- Jira SYN-61, SYN-45
- [ADR-0002](./0002-worker-claims-and-holds-the-row-until-processed.md), worker claim and lock
- [synthetic-price-generation.md](../design/synthetic-price-generation.md), random walk reference
- [domain-analysis.md](../design/domain-analysis.md)
