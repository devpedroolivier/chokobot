"""Multi-tenant control plane: tenants, tenant_config, tenant_knowledge, users.

Revision ID: 0002_tenant_tables
Revises: 0001_baseline
Create Date: 2026-04-26

Postgres-only migration. It introduces the platform tables that hold
each tenant's identity, configuration, knowledge files and panel
users. A seed row for Chokodelícia is inserted so existing data can be
attached to ``tenant_id = 1`` by the follow-up migration 0003.

This migration is intentionally Postgres-flavoured (BIGSERIAL, JSONB,
TEXT[]). It does not run against the legacy SQLite database — the
SQLite branch stays at revision 0001_baseline until the cutover swaps
DATABASE_URL to Postgres and ``alembic upgrade head`` is executed.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0002_tenant_tables"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_TENANTS = """
CREATE TABLE tenants (
    id                  BIGSERIAL PRIMARY KEY,
    slug                TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active', 'suspended', 'trial')),
    evolution_instance  TEXT NOT NULL UNIQUE,
    timezone            TEXT NOT NULL DEFAULT 'America/Sao_Paulo',
    admin_phones        TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    webhook_secret      TEXT,
    branding            JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_TENANT_CONFIG = """
CREATE TABLE tenant_config (
    tenant_id    BIGINT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    schedule     JSONB NOT NULL DEFAULT '{}'::JSONB,
    commercial   JSONB NOT NULL DEFAULT '{}'::JSONB,
    cutoffs      JSONB NOT NULL DEFAULT '{}'::JSONB,
    branding     JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_TENANT_KNOWLEDGE = """
CREATE TABLE tenant_knowledge (
    tenant_id     BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    slot          TEXT NOT NULL,
    content_type  TEXT NOT NULL CHECK (content_type IN ('markdown', 'json')),
    content       TEXT NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, slot)
);
"""

CREATE_USERS = """
CREATE TABLE users (
    id             BIGSERIAL PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    tenant_id      BIGINT REFERENCES tenants(id) ON DELETE CASCADE,
    role           TEXT NOT NULL
                     CHECK (role IN ('platform_admin', 'tenant_admin', 'tenant_operator')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT users_tenant_role_consistency CHECK (
        (role = 'platform_admin' AND tenant_id IS NULL)
        OR (role IN ('tenant_admin', 'tenant_operator') AND tenant_id IS NOT NULL)
    )
);
"""

# The seed row for Chokodelícia. Using id=1 deliberately so migration
# 0003 can backfill existing legacy rows with tenant_id = 1 without
# extra lookup. Branding is intentionally minimal — Phase B.D loads
# rich branding from tenant_config.branding.
SEED_CHOKODELICIA = """
INSERT INTO tenants (
    id, slug, display_name, status, evolution_instance, timezone,
    admin_phones, branding
)
VALUES (
    1,
    'chokodelicia',
    'Chokodelícia',
    'active',
    'chokodelicia',
    'America/Sao_Paulo',
    ARRAY[]::TEXT[],
    '{"display_name": "Chokodelícia", "short_name": "Choko"}'::JSONB
);

-- Keep BIGSERIAL counter in sync with the explicit id above.
SELECT setval(pg_get_serial_sequence('tenants', 'id'), 1, true);

INSERT INTO tenant_config (tenant_id, schedule, commercial, cutoffs, branding)
VALUES (
    1,
    '{
        "timezone": "America/Sao_Paulo",
        "weekly": {
            "sunday": null,
            "monday": ["12:00", "18:00"],
            "tuesday": ["09:00", "18:00"],
            "wednesday": ["09:00", "18:00"],
            "thursday": ["09:00", "18:00"],
            "friday": ["09:00", "18:00"],
            "saturday": ["09:00", "18:00"]
        }
    }'::JSONB,
    '{
        "delivery_fee_standard": 10.00,
        "delivery_fee_cafeteria": 5.00,
        "card_installment_min_total": 100.00,
        "card_installment_max": 2,
        "payment_methods": ["PIX", "Cartão (débito/crédito)", "Dinheiro"],
        "pix_key": ""
    }'::JSONB,
    '{
        "same_day_cake_order": "11:00",
        "delivery": "17:30",
        "croissant_prep_minutes": 20
    }'::JSONB,
    '{
        "display_name": "Chokodelícia",
        "short_name": "Choko",
        "social_handle": "@chokodelicia",
        "easter_link": "https://pascoachoko.goomer.app"
    }'::JSONB
);
"""


def upgrade() -> None:
    op.execute(CREATE_TENANTS)
    op.execute(CREATE_TENANT_CONFIG)
    op.execute(CREATE_TENANT_KNOWLEDGE)
    op.execute(CREATE_USERS)
    op.execute(SEED_CHOKODELICIA)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users;")
    op.execute("DROP TABLE IF EXISTS tenant_knowledge;")
    op.execute("DROP TABLE IF EXISTS tenant_config;")
    op.execute("DROP TABLE IF EXISTS tenants;")
