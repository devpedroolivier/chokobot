"""Add tenant_id to every domain table and create the outbox table.

Revision ID: 0003_tenant_id_on_domain
Revises: 0002_tenant_tables
Create Date: 2026-04-26

Postgres-only migration. Adds ``tenant_id BIGINT NOT NULL REFERENCES
tenants(id)`` to every domain table, backfilling the legacy
Chokodelícia rows with ``tenant_id = 1`` (seeded in 0002). Also:

- Replaces the ``clientes.telefone`` UNIQUE constraint with a compound
  unique on ``(tenant_id, telefone)`` — different tenants can share a
  phone number.
- Adds a new ``outbox`` table for the Phase B replacement of
  ``dados/outbox.jsonl`` (decision 7 in PHASE_B_DECISIONS.md). Same
  tenant_id discipline.
- Adds compound indexes ``(tenant_id, …)`` on hot lookup paths.
- Recreates ``v_encomendas`` / ``v_entregas`` so the views expose
  ``tenant_id`` and queries can filter on them.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0003_tenant_id_on_domain"
down_revision: Union[str, Sequence[str], None] = "0002_tenant_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DOMAIN_TABLES = (
    "clientes",
    "encomendas",
    "entregas",
    "pedidos_cafeteria",
    "encomenda_doces",
    "atendimentos",
    "customer_processes",
)


ADD_TENANT_ID_COLUMN = """
ALTER TABLE {table}
    ADD COLUMN tenant_id BIGINT REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE {table} SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_{table}_tenant_id ON {table}(tenant_id);
"""


CLIENTES_TENANT_PHONE_UNIQUE = """
ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_telefone_key;
ALTER TABLE clientes ADD CONSTRAINT clientes_tenant_telefone_key
    UNIQUE (tenant_id, telefone);
"""


CREATE_OUTBOX = """
CREATE TABLE outbox (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone           TEXT NOT NULL,
    message         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued', 'sent', 'failed', 'cancelled')),
    error_message   TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    last_attempt_at TIMESTAMPTZ
);
CREATE INDEX idx_outbox_tenant_status ON outbox(tenant_id, status);
CREATE INDEX idx_outbox_queued_at ON outbox(queued_at);
"""


CREATE_EVENTS = """
CREATE TABLE events (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_type   TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_events_tenant_type ON events(tenant_id, event_type);
CREATE INDEX idx_events_occurred_at ON events(occurred_at);
"""


REBUILD_VIEW_ENCOMENDAS = """
DROP VIEW IF EXISTS v_encomendas;
CREATE VIEW v_encomendas AS
SELECT
    e.tenant_id,
    e.id AS id,
    e.id AS encomenda_id,
    e.cliente_id,
    c.nome AS cliente_nome,
    c.telefone AS cliente_telefone,
    e.categoria, e.produto, e.tamanho, e.massa, e.recheio, e.mousse,
    e.adicional, e.kit_festou, e.quantidade, e.valor_total,
    e.data_entrega, e.horario, e.serve_pessoas, e.criado_em,
    e.adicional AS fruta_ou_nozes,
    e.horario AS horario_retirada,
    TRIM(COALESCE(e.massa, '') || ' | ' || COALESCE(e.recheio, '') || ' + ' || COALESCE(e.mousse, '')) AS descricao,
    e.valor_total AS valor,
    e.horario AS hora_entrega,
    en.tipo AS entrega_tipo,
    en.status AS entrega_status,
    en.endereco AS endereco,
    NULL::TEXT AS numero, NULL::TEXT AS bairro, NULL::TEXT AS cidade,
    NULL::TEXT AS cep, NULL::TEXT AS complemento,
    en.data_agendada AS entrega_criado_em
FROM encomendas e
LEFT JOIN clientes c
    ON c.id = e.cliente_id AND c.tenant_id = e.tenant_id
LEFT JOIN entregas en
    ON en.encomenda_id = e.id AND en.tenant_id = e.tenant_id
ORDER BY e.criado_em DESC;
"""


REBUILD_VIEW_ENTREGAS = """
DROP VIEW IF EXISTS v_entregas;
CREATE VIEW v_entregas AS
SELECT
    en.tenant_id,
    en.id AS id,
    en.encomenda_id,
    e.data_entrega,
    e.horario AS horario_retirada,
    c.nome AS cliente_nome,
    c.telefone AS cliente_telefone,
    en.tipo, en.status, en.endereco,
    NULL::TEXT AS numero, NULL::TEXT AS bairro, NULL::TEXT AS cidade,
    NULL::TEXT AS cep, NULL::TEXT AS complemento,
    en.data_agendada AS criado_em
FROM entregas en
LEFT JOIN encomendas e
    ON e.id = en.encomenda_id AND e.tenant_id = en.tenant_id
LEFT JOIN clientes c
    ON c.id = e.cliente_id AND c.tenant_id = en.tenant_id
ORDER BY en.data_agendada DESC;
"""


def upgrade() -> None:
    for table in DOMAIN_TABLES:
        op.execute(ADD_TENANT_ID_COLUMN.format(table=table))

    op.execute(CLIENTES_TENANT_PHONE_UNIQUE)
    op.execute(CREATE_OUTBOX)
    op.execute(CREATE_EVENTS)
    op.execute(REBUILD_VIEW_ENCOMENDAS)
    op.execute(REBUILD_VIEW_ENTREGAS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_entregas;")
    op.execute("DROP VIEW IF EXISTS v_encomendas;")
    op.execute("DROP TABLE IF EXISTS events;")
    op.execute("DROP TABLE IF EXISTS outbox;")
    op.execute("ALTER TABLE clientes DROP CONSTRAINT IF EXISTS clientes_tenant_telefone_key;")
    op.execute("ALTER TABLE clientes ADD CONSTRAINT clientes_telefone_key UNIQUE (telefone);")
    for table in DOMAIN_TABLES:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_tenant_id;")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id;")
