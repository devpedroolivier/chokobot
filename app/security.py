import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import (
    PANEL_AUTH_PASS,
    PANEL_AUTH_USER,
    WEBHOOK_SECRET,
    WEBHOOK_SIGNATURE_HEADER,
    WEBHOOK_TOKEN,
    WEBHOOK_TOKEN_HEADER,
)

_basic = HTTPBasic(auto_error=False)


def _unauthorized(detail: str = "Unauthorized") -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Basic"},
    )


def require_panel_auth(
    credentials: HTTPBasicCredentials = Depends(_basic),
) -> None:
    if credentials is None:
        _unauthorized("Painel sem autenticacao")

    valid_user = secrets.compare_digest(credentials.username, PANEL_AUTH_USER)
    valid_pass = secrets.compare_digest(credentials.password, PANEL_AUTH_PASS)
    if not (valid_user and valid_pass):
        _unauthorized("Credenciais invalidas")


def validate_webhook_request(request: Request, raw_body: bytes) -> None:
    if WEBHOOK_TOKEN:
        received_token = (request.headers.get(WEBHOOK_TOKEN_HEADER) or "").strip()
        if not received_token or not secrets.compare_digest(received_token, WEBHOOK_TOKEN):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook token invalido")

    if WEBHOOK_SECRET:
        received_sig = (request.headers.get(WEBHOOK_SIGNATURE_HEADER) or "").strip()
        if not received_sig:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura ausente")

        if received_sig.lower().startswith("sha256="):
            received_sig = received_sig.split("=", 1)[1]

        expected_sig = hmac.new(
            WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not secrets.compare_digest(received_sig.lower(), expected_sig.lower()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura invalida")
