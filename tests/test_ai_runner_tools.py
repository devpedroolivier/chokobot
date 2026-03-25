import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.agents import CakeOrderAgent, KnowledgeAgent, SweetOrderAgent
from app.ai.runner import get_openai_tools
from app.ai.tools import get_cake_options


class AIRunnerToolWiringTests(unittest.TestCase):
    def test_cake_order_agent_registers_cake_options_tool(self):
        tools = get_openai_tools(CakeOrderAgent)
        function_names = {tool["function"]["name"] for tool in tools}

        self.assertIn("get_cake_options", function_names)
        self.assertIn("get_cake_pricing", function_names)

    def test_knowledge_agent_registers_cake_pricing_tool(self):
        tools = get_openai_tools(KnowledgeAgent)
        function_names = {tool["function"]["name"] for tool in tools}

        self.assertIn("get_cake_pricing", function_names)

    def test_sweet_order_agent_registers_sweet_tool(self):
        tools = get_openai_tools(SweetOrderAgent)
        function_names = {tool["function"]["name"] for tool in tools}

        self.assertIn("create_sweet_order", function_names)

    def test_transfer_tool_allows_sweet_order_agent(self):
        tools = get_openai_tools(SweetOrderAgent)
        transfer_tool = next(tool for tool in tools if tool["function"]["name"] == "transfer_to_agent")
        allowed_agents = transfer_tool["function"]["parameters"]["properties"]["agent_name"]["enum"]

        self.assertIn("SweetOrderAgent", allowed_agents)

    def test_sweet_tool_description_requires_explicit_confirmation(self):
        tools = get_openai_tools(SweetOrderAgent)
        sweet_tool = next(tool for tool in tools if tool["function"]["name"] == "create_sweet_order")
        description = sweet_tool["function"]["description"]

        self.assertIn("confirmacao final explicita", description)
        self.assertIn("ultima mensagem do cliente", description)

    def test_cake_options_tool_requires_category_and_option_type(self):
        tools = get_openai_tools(CakeOrderAgent)
        cake_options_tool = next(tool for tool in tools if tool["function"]["name"] == "get_cake_options")
        params = cake_options_tool["function"]["parameters"]

        self.assertEqual(params["required"], ["category", "option_type"])
        self.assertIn("tradicional", params["properties"]["category"]["enum"])
        self.assertIn("recheio", params["properties"]["option_type"]["enum"])

    def test_get_cake_options_returns_full_traditional_fillings(self):
        result = get_cake_options("tradicional", "recheio")

        self.assertEqual(
            result,
            "Temos estes recheios: Beijinho, Brigadeiro, Brigadeiro de Nutella, "
            "Brigadeiro Branco Gourmet, Brigadeiro Branco de Ninho, Casadinho e Doce de Leite. "
            "Se escolher Casadinho, nao precisa de mousse.",
        )
        self.assertNotIn(", Ninho,", result)
        self.assertNotIn("Morango", result)


if __name__ == "__main__":
    unittest.main()
