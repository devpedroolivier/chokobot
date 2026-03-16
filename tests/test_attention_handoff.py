import unittest

from app.application.use_cases.manage_human_handoff import activate_human_handoff, deactivate_human_handoff
from app.infrastructure.gateways.local_attention_gateway import LocalAttentionGateway
from app.services.estados import (
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
)


class AttentionHandoffTests(unittest.TestCase):
    def setUp(self):
        for state_map in (
            estados_atendimento,
            estados_encomenda,
            estados_cafeteria,
            estados_entrega,
            estados_cestas_box,
        ):
            state_map.clear()

    def test_activate_human_handoff_clears_pending_legacy_states(self):
        telefone = "5511999999999"
        estados_encomenda[telefone] = {"etapa": "massa"}
        estados_cafeteria[telefone] = {"etapa": "pedido"}
        estados_entrega[telefone] = {"etapa": "endereco"}
        estados_cestas_box[telefone] = {"etapa": "selecao"}

        message = activate_human_handoff(telefone, nome="Cliente Teste", audit_writer=None)

        self.assertIn(telefone, estados_atendimento)
        self.assertEqual(message, "Um momento! Estou transferindo você para um dos nossos atendentes humanos. 👩‍🍳")
        self.assertNotIn(telefone, estados_encomenda)
        self.assertNotIn(telefone, estados_cafeteria)
        self.assertNotIn(telefone, estados_entrega)
        self.assertNotIn(telefone, estados_cestas_box)

    def test_local_attention_gateway_uses_shared_handoff_flow(self):
        gateway = LocalAttentionGateway()
        telefone = "5511888888888"
        estados_encomenda[telefone] = {"etapa": "massa"}

        result = gateway.activate_human_handoff(telefone=telefone, motivo="cliente pediu ajuda")

        self.assertIn(telefone, estados_atendimento)
        self.assertEqual(estados_atendimento[telefone]["motivo"], "cliente pediu ajuda")
        self.assertEqual(result, "Um momento! Estou transferindo você para um dos nossos atendentes humanos. 👩‍🍳")
        self.assertNotIn(telefone, estados_encomenda)

    def test_deactivate_human_handoff_reports_previous_state(self):
        telefone = "5511777777777"
        estados_atendimento[telefone] = {"humano": True}

        self.assertTrue(deactivate_human_handoff(telefone))
        self.assertFalse(deactivate_human_handoff(telefone))


if __name__ == "__main__":
    unittest.main()
