import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.ai.agents import SweetOrderAgent
from app.ai.runner import get_openai_tools


class AIRunnerToolWiringTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
