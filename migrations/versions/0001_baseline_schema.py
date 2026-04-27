"""Baseline schema snapshot — captures the current Chokodelícia tables and views.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-26

Idempotent (uses CREATE TABLE IF NOT EXISTS / CREATE VIEW IF NOT EXISTS)
so it can be applied to an existing production database without
disturbing data. New installs (and the Phase B cutover staging
environment) get the full schema in one run.

Phase B introduces a follow-up migration that adds ``tenant_id``
columns and the ``tenants`` / ``tenant_config`` / ``tenant_knowledge``
/ ``users`` tables.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_CLIENTES = """
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL UNIQUE,
    criado_em TEXT NOT NULL
);
"""

CREATE_ENCOMENDAS = """
CREATE TABLE IF NOT EXISTS encomendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    categoria TEXT,
    produto TEXT,
    tamanho TEXT,
    massa TEXT,
    recheio TEXT,
    mousse TEXT,
    adicional TEXT,
    kit_festou INTEGER DEFAULT 0,
    quantidade INTEGER DEFAULT 1,
    data_entrega TEXT,
    horario TEXT,
    valor_total REAL,
    serve_pessoas INTEGER,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);
"""

CREATE_ENTREGAS = """
CREATE TABLE IF NOT EXISTS entregas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encomenda_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    endereco TEXT,
    data_agendada TEXT,
    status TEXT,
    FOREIGN KEY (encomenda_id) REFERENCES encomendas (id)
);
"""

CREATE_PEDIDOS_CAFETERIA = """
CREATE TABLE IF NOT EXISTS pedidos_cafeteria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    pedido TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);
"""

CREATE_ENCOMENDA_DOCES = """
CREATE TABLE IF NOT EXISTS encomenda_doces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    encomenda_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    qtd INTEGER NOT NULL,
    preco REAL,
    unit REAL,
    FOREIGN KEY (encomenda_id) REFERENCES encomendas (id)
);
"""

CREATE_ATENDIMENTOS = """
CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    mensagem TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);
"""

CREATE_CUSTOMER_PROCESSES = """
CREATE TABLE IF NOT EXISTS customer_processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    customer_id INTEGER,
    process_type TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    source TEXT,
    draft_payload TEXT NOT NULL DEFAULT '{}',
    order_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (phone, process_type),
    FOREIGN KEY (customer_id) REFERENCES clientes (id),
    FOREIGN KEY (order_id) REFERENCES encomendas (id)
);
"""

CREATE_VIEW_ENCOMENDAS = """
CREATE VIEW IF NOT EXISTS v_encomendas AS
SELECT
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
    NULL AS numero, NULL AS bairro, NULL AS cidade, NULL AS cep, NULL AS complemento,
    en.data_agendada AS entrega_criado_em
FROM encomendas e
LEFT JOIN clientes c ON c.id = e.cliente_id
LEFT JOIN entregas en ON en.encomenda_id = e.id
ORDER BY e.criado_em DESC;
"""

CREATE_VIEW_ENTREGAS = """
CREATE VIEW IF NOT EXISTS v_entregas AS
SELECT
    en.id AS id,
    en.encomenda_id,
    e.data_entrega,
    e.horario AS horario_retirada,
    c.nome AS cliente_nome,
    c.telefone AS cliente_telefone,
    en.tipo, en.status, en.endereco,
    NULL AS numero, NULL AS bairro, NULL AS cidade, NULL AS cep, NULL AS complemento,
    en.data_agendada AS criado_em
FROM entregas en
LEFT JOIN encomendas e ON e.id = en.encomenda_id
LEFT JOIN clientes c ON c.id = e.cliente_id
ORDER BY en.data_agendada DESC;
"""


def upgrade() -> None:
    op.execute(CREATE_CLIENTES)
    op.execute(CREATE_ENCOMENDAS)
    op.execute(CREATE_ENTREGAS)
    op.execute(CREATE_PEDIDOS_CAFETERIA)
    op.execute(CREATE_ENCOMENDA_DOCES)
    op.execute(CREATE_ATENDIMENTOS)
    op.execute(CREATE_CUSTOMER_PROCESSES)
    op.execute(CREATE_VIEW_ENCOMENDAS)
    op.execute(CREATE_VIEW_ENTREGAS)


def downgrade() -> None:
    # The baseline is intentionally not reversible — destroying the
    # production schema is never the right Alembic action.
    raise RuntimeError("Baseline schema is not downgradable.")
