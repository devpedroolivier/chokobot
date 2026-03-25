import unittest

from app.ai.agents import CAFETERIA_PROMPT, KNOWLEDGE_PROMPT, TRIAGE_PROMPT
from app.ai.policies import DELIVERY_CUTOFF_LABEL, SAME_DAY_CAKE_ORDER_CUTOFF_LABEL
from app.services.commercial_rules import DELIVERY_RULE_LINE, PAYMENT_CHANGE_RULE_LINE, STORE_OPERATION_RULE_LINE


class CommercialRulesTests(unittest.TestCase):
    def test_cutoff_labels_match_prompt_and_policy(self):
        self.assertEqual(SAME_DAY_CAKE_ORDER_CUTOFF_LABEL, "11:00")
        self.assertEqual(DELIVERY_CUTOFF_LABEL, "17:30")
        self.assertIn("DEPOIS das 11:00", TRIAGE_PROMPT)
        self.assertIn("até 17:30", DELIVERY_RULE_LINE)

    def test_shared_operational_rule_lines_are_reused_in_prompts(self):
        self.assertIn(DELIVERY_RULE_LINE, TRIAGE_PROMPT)
        self.assertIn(DELIVERY_RULE_LINE, CAFETERIA_PROMPT)
        self.assertIn(STORE_OPERATION_RULE_LINE, KNOWLEDGE_PROMPT)
        self.assertIn(PAYMENT_CHANGE_RULE_LINE, CAFETERIA_PROMPT)


if __name__ == "__main__":
    unittest.main()
