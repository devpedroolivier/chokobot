DROP VIEW IF EXISTS v_encomendas;
DROP VIEW IF EXISTS v_entregas;

CREATE VIEW v_encomendas AS
SELECT
  e.id AS id,
  e.id AS encomenda_id,
  e.cliente_id,
  c.nome AS cliente_nome,
  c.telefone AS cliente_telefone,
  e.categoria AS categoria,
  COALESCE(NULLIF(e.linha, ''), e.categoria) AS linha,
  e.tamanho AS tamanho,
  e.recheio AS recheio,
  e.mousse AS mousse,
  COALESCE(e.adicional, e.fruta_ou_nozes) AS adicional,
  e.descricao AS observacoes,
  e.valor_total AS valor,
  e.data_entrega AS data_entrega,
  e.horario AS hora_entrega,
  e.forma_pagamento AS forma_pagamento,
  e.troco_para AS troco_para,
  e.criado_em AS criado_em,
  en.tipo AS entrega_tipo,
  en.status AS entrega_status,
  en.endereco AS endereco,
  en.data_agendada AS entrega_data_agendada,
  en.atualizado_em AS entrega_atualizado_em
FROM encomendas e
LEFT JOIN clientes c ON c.id = e.cliente_id
LEFT JOIN entregas en ON en.encomenda_id = e.id
ORDER BY e.criado_em DESC;

CREATE VIEW v_entregas AS
SELECT
  en.id,
  en.encomenda_id,
  en.tipo,
  en.status,
  en.endereco,
  en.data_agendada,
  en.atualizado_em
FROM entregas en
ORDER BY en.atualizado_em DESC;
