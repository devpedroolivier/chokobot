import unittest
from unittest.mock import patch

from app.ai import runner
from app.ai.tool_execution import handle_tool_call
from app.observability import clear_metrics, snapshot_metrics


class AIToolExecutionTests(unittest.TestCase):
    def setUp(self):
        clear_metrics()

    def test_transfer_to_agent_updates_session_and_keeps_run_active(self):
        session = {"messages": [], "current_agent": "TriageAgent"}
        saved = []
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="transfer_to_agent",
            arguments={"agent_name": "CafeteriaAgent"},
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: saved.append((telefone, dict(state))),
        )

        self.assertFalse(should_return)
        self.assertEqual(session["current_agent"], "CafeteriaAgent")
        self.assertIn("Transferencia interna concluida", tool_result)
        self.assertEqual(saved[0][0], "5511999999999")

    def test_escalate_to_human_clears_messages_and_short_circuits(self):
        session = {"messages": [{"role": "user", "content": "oi"}], "current_agent": "TriageAgent"}
        calls = []
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: calls.append((telefone, motivo)),
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="escalate_to_human",
            arguments={"motivo": "Cliente pediu humano"},
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
        )

        self.assertTrue(should_return)
        self.assertEqual(calls, [("5511999999999", "Cliente pediu humano")])
        self.assertEqual(session["messages"], [])
        self.assertIn("transferindo", tool_result)

    def test_create_cake_order_without_explicit_confirmation_only_saves_draft_process(self):
        session = {
            "messages": [{"role": "user", "content": "Quero esse bolo para sexta às 15:00"}],
            "current_agent": "CakeOrderAgent",
        }
        persisted_calls = []
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: persisted_calls.append(order) or "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        with patch(
            "app.ai.tool_execution.save_cake_order_draft_process",
            return_value=(
                "Pedido em rascunho salvo no atendimento. Valor oficial calculado: R$135,00. "
                "Ainda nao foi salvo como pedido confirmado no sistema. "
                "Peca uma confirmacao final explicita do cliente antes de concluir."
            ),
        ) as mocked_draft:
            should_return, tool_result = handle_tool_call(
                runtime=runtime,
                function_name="create_cake_order",
                arguments={
                    "linha": "tradicional",
                    "categoria": "tradicional",
                    "descricao": "Bolo tradicional",
                    "data_entrega": "10/10/2030",
                    "horario_retirada": "15:00",
                    "modo_recebimento": "retirada",
                    "pagamento": {"forma": "PIX"},
                },
                telefone="5511999999999",
                nome_cliente="Cliente",
                cliente_id=1,
                session=session,
                save_session_fn=lambda telefone, state: None,
            )

        self.assertFalse(should_return)
        self.assertEqual(persisted_calls, [])
        mocked_draft.assert_called_once()
        self.assertEqual(session["messages"][0]["content"], "Quero esse bolo para sexta às 15:00")
        self.assertIn("rascunho", tool_result)
        self.assertIn("Ainda nao foi salvo como pedido confirmado no sistema", tool_result)
        counters, _ = snapshot_metrics()
        blocked_total = sum(
            value
            for (name, _labels), value in counters.items()
            if name == "ai_order_confirmation_blocks_total"
        )
        self.assertEqual(blocked_total, 1.0)

    def test_create_sweet_order_with_explicit_confirmation_persists_and_clears_session(self):
        session = {
            "messages": [{"role": "user", "content": "Sim, pode fechar."}],
            "current_agent": "SweetOrderAgent",
        }
        saved = []
        persisted_calls = []
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: persisted_calls.append(order) or "Pedido de doces salvo com sucesso! ID: 77",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="create_sweet_order",
            arguments={
                "itens": [{"nome": "Brigadeiro Escama", "quantidade": 10}],
                "data_entrega": "10/10/2030",
                "horario_retirada": "15:00",
                "modo_recebimento": "retirada",
                "pagamento": {"forma": "PIX"},
            },
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: saved.append((telefone, dict(state))),
        )

        self.assertTrue(should_return)
        self.assertEqual(len(persisted_calls), 1)
        self.assertEqual(session["messages"], [])
        self.assertEqual(saved[0][0], "5511999999999")
        self.assertIn("pedido foi finalizado", tool_result)

    def test_get_cake_options_uses_runtime_and_keeps_run_active(self):
        session = {"messages": [], "current_agent": "CakeOrderAgent"}
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": f"{category}:{option_type}",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="get_cake_options",
            arguments={"category": "tradicional", "option_type": "recheio"},
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
        )

        self.assertFalse(should_return)
        self.assertEqual(tool_result, "tradicional:recheio")

    def test_get_cake_pricing_uses_runtime_and_keeps_run_active(self):
        session = {"messages": [], "current_agent": "KnowledgeAgent"}
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
            get_cake_pricing=lambda category="tradicional", tamanho=None, produto=None, adicional=None, cobertura=None, kit_festou=False, quantidade=1: (
                f"{category}:{tamanho}:{produto}:{adicional}:{cobertura}:{kit_festou}:{quantidade}"
            ),
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="get_cake_pricing",
            arguments={"category": "tradicional", "tamanho": "B3", "kit_festou": True},
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
        )

        self.assertFalse(should_return)
        self.assertEqual(tool_result, "tradicional:B3:None:None:None:True:1")

    def test_lookup_catalog_items_uses_runtime_and_keeps_run_active(self):
        session = {"messages": [], "current_agent": "KnowledgeAgent"}
        runtime = runner.AIRuntime(
            get_menu=lambda category="todas": "menu",
            get_cake_options=lambda category="tradicional", option_type="recheio": "cake-options",
            get_learnings=lambda: "",
            save_learning=lambda aprendizado: aprendizado,
            escalate_to_human=lambda telefone, motivo: "ok",
            create_cake_order=lambda telefone, nome_cliente, cliente_id, order: "pedido",
            create_sweet_order=lambda telefone, nome_cliente, cliente_id, order: "doces",
            lookup_catalog_items=lambda query, catalog="auto": f"{catalog}:{query}",
        )

        should_return, tool_result = handle_tool_call(
            runtime=runtime,
            function_name="lookup_catalog_items",
            arguments={"query": "croasant de chocolate", "catalog": "cafeteria"},
            telefone="5511999999999",
            nome_cliente="Cliente",
            cliente_id=1,
            session=session,
            save_session_fn=lambda telefone, state: None,
        )

        self.assertFalse(should_return)
        self.assertEqual(tool_result, "cafeteria:croasant de chocolate")


if __name__ == "__main__":
    unittest.main()
