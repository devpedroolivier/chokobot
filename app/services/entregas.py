from datetime import datetime
import os

from app.utils.mensagens import responder_usuario
from app.models.entregas import salvar_entrega
from app.services.estados import estados_entrega  # ✅ usa os estados globais compartilhados

def salvar_entrega_txt(telefone, nome, dados):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = f"{agora} - {nome} | {telefone} | Endereço: {dados['endereco']} | Referência: {dados['referencia']}\n"

    try:
        os.makedirs("dados", exist_ok=True)
        with open("dados/entregas.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Entrega registrada no .txt:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar entrega:", e)

async def processar_entrega(telefone, texto, estado):
    etapa = estado["etapa"]
    dados = estado["dados"]
    nome = estado["nome"]

    print(f"📍 ETAPA ATUAL: {etapa}")

    if etapa == 1:
        dados["endereco"] = texto
        estado["etapa"] = 2
        await responder_usuario(telefone, "📞 Informe um telefone alternativo ou referência, se tiver:")

    elif etapa == 2:
        dados["referencia"] = texto

        encomenda_id = dados.get("encomenda_id")
        data_agendada = dados.get("data")

        if encomenda_id:
            try:
                salvar_entrega(
                    encomenda_id=encomenda_id,
                    tipo="entrega",
                    endereco=dados["endereco"],
                    data_agendada=data_agendada,
                    status="pendente"
                )
                print(f"✅ Entrega registrada com encomenda_id {encomenda_id}")
            except Exception as e:
                print(f"❌ ERRO ao salvar entrega no banco: {e}")

        salvar_entrega_txt(telefone, nome, dados)

        await responder_usuario(telefone, "🚚 Endereço registrado! Em breve confirmaremos o envio com você.")
        return "finalizar"
