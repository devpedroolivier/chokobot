# app/db/init_db.py  (or wherever you init)
def _create_views(conn):
    cur = conn.cursor()

    # Clean list of orders (joins client)
    cur.execute("""
    CREATE VIEW IF NOT EXISTS v_encomendas AS
    SELECT
      e.id,
      e.cliente_id,
      c.nome AS cliente_nome,
      c.telefone,
      e.categoria,
      e.produto,
      e.tamanho,
      e.descricao,
      e.fruta_ou_nozes,
      e.kit_festou,
      e.quantidade,
      e.data_entrega,
      e.horario_retirada,
      e.valor_total,
      e.serve_pessoas,
      e.criado_em
    FROM encomendas e
    JOIN clientes c ON c.id = e.cliente_id
    ;
    """)

    # Orders + (optional) delivery snapshot
    cur.execute("""
    CREATE VIEW IF NOT EXISTS v_entregas AS
    SELECT
      en.id AS encomenda_id,
      en.data_entrega,
      en.horario_retirada,
      c.nome AS cliente_nome,
      c.telefone,
      et.tipo,
      et.endereco,
      et.status,
      et.data_agendada,
      et.atualizado_em
    FROM encomendas en
    JOIN clientes c ON c.id = en.cliente_id
    LEFT JOIN entregas et ON et.encomenda_id = en.id
    ;
    """)

    conn.commit()
