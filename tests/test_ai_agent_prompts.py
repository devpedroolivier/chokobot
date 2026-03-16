import unittest

from app.ai.agents import CAKE_ORDER_PROMPT, TRIAGE_PROMPT


class AIAgentPromptsTests(unittest.TestCase):
    def test_triage_prompt_uses_1730_cutoff_for_same_day_orders(self):
        self.assertIn("DEPOIS das 17:30", TRIAGE_PROMPT)
        self.assertIn("ATÉ as 17:30", TRIAGE_PROMPT)
        self.assertNotIn("DEPOIS das 11:00", TRIAGE_PROMPT)

    def test_cake_order_prompt_uses_1730_cutoff_for_same_day_orders(self):
        self.assertIn('já passou das 17:30', CAKE_ORDER_PROMPT)
        self.assertNotIn('já passou das 11:00', CAKE_ORDER_PROMPT)


if __name__ == "__main__":
    unittest.main()
