from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.application.commands import GenerateAiReplyCommand, HandleInboundMessageCommand
from app.application.service_registry import get_command_bus

router = APIRouter(prefix="/internal")


class InboundMessageRequest(BaseModel):
    payload: dict


class AiReplyRequest(BaseModel):
    telefone: str
    text: str
    nome_cliente: str
    cliente_id: int


async def dispatch_inbound_via_bus(payload: dict):
    await get_command_bus().dispatch(HandleInboundMessageCommand(payload=payload))


async def generate_ai_reply_via_bus(data: AiReplyRequest) -> str:
    return await get_command_bus().dispatch(
        GenerateAiReplyCommand(
            telefone=data.telefone,
            text=data.text,
            nome_cliente=data.nome_cliente,
            cliente_id=data.cliente_id,
        )
    )


@router.post("/messages/handle")
async def handle_inbound_message(request: InboundMessageRequest):
    await dispatch_inbound_via_bus(request.payload)
    return {"status": "ok"}


@router.post("/messages/reply")
async def generate_reply(request: AiReplyRequest):
    reply = await generate_ai_reply_via_bus(request)
    return {"status": "ok", "reply": reply}
