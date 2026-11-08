"""Create tick_range and domain_event.

The instrument table, the foreign key to it and tick_range.price_decimals are
left out on purpose: they arrive with the instrument check (SYN-48).
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE tick_range_status AS ENUM
            ('REQUESTED', 'STARTED', 'PROCESSED', 'EXPIRED', 'FAILED')
        """
    )
    op.execute(
        """
        CREATE TABLE tick_range (
            tick_range_id      UUID               NOT NULL,
            version            INTEGER            NOT NULL DEFAULT 1,
            status             tick_range_status  NOT NULL DEFAULT 'REQUESTED',

            instrument         VARCHAR(20)        NOT NULL,
            initial_bid        NUMERIC(18,8)      NOT NULL,
            min_price          NUMERIC(18,8)      NOT NULL,
            max_price          NUMERIC(18,8)      NOT NULL,
            date_from          TIMESTAMPTZ        NOT NULL,
            date_to            TIMESTAMPTZ        NOT NULL,
            trend_drift        DOUBLE PRECISION   NOT NULL,
            volatility_sigma   DOUBLE PRECISION   NOT NULL,
            spread_mean        DOUBLE PRECISION   NOT NULL,
            spread_stdev       DOUBLE PRECISION   NOT NULL,
            time_unit_seconds  DOUBLE PRECISION   NOT NULL,
            mean_ticks         DOUBLE PRECISION   NOT NULL,
            dispersion         DOUBLE PRECISION   NOT NULL,
            min_ticks          INTEGER            NOT NULL,
            max_ticks          INTEGER            NOT NULL,
            seed               BIGINT             NOT NULL,

            records_produced   BIGINT             NULL,
            expires_at         TIMESTAMPTZ        NULL,
            failure_reason     TEXT               NULL,
            storage_bucket     VARCHAR(63)        NULL,
            storage_prefix     VARCHAR(1024)      NULL,
            objects_produced   INTEGER            NULL,
            ticks_per_object   INTEGER            NULL,

            created_at         TIMESTAMPTZ        NOT NULL DEFAULT now(),
            updated_at         TIMESTAMPTZ        NOT NULL DEFAULT now(),

            CONSTRAINT pk_tick_range PRIMARY KEY (tick_range_id),
            CONSTRAINT ck_tick_range_version      CHECK (version > 0),
            CONSTRAINT ck_tick_range_price_range  CHECK (min_price < max_price),
            CONSTRAINT ck_tick_range_min_price    CHECK (min_price > 0),
            CONSTRAINT ck_tick_range_initial_bid  CHECK (initial_bid BETWEEN min_price AND max_price),
            CONSTRAINT ck_tick_range_time_range   CHECK (date_from < date_to),
            CONSTRAINT ck_tick_range_volatility   CHECK (volatility_sigma >= 0),
            CONSTRAINT ck_tick_range_spread       CHECK (spread_mean >= 0 AND spread_stdev >= 0),
            CONSTRAINT ck_tick_range_tick_timing  CHECK (
                time_unit_seconds > 0 AND mean_ticks > 0 AND dispersion > 0
                AND min_ticks >= 0 AND max_ticks >= 1 AND min_ticks <= max_ticks
                AND mean_ticks BETWEEN min_ticks AND max_ticks
            ),
            CONSTRAINT ck_tick_range_ticks_per_object CHECK (ticks_per_object IS NULL OR ticks_per_object > 0),
            CONSTRAINT ck_tick_range_failure      CHECK (status <> 'FAILED' OR failure_reason IS NOT NULL),
            CONSTRAINT ck_tick_range_storage      CHECK (
                status NOT IN ('PROCESSED', 'EXPIRED')
                OR (storage_bucket IS NOT NULL AND storage_prefix IS NOT NULL
                    AND records_produced IS NOT NULL AND objects_produced IS NOT NULL
                    AND ticks_per_object IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_tick_range_expiry
            ON tick_range (expires_at)
            WHERE status = 'PROCESSED'
        """
    )
    op.execute(
        """
        CREATE TABLE domain_event (
            event_id           UUID          NOT NULL,
            event_type         VARCHAR(100)  NOT NULL,
            aggregate_type     VARCHAR(100)  NOT NULL,
            aggregate_id       UUID          NOT NULL,
            aggregate_version  INTEGER       NULL,
            recorded_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
            payload            JSONB         NOT NULL,
            metadata           JSONB         NOT NULL DEFAULT '{}'::jsonb,
            correlation_id     UUID          NULL,
            causation_id       UUID          NULL,
            published_at       TIMESTAMPTZ   NULL,

            CONSTRAINT pk_domain_event PRIMARY KEY (event_id),
            CONSTRAINT uq_domain_event_aggregate_version
                UNIQUE (aggregate_type, aggregate_id, aggregate_version),
            CONSTRAINT ck_domain_event_aggregate_version
                CHECK (aggregate_version IS NULL OR aggregate_version > 0),
            CONSTRAINT ck_domain_event_version_required
                CHECK ((event_type IN ('TickRangeDataRequested', 'TickRangeDataDelivered'))
                       = (aggregate_version IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX ix_domain_event_aggregate ON domain_event (aggregate_id, aggregate_version)")
    op.execute("CREATE INDEX ix_domain_event_aggregate_time ON domain_event (aggregate_id, recorded_at)")
    op.execute("CREATE INDEX ix_domain_event_type_recorded ON domain_event (event_type, recorded_at)")
    op.execute(
        "CREATE INDEX ix_domain_event_pending ON domain_event (recorded_at) WHERE published_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_domain_event_correlation ON domain_event (correlation_id) "
        "WHERE correlation_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE domain_event")
    op.execute("DROP TABLE tick_range")
    op.execute("DROP TYPE tick_range_status")
