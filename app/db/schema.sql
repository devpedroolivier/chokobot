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

  -- Campos nativos
  e.categoria          AS categoria,
  e.produto            AS produto,
  e.tamanho            AS tamanho,
  e.massa              AS massa,
  e.recheio            AS recheio,
  e.mousse             AS mousse,
  e.adicional          AS adicional,
  e.kit_festou         AS kit_festou,
  e.quantidade         AS quantidade,
  e.valor_total        AS valor_total,
  e.data_entrega       AS data_entrega,
  e.horario            AS horario,
  e.serve_pessoas      AS serve_pessoas,
  e.criado_em          AS criado_em,

  -- Aliases de compatibilidade
  e.adicional          AS fruta_ou_nozes,
  e.horario            AS horario_retirada,
  TRIM(COALESCE(e.massa, '') || ' | ' || COALESCE(e.recheio, '') || ' + ' || COALESCE(e.mousse, '')) AS descricao,
  e.valor_total        AS valor,
  e.horario            AS hora_entrega,

  -- Entrega/retirada
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
  en.id                AS id,
  en.encomenda_id,
  e.data_entrega,
  e.horario            AS horario_retirada,
  c.nome               AS cliente_nome,
  c.telefone           AS cliente_telefone,
  en.tipo,
  en.status,
  en.endereco,
  NULL AS numero,
  NULL AS bairro,
  NULL AS cidade,
  NULL AS cep,
  NULL AS complemento,
  en.data_agendada     AS criado_em
FROM entregas en
LEFT JOIN encomendas e ON e.id = en.encomenda_id
LEFT JOIN clientes c ON c.id = e.cliente_id
ORDER BY en.data_agendada DESC;
