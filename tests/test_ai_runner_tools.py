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


if __name__ == "__main__":
    unittest.main()
