from datetime import datetime
from app.utils.mensagens import responder_usuario

def salvar_atendimento_txt(telefone: str, nome: str):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = f"{agora} - {nome} | {telefone} solicitou atendimento humano\n"

    try:
        with open("dados/atendimentos.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("🧑‍💻 Atendimento humano registrado:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar atendimento:", e)

async def processar_atendimento(telefone: str, nome: str):
    salvar_atendimento_txt(telefone, nome)
    await responder_usuario(
        telefone,
        "👤 Sua solicitação foi registrada!\nEm breve um atendente humano falará com você pelo WhatsApp 😊"
    )
