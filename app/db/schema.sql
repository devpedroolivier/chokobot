-- ===== RESET VIEWS =====
DROP VIEW IF EXISTS v_encomendas;
DROP VIEW IF EXISTS v_entregas;

-- ===== v_encomendas compatível com seu schema atual =====
CREATE VIEW v_encomendas AS
SELECT
  e.id                 AS id,
  e.id                 AS encomenda_id,
  e.cliente_id,
  c.nome               AS cliente_nome,
  c.telefone           AS cliente_telefone,

  -- Campos usados no painel (mapeados/placeholder)
  e.categoria          AS categoria,
  NULL                 AS linha,           -- não existe
  NULL                 AS tamanho,         -- não existe -> EVITA o erro atual
  NULL                 AS recheio,         -- não existe
  NULL                 AS mousse,          -- não existe
  e.fruta_ou_nozes     AS adicional,       -- mapeado
  e.descricao          AS observacoes,     -- mapeado
  e.valor_total        AS valor,           -- mapeado
  e.data_entrega       AS data_entrega,    -- mapeado (texto dd/mm/aaaa)
  e.horario_retirada   AS hora_entrega,    -- mapeado
  e.criado_em          AS criado_em,       -- p/ ORDER BY

  -- Entrega/retirada (placeholders p/ colunas ausentes)
  en.tipo              AS entrega_tipo,
  en.status            AS entrega_status,
  en.endereco          AS endereco,
  NULL                 AS numero,
  NULL                 AS bairro,
  NULL                 AS cidade,
  NULL                 AS cep,
  NULL                 AS complemento,
  en.data_agendada     AS entrega_criado_em
FROM encomendas e
LEFT JOIN clientes c  ON c.id = e.cliente_id
LEFT JOIN entregas en ON en.encomenda_id = e.id
ORDER BY e.criado_em DESC;

-- ===== v_entregas (detalhe) =====
CREATE VIEW v_entregas AS
SELECT
  en.id,
  en.encomenda_id,
  en.tipo,
  en.status,
  en.endereco,
  NULL AS numero,
  NULL AS bairro,
  NULL AS cidade,
  NULL AS cep,
  NULL AS complemento,
  en.data_agendada AS criado_em
FROM entregas en
ORDER BY en.data_agendada DESC;
