import json
import os
import sys
import time
import httpx


HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))
HTTP_TIMEOUT_READ = int(os.getenv("HTTP_TIMEOUT_READ", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_BACKOFF_FACTOR = float(os.getenv("HTTP_BACKOFF_FACTOR", "1"))
OUTBOX_PATH = os.getenv("OUTBOX_PATH", "dados/outbox.jsonl")

ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE = os.getenv("ZAPI_BASE")
if not ZAPI_TOKEN or not ZAPI_BASE:
    print("Missing ZAPI_TOKEN or ZAPI_BASE in environment.")
    sys.exit(1)

ZAPI_ENDPOINT_TEXT = f"{ZAPI_BASE}/send-text"


def send_message(client: httpx.Client, phone: str, message: str) -> bool:
    payload = {"phone": phone, "message": message}
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_TOKEN}
    last_exc = None

    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            resp = client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
            if 200 <= resp.status_code < 300:
                return True
            if resp.status_code not in (429, 500, 502, 503, 504):
                return False
        except httpx.HTTPError as e:
            last_exc = e

        if attempt < HTTP_MAX_RETRIES:
            backoff = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
            time.sleep(backoff)

    if last_exc:
        print(f"HTTP error sending to {phone}: {repr(last_exc)}")
    return False


def main() -> int:
    if not os.path.exists(OUTBOX_PATH):
        print(f"Outbox not found: {OUTBOX_PATH}")
        return 0

    with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("Outbox empty.")
        return 0

    remaining = []
    timeout = httpx.Timeout(
        connect=HTTP_TIMEOUT_CONNECT,
        read=HTTP_TIMEOUT_READ,
        write=HTTP_TIMEOUT_READ,
        pool=HTTP_TIMEOUT_CONNECT,
    )

    with httpx.Client(timeout=timeout) as client:
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

            ok = send_message(client, phone, message)
            if not ok:
                remaining.append(line)

    with open(OUTBOX_PATH, "w", encoding="utf-8") as f:
        f.writelines(remaining)

    sent = len(lines) - len(remaining)
    print(f"Reprocess done. Sent={sent}, Remaining={len(remaining)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
