from datetime import datetime
from app.models.entregas import salvar_entrega
from app.services.entregas import processar_entrega
from app.utils.mensagens import responder_usuario
from app.utils.banco import salvar_encomenda_sqlite
from app.services.estados import estados_entrega  # ✅ somente esse!

async def processar_encomenda(telefone, texto, estado, nome_cliente):
    etapa = estado["etapa"]
    dados = estado["dados"]

    if etapa == 1:
        if texto in ["1", "normal", "personalizado"]:
            estado["linha"] = "normal"
            dados["linha"] = "normal"
            estado["etapa"] = 2

            estado["etapa"] = 2
            await responder_usuario(
                telefone,
                "🍰 *Monte seu bolo personalizado!*\n\n"
                "1️⃣ Escolha a massa:\n- Branca\n- Chocolate\n- Mesclada"
            )
        elif texto in ["2", "gourmet"]:
            estado["linha"] = "gourmet"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "✨ *Linha Gourmet:*\n"
                "- Bolo Inglês\n- Inglês Belga\n- Floresta Negra\n"
                "- Língua de Gato\n- Ninho com Morango\n"
                "- Nozes com Doce de Leite\n- Olho de Sogra\n- Red Velvet\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome do bolo desejado:"
            )
        elif texto in ["3", "p6", "redondo", "bolo redondo"]:
            estado["linha"] = "redondo"
            dados["linha"] = "redondo"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🍥 *Bolos Redondos P6 (serve 20 pessoas):*\n"
                "- P6 Língua de Gato de Chocolate\n"
                "- P6 Língua de Gato de Chocolate Branco\n"
                "- P6 Camafeu\n"
                "- P6 Naked Cake\n"
                "- P6 Red Velvet\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome do bolo desejado:"
            )
        elif texto in ["4", "torta", "tortas"]:
            estado["linha"] = "torta"
            dados["linha"] = "torta"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🥧 *Tortas (serve 16 pessoas):*\n"
                "- Torta Argentina\n- Torta Banoffee\n"
                "- Cheesecake Tradicional\n- Cheesecake Pistache\n"
                "- Citrus Pie\n- Torta Limão\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome da torta desejada:"
            )

        elif texto in ["5", "pronta entrega"]:
            estado["linha"] = "pronta_entrega"
            estado["etapa"] = "confirmar_pronta"
            await responder_usuario(
                telefone,
                "📦 *Pronta entrega de hoje:*\n"
                "- B3 Mesclado com Brigadeiro e Ninho\n"
                "- B4 Mesclado com Brigadeiro e Ninho\n\n"
                "📝 Digite o nome do bolo desejado:"
            )

        else:
            await responder_usuario(
                telefone,
                "🎂 *Escolha uma linha de bolo para começar:*\n"
                "1️⃣ Montar bolo personalizado\n"
                "2️⃣ Linha Gourmet\n"
                "3️⃣ Bolos Redondos (P6)\n"
                "4️⃣ Tortas\n\n"
                "Digite o número ou nome da linha desejada."
            )

    elif etapa == 2:
        massas_validas = ["branca", "chocolate", "mesclada"]
        massa = texto.strip().lower()

        if massa not in massas_validas:
            await responder_usuario(
                telefone,
                "⚠️ Massa inválida. Escolha uma das opções:\n- Branca\n- Chocolate\n- Mesclada"
            )
            return

        dados["massa"] = massa.capitalize()
        estado["etapa"] = 3
        await responder_usuario(
            telefone,
            "🍫 *Escolha 1 recheio:*\n"
            "- Beijinho\n- Brigadeiro\n- Brigadeiro de Nutella\n"
            "- Brigadeiro Branco\n- Branco Gourmet\n- Branco de Ninho\n"
            "- Casadinho\n- Doce de Leite\n\n"
            "📌 *Escolha 1 mousse:*\n"
            "- Ninho ou Trufa Branca\n- Chocolate ou Trufa Preta\n\n"
            "📝 Envie os dois juntos no formato:\n"
            "`Brigadeiro + Ninho`\n\n"
            "Exemplo: *Brigadeiro + Ninho*"
        )

    elif etapa == 3:
        if "+" not in texto:
            await responder_usuario(telefone, "⚠️ Envie no formato: Brigadeiro + Ninho")
            return

        recheio, mousse = map(str.strip, texto.split("+", 1))
        dados["recheio"] = recheio
        dados["mousse"] = mousse
        estado["etapa"] = 4
        await responder_usuario(
            telefone,
            "🍓 Deseja adicionar fruta ou noz? (R$ adicional)\n"
            "- Morango\n- Abacaxi\n- Ameixa\n- Nozes\nOu digite *não* para pular."
        )

    elif etapa == 4:
        dados["adicional"] = texto if texto.lower() != "não" else "Nenhum"
        estado["etapa"] = 5
        await responder_usuario(
            telefone,
            "📏 Escolha o tamanho do bolo:\n"
            "- Mini (15 pessoas)\n- Pequeno (30 pessoas)\n"
            "- Médio (50 pessoas)\n- Grande (80 pessoas)"
        )

    elif etapa == 5:
        dados["tamanho"] = texto
        dados["data"] = datetime.now().strftime("%Y-%m-%d")
        estado["etapa"] = 6
        await responder_usuario(
            telefone,
            "📦 Como você prefere receber?\n"
            "1️⃣ Retirar na loja\n"
            "2️⃣ Receber em casa"
        )


    elif etapa == 6:
        encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)

        if texto in ["1", "retirada", "retirar", "loja"]:
            estados_entrega[telefone] = {
                "etapa": "retirada",
                "dados": {
                    "encomenda_id": encomenda_id,
                    "data": dados["data"]
                },
                "nome": nome_cliente
            }
            return await processar_entrega(telefone, "retirada", estados_entrega[telefone])

        elif texto in ["2", "entregar", "entrega", "receber"]:
            estados_entrega[telefone] = {
                "etapa": 1,
                "dados": {
                    "encomenda_id": encomenda_id,
                    "data": dados["data"]
                },
                "nome": nome_cliente
            }
            await responder_usuario(
                telefone,
                "📍 Por favor, informe o endereço completo para entrega (Rua, número, bairro):"
            )
            return


        else:
            await responder_usuario(
                telefone,
                "Por favor, escolha:\n"
                "1️⃣ Retirar na loja\n"
                "2️⃣ Receber em casa"
            )



    elif etapa == "confirmar_pronta":
        dados["pronta_entrega"] = texto
        salvar_encomenda_sqlite(telefone, dados, nome_cliente)
        await responder_usuario(telefone, "✅ Pronta entrega registrada! 🎉")
        return "finalizar"

    elif etapa == "gourmet":
        dados["linha"] = estado["linha"]
        dados["gourmet"] = texto
        estado["etapa"] = 6
        await responder_usuario(
            telefone,
            "📆 Para qual data deseja o bolo?\n"
            "⚠️ *Precisa de 2 dias de antecedência.*\n\n"
            "Ou digite *pronta entrega* para ver sabores disponíveis hoje."
        )

    return None

async def processar_encomenda(telefone, texto, estado, nome_cliente):
    etapa = estado["etapa"]
    dados = estado["dados"]

    if etapa == 1:
        if texto in ["1", "normal", "personalizado"]:
            estado["linha"] = "normal"
            dados["linha"] = "normal"
            estado["etapa"] = 2

            estado["etapa"] = 2
            await responder_usuario(
                telefone,
                "🍰 *Monte seu bolo personalizado!*\n\n"
                "1️⃣ Escolha a massa:\n- Branca\n- Chocolate\n- Mesclada"
            )
        elif texto in ["2", "gourmet"]:
            estado["linha"] = "gourmet"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "✨ *Linha Gourmet:*\n"
                "- Bolo Inglês\n- Inglês Belga\n- Floresta Negra\n"
                "- Língua de Gato\n- Ninho com Morango\n"
                "- Nozes com Doce de Leite\n- Olho de Sogra\n- Red Velvet\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome do bolo desejado:"
            )
        elif texto in ["3", "p6", "redondo", "bolo redondo"]:
            estado["linha"] = "redondo"
            dados["linha"] = "redondo"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🍥 *Bolos Redondos P6 (serve 20 pessoas):*\n"
                "- P6 Língua de Gato de Chocolate\n"
                "- P6 Língua de Gato de Chocolate Branco\n"
                "- P6 Camafeu\n"
                "- P6 Naked Cake\n"
                "- P6 Red Velvet\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome do bolo desejado:"
            )
        elif texto in ["4", "torta", "tortas"]:
            estado["linha"] = "torta"
            dados["linha"] = "torta"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🥧 *Tortas (serve 16 pessoas):*\n"
                "- Torta Argentina\n- Torta Banoffee\n"
                "- Cheesecake Tradicional\n- Cheesecake Pistache\n"
                "- Citrus Pie\n- Torta Limão\n\n"
                "📷 Veja fotos e preços no cardápio: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o nome da torta desejada:"
            )

        elif texto in ["5", "pronta entrega"]:
            estado["linha"] = "pronta_entrega"
            estado["etapa"] = "confirmar_pronta"
            await responder_usuario(
                telefone,
                "📦 *Pronta entrega de hoje:*\n"
                "- B3 Mesclado com Brigadeiro e Ninho\n"
                "- B4 Mesclado com Brigadeiro e Ninho\n\n"
                "📝 Digite o nome do bolo desejado:"
            )

        else:
            await responder_usuario(
                telefone,
                "🎂 *Escolha uma linha de bolo para começar:*\n"
                "1️⃣ Montar bolo personalizado\n"
                "2️⃣ Linha Gourmet\n"
                "3️⃣ Bolos Redondos (P6)\n"
                "4️⃣ Tortas\n\n"
                "Digite o número ou nome da linha desejada."
            )

    elif etapa == 2:
        massas_validas = ["branca", "chocolate", "mesclada"]
        massa = texto.strip().lower()

        if massa not in massas_validas:
            await responder_usuario(
                telefone,
                "⚠️ Massa inválida. Escolha uma das opções:\n- Branca\n- Chocolate\n- Mesclada"
            )
            return

        dados["massa"] = massa.capitalize()
        estado["etapa"] = 3
        await responder_usuario(
            telefone,
            "🍫 *Escolha 1 recheio:*\n"
            "- Beijinho\n- Brigadeiro\n- Brigadeiro de Nutella\n"
            "- Brigadeiro Branco\n- Branco Gourmet\n- Branco de Ninho\n"
            "- Casadinho\n- Doce de Leite\n\n"
            "📌 *Escolha 1 mousse:*\n"
            "- Ninho ou Trufa Branca\n- Chocolate ou Trufa Preta\n\n"
            "📝 Envie os dois juntos no formato:\n"
            "`Brigadeiro + Ninho`\n\n"
        )

    elif etapa == 3:
        if "+" not in texto:
            await responder_usuario(telefone, "⚠️ Envie no formato: Brigadeiro + Ninho")
            return

        recheio, mousse = map(str.strip, texto.split("+", 1))
        dados["recheio"] = recheio
        dados["mousse"] = mousse
        estado["etapa"] = 4
        await responder_usuario(
            telefone,
            "🍓 Deseja adicionar fruta ou noz? (R$ adicional)\n"
            "- Morango\n- Abacaxi\n- Ameixa\n- Nozes\nOu digite *não* para pular."
        )

    elif etapa == 4:
        dados["adicional"] = texto if texto.lower() != "não" else "Nenhum"
        estado["etapa"] = 5
        await responder_usuario(
            telefone,
            "📏 Escolha o tamanho do bolo:\n"
            "- Mini (15 pessoas)\n- Pequeno (30 pessoas)\n"
            "- Médio (50 pessoas)\n- Grande (80 pessoas)"
        )

    elif etapa == 5:
        dados["tamanho"] = texto
        dados["data"] = datetime.now().strftime("%Y-%m-%d")
        estado["etapa"] = 6
        await responder_usuario(
            telefone,
            "📦 Como você prefere receber?\n"
            "1️⃣ Retirar na loja\n"
            "2️⃣ Receber em casa"
        )


    elif etapa == 6:
        if texto in ["1", "retirada", "retirar", "loja"]:
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)
            salvar_entrega(
                encomenda_id,
                tipo="retirada",
                data_agendada=dados["data"],
                status="Retirada na loja"
            )
            await responder_usuario(telefone, "✅ Encomenda registrada com sucesso 🎂")
            return "finalizar"

        elif texto in ["2", "entregar", "entrega", "receber"]:
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)
            estados_entrega[telefone] = {
                "etapa": 1,
                "dados": {
                    "encomenda_id": encomenda_id,
                    "data": dados["data"]
                },
                "nome": nome_cliente
            }
            await responder_usuario(
                telefone,
                "📍 Por favor, informe o endereço completo para entrega (Rua, número, bairro):"
            )
            return

        else:
            await responder_usuario(
                telefone,
                "Por favor, escolha:\n"
                "1️⃣ Retirar na loja\n"
                "2️⃣ Receber em casa"
            )



    elif etapa == "confirmar_pronta":
        dados["pronta_entrega"] = texto
        salvar_encomenda_sqlite(telefone, dados, nome_cliente)
        await responder_usuario(telefone, "✅ Pronta entrega registrada! 🎉")
        return "finalizar"

    elif etapa == "gourmet":
        dados["linha"] = estado["linha"]
        dados["gourmet"] = texto
        dados["data"] = datetime.now().strftime("%Y-%m-%d")
        estado["etapa"] = 6
        await responder_usuario(
            telefone,
            "📦 Como você prefere receber?\n"
            "1️⃣ Retirar na loja\n"
            "2️⃣ Receber em casa"
        )


    return None
