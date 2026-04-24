import asyncio
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.application.service_registry import get_messaging_gateway  # noqa: E402


OUTBOX_PATH = os.getenv("OUTBOX_PATH", "dados/outbox.jsonl")


async def _drain() -> int:
    if not os.path.exists(OUTBOX_PATH):
        print(f"Outbox not found: {OUTBOX_PATH}")
        return 0

    with open(OUTBOX_PATH, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    if not lines:
        print("Outbox empty.")
        return 0

    gateway = get_messaging_gateway()
    remaining: list[str] = []

    for line in lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
            phone = str(item.get("phone", "")).strip()
            message = str(item.get("message", "")).strip()
            if not phone or not message:
                remaining.append(line)
                continue
        except Exception:
            remaining.append(line)
            continue

        try:
            ok = await gateway.send_text(phone, message)
        except Exception as exc:
            print(f"Error sending to {phone}: {exc!r}")
            ok = False

        if not ok:
            remaining.append(line)

    with open(OUTBOX_PATH, "w", encoding="utf-8") as handle:
        handle.writelines(remaining)

    sent = len(lines) - len(remaining)
    print(f"Reprocess done. Sent={sent}, Remaining={len(remaining)}")
    return 0


def main() -> int:
    return asyncio.run(_drain())


if __name__ == "__main__":
    raise SystemExit(main())
