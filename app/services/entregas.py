# app/services/entregas.py
from datetime import datetime
import os

from app.utils.mensagens import responder_usuario
from app.models.entregas import salvar_entrega
from app.services.estados import estados_entrega
from app.services.precos import montar_resumo  # pedido já vem com total calculado

def salvar_entrega_txt(telefone, nome, dados):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = (
        f"{agora} - {nome} | {telefone} | "
        f"Endereço: {dados.get('endereco','')} | Referência: {dados.get('referencia','')}\n"
    )
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

    print(f"📍 ETAPA ATUAL (entrega): {etapa}")

    # ETAPA 1 — endereço
    if etapa == 1:
        dados["endereco"] = texto.strip()
        estado["etapa"] = 2
        await responder_usuario(
            telefone,
            "📞 Informe um *telefone alternativo* ou *referência* (ex.: portaria, bloco, ponto de referência):"
        )
        return

    # ETAPA 2 — referência -> MOSTRA RESUMO e pede CONFIRMAÇÃO (não salvar ainda)
    if etapa == 2:
        dados["referencia"] = texto.strip()

        pedido = dados.get("pedido") or {}
        pedido["endereco"] = dados.get("endereco", "")  # 🔹 garante endereço no resumo
        pedido["referencia"] = dados.get("referencia", "")
        try:
            total = float(pedido.get("valor_total", 0))
            # Usa o valor total já com a taxa de entrega aplicada
            await responder_usuario(telefone, montar_resumo(pedido, total))
            await responder_usuario(
                telefone,
                "💲 *Obs: já inclui a taxa de entrega de R$ 10,00.*"
            )
        except Exception as e:
            print(f"⚠️ Não foi possível montar o resumo: {e}")

        estado["etapa"] = "confirmar_entrega"
        await responder_usuario(
            telefone,
            "Está tudo correto?\n"
            "1️⃣ Confirmar pedido\n"
            "2️⃣ Corrigir endereço\n"
            "3️⃣ Falar com atendente"
        )
        return

    # ETAPA 3 — confirmação final (agora sim salva)
    if etapa == "confirmar_entrega":
        opc = texto.strip().lower()

        if opc in ["1", "confirmar", "ok", "c", "sim", "s", "confirmar pedido", "pedido confirmado", "confirmo"]:
            encomenda_id = dados.get("encomenda_id")
            print(f"✅ DEBUG: Pedido confirmado via ENTREGA para {telefone} | Encomenda ID {encomenda_id}")

            # junta referência ao endereço
            endereco_base = dados.get("endereco", "")
            ref = dados.get("referencia", "")
            endereco_final = f"{endereco_base} | Ref: {ref}" if ref else endereco_base

            try:
                salvar_entrega(
                    encomenda_id=encomenda_id,
                    tipo="entrega",
                    endereco=endereco_final,
                    data_agendada=dados.get("data"),
                    status="pendente"
                )
                salvar_entrega_txt(telefone, nome, dados)
            except Exception as e:
                print(f"❌ ERRO ao salvar entrega: {e}")

            # garante que o fluxo termine
            estados_entrega.pop(telefone, None)

            await responder_usuario(
                telefone,
                "Pedido confirmado com sucesso ✅\n"
                "Obrigada por encomendar com a *Choko* ❤\n"
                "✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia"
            )
            return "finalizar"



        if opc in ["2", "corrigir", "endereco", "endereço", "ajustar", "editar"]:
            estado["etapa"] = 1
            await responder_usuario(telefone, "Sem problema! Envie novamente o *endereço completo*:")
            return

        if opc in ["3", "atendente", "humano", "falar", "ajuda"]:
            estados_entrega.pop(telefone, None)
            await responder_usuario(telefone, "Vou te conectar com um atendente. 👩‍🍳")
            return "finalizar"

        await responder_usuario(
            telefone,
            "Escolha uma opção:\n"
            "1️⃣ Confirmar pedido\n"
            "2️⃣ Corrigir endereço\n"
            "3️⃣ Falar com atendente"
        )
        return
