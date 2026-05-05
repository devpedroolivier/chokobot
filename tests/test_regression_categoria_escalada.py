"""Regressão: categorias granulares de escalada.

Antes da #20, 72% dos motivos caíam em 'falha_bot'. Agora há 10 categorias.
"""
import unittest

from app.application.use_cases.manage_human_handoff import _classify_escalation_category


class CategoriaEscaladaTests(unittest.TestCase):
    def test_dia_das_maes_e_campanha_ativa(self):
        self.assertEqual(
            _classify_escalation_category("Cliente perguntou sobre Dia das Maes"),
            "campanha_ativa_dia_das_maes",
        )

    def test_pluxee_e_pagamento_nao_suportado(self):
        self.assertEqual(
            _classify_escalation_category("Cliente perguntou sobre Pluxee"),
            "pagamento_nao_suportado",
        )
        self.assertEqual(
            _classify_escalation_category("Cliente quer pagar com Sodexo"),
            "pagamento_nao_suportado",
        )

    def test_status_pedido_e_pos_venda(self):
        self.assertEqual(
            _classify_escalation_category("Cliente quer status do pedido"),
            "pos_venda",
        )
        self.assertEqual(
            _classify_escalation_category("Cliente pediu para alterar a data"),
            "pos_venda",
        )

    def test_cesta_personalizada_e_pedido_personalizado(self):
        self.assertEqual(
            _classify_escalation_category("Cliente pediu cesta de cafe da manha"),
            "pedido_personalizado",
        )
        self.assertEqual(
            _classify_escalation_category("Cliente quer personalizar a cesta"),
            "pedido_personalizado",
        )

    def test_pascoa_continua_campanha_encerrada(self):
        self.assertEqual(
            _classify_escalation_category("Cliente perguntou sobre Pascoa fora de epoca"),
            "campanha_encerrada",
        )

    def test_cliente_solicitou_humano(self):
        self.assertEqual(
            _classify_escalation_category("cliente pediu humano"),
            "cliente_solicitou",
        )

    def test_default_falha_bot(self):
        self.assertEqual(
            _classify_escalation_category("motivo qualquer fora dos padroes"),
            "falha_bot",
        )


if __name__ == "__main__":
    unittest.main()
