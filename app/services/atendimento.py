from app.utils.mensagens import responder_usuario
from app.application.use_cases.manage_human_handoff import (
    activate_human_handoff,
    build_reactivation_message,
    deactivate_human_handoff,
)

async def processar_atendimento(telefone: str, nome: str = "Cliente") -> None:
    mensagem = activate_human_handoff(telefone, nome=nome)
    await responder_usuario(telefone, mensagem)

async def encerrar_atendimento(telefone: str) -> None:
    deactivate_human_handoff(telefone)
    await responder_usuario(telefone, build_reactivation_message(include_menu=True))
