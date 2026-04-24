#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
TMP_DIR = Path(os.getenv("CHOKOBOT_TEST_TMPDIR", "/tmp/chokobot-tests"))
EXCLUDED_TEST_FILES = {
    "test_ai_advanced.py",
    "test_ai_agent.py",
    "test_ai_all_flows.py",
    "test_ai_final_rules.py",
    "test_ai_nlp_dates.py",
    "test_e2e.py",
}
DEFAULT_ENV = {
    "BOT_AUTO_REPLIES_ENABLED": "1",
    "DB_PATH": str(TMP_DIR / "chokobot.db"),
    "OPENAI_API_KEY": "test-key",
    "OUTBOX_EVENTS_PATH": str(TMP_DIR / "domain_events.jsonl"),
    "OUTBOX_PATH": str(TMP_DIR / "outbox.jsonl"),
    "ZAPI_BASE": "https://example.test",
    "ZAPI_TOKEN": "test-token",
    "MESSAGING_PROVIDER": "zapi",
    "EVOLUTION_SERVER_URL": "http://evolution.test",
    "EVOLUTION_API_KEY": "test-key",
    "EVOLUTION_INSTANCE": "test",
}


def prepare_environment() -> None:
    TMP_DIR.mkdir(exist_ok=True)
    for file_name in ("chokobot.db", "domain_events.jsonl", "outbox.jsonl"):
        target = TMP_DIR / file_name
        if target.exists():
            target.unlink()

    for key, value in DEFAULT_ENV.items():
        os.environ.setdefault(key, value)


def build_suite() -> unittest.TestSuite:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    for path in sorted(TESTS_DIR.glob("test_*.py")):
        if path.name in EXCLUDED_TEST_FILES:
            continue
        suite.addTests(loader.discover(str(TESTS_DIR), pattern=path.name, top_level_dir=str(ROOT)))

    return suite


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    prepare_environment()

    suite = build_suite()
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    if EXCLUDED_TEST_FILES:
        excluded = ", ".join(sorted(EXCLUDED_TEST_FILES))
        print(f"\nArquivos excluidos da suite principal: {excluded}")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
