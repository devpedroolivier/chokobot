from __future__ import annotations

from typing import Awaitable, Callable

from app.application.service_registry import (
    get_customer_process_repository,
    get_delivery_gateway,
    get_order_gateway,
)
from app.observability import log_event
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido, _parse_hora, _valida_data
from app.utils.mensagens import responder_usuario

ResponderUsuarioFn = Callable[[str, str], Awaitable[bool]]

CESTAS_BOX_CATALOGO = {
    "1": {
        "nome": "BOX P CHOCOLATES",
        "preco": 99.90,
        "descricao": "2 trufas, 1 chokobom, 1 cake, 6 bombons, 1 tablete de chocolate",
        "serve": 1,
    },
    "2": {
        "nome": "BOX P CHOCOLATES (com Balão)",
        "preco": 119.90,
        "descricao": "2 trufas, 1 chokobom, 1 cake, 6 bombons, 1 tablete de chocolate, Balão Personalizado",
        "serve": 1,
    },
    "3": {
        "nome": "BOX M CHOCOLATES",
        "preco": 149.90,
        "descricao": "3 trufas, 2 chokobons, 2 cakes, 6 bombons, 1 tablete de chocolate",
        "serve": 2,
    },
    "4": {
        "nome": "BOX M CHOCOLATES BALÃO",
        "preco": 189.90,
        "descricao": "3 trufas, 2 chokobons, 2 cakes, 6 bombons, 1 tablete de chocolate, Balão Personalizado",
        "serve": 2,
    },
    "5": {
        "nome": "BOX M CAFÉ",
        "preco": 179.90,
        "descricao": "5 bombons, 1 tablete de chocolate, 1 pote cheesecake, 1 pão de queijo, 1 croissant, 1 suco natural, Bolachinhas, 1 cappuccino em pó",
        "serve": 2,
    },
    "6": {
        "nome": "BOX M CAFÉ BALÃO",
        "preco": 219.90,
        "descricao": "5 bombons, 1 tablete de chocolate, 1 pote cheesecake, 1 pão de queijo, 1 croissant, 1 suco natural, Bolachinhas, 1 cappuccino em pó, Balão Personalizado",
        "serve": 2,
    },
}


def _build_cesta_process_payload(dados: dict) -> dict:
    return {
        "categoria": "cesta_box",
        "cesta_nome": dados.get("cesta_nome"),
        "descricao": dados.get("cesta_descricao") or dados.get("cesta_nome") or "Cesta box",
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados.get("modo_recebimento"),
        "endereco": dados.get("endereco", ""),
        "valor_total": dados.get("cesta_preco", 0.0) + dados.get("taxa_entrega", 0.0),
        "pagamento": dados.get("pagamento", {}),
    }


def _sync_cesta_process(
    process_repository,
    *,
    phone: str,
    customer_id: int,
    stage: str,
    dados: dict,
    status: str = "active",
    order_id: int | None = None,
) -> None:
    process_repository.upsert_process(
        phone=phone,
        customer_id=customer_id,
        process_type="cesta_box_order",
        stage=stage,
        status=status,
        source="cesta_box",
        draft_payload=_build_cesta_process_payload(dados),
        order_id=order_id,
    )


def montar_menu_cestas() -> str:
    linhas = ["🎁 *Cestas Box Café ou Chocolate*\n"]
    for chave, info in CESTAS_BOX_CATALOGO.items():
        linhas.append(f"{chave}. {info['nome']} — R${info['preco']:.2f}")
    linhas.append("\n📝 Digite o *número da cesta* desejada:")
    return "\n".join(linhas)


async def montar_resumo_e_confirmar(
    telefone: str,
    estado: dict,
    dados: dict,
    *,
    responder_usuario_fn: ResponderUsuarioFn = responder_usuario,
) -> None:
    modo_txt = "🏪 Retirada na loja" if dados.get("modo_recebimento") == "retirada" else "🚚 Entrega em casa"
    endereco_txt = f"\n📍 Endereço: {dados.get('endereco', '')}" if dados.get("endereco") else ""
    preco_base = dados.get("cesta_preco", 0.0)
    taxa = dados.get("taxa_entrega", 0.0)
    total = preco_base + taxa

    taxa_txt = f"Taxa de entrega: R${taxa:.2f}\n" if taxa else ""
    resumo = (
        f"✅ *Resumo do seu pedido*\n\n"
        f"🎁 *Cesta*: {dados.get('cesta_nome')}\n"
        f"R${preco_base:.2f}\n\n"
        f"📋 *Detalhes*:\n{dados.get('cesta_descricao')}\n\n"
        f"📅 *Data*: {dados.get('data_entrega')}\n"
        f"⏰ *Horário*: {dados.get('horario_retirada')}\n"
        f"{modo_txt}{endereco_txt}\n\n"
        f"———\n"
        f"{taxa_txt}"
        f"*Total: R${total:.2f}*\n"
        f"———\n\n"
        f"Tudo correto?\n"
        f"1️⃣ Confirmar pedido\n"
        f"2️⃣ Corrigir"
    )

    await responder_usuario_fn(telefone, resumo)


async def salvar_pedido_cesta(
    telefone: str,
    estado: dict,
    dados: dict,
    nome_cliente: str,
    cliente_id: int,
    *,
    responder_usuario_fn: ResponderUsuarioFn = responder_usuario,
    order_gateway=None,
    delivery_gateway=None,
    customer_process_repository=None,
) -> None:
    order_gateway = order_gateway or get_order_gateway()
    delivery_gateway = delivery_gateway or get_delivery_gateway()
    process_repository = customer_process_repository or get_customer_process_repository()

    try:
        pedido_final = {
            "categoria": "cesta_box",
            "cesta_nome": dados.get("cesta_nome"),
            "cesta_preco": dados.get("cesta_preco"),
            "cesta_descricao": dados.get("cesta_descricao"),
            "data_entrega": dados.get("data_entrega"),
            "horario_retirada": dados.get("horario_retirada"),
            "modo_recebimento": dados.get("modo_recebimento"),
            "endereco": dados.get("endereco", ""),
            "valor_total": dados.get("cesta_preco", 0.0) + dados.get("taxa_entrega", 0.0),
            "pagamento": dados.get("pagamento", {}),
        }

        encomenda_id = order_gateway.create_order(
            phone=telefone,
            dados=pedido_final,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
        )

        if dados.get("modo_recebimento") == "entrega":
            delivery_gateway.create_delivery(
                encomenda_id=encomenda_id,
                tipo="cesta_box",
                endereco=dados.get("endereco"),
                data_agendada=dados.get("data_entrega"),
                status="agendada",
            )

        total = dados.get("cesta_preco", 0.0) + dados.get("taxa_entrega", 0.0)
        log_event("cesta_box_order_saved", telefone=telefone, encomenda_id=encomenda_id)
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="pedido_confirmado",
            dados=dados,
            status="converted",
            order_id=encomenda_id,
        )
        await responder_usuario_fn(
            telefone,
            f"✅ *Pedido confirmado com sucesso!* ✅\n"
            f"ID: #{encomenda_id}\n"
            f"Cesta: {dados.get('cesta_nome')}\n"
            f"Data: {dados.get('data_entrega')}\n"
            f"Horário: {dados.get('horario_retirada')}\n\n"
            f"💰 *Total: R${total:.2f}*\n\n"
            f"Obrigada por sua compra! 🎁\n"
            f"✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia",
        )
    except Exception as exc:
        log_event("cesta_box_order_save_failed", telefone=telefone, error_type=type(exc).__name__)
        await responder_usuario_fn(telefone, f"❌ Erro ao processar pedido: {str(exc)}")


async def process_cesta_box_flow(
    telefone: str,
    texto: str,
    estado: dict,
    nome_cliente: str,
    cliente_id: int,
    *,
    responder_usuario_fn: ResponderUsuarioFn = responder_usuario,
    order_gateway=None,
    delivery_gateway=None,
    customer_process_repository=None,
):
    etapa = estado.get("etapa", "selecao")
    dados = estado.setdefault("dados", {})
    process_repository = customer_process_repository or get_customer_process_repository()

    if etapa == "selecao":
        escolha = (texto or "").strip().lower()

        if escolha not in CESTAS_BOX_CATALOGO:
            await responder_usuario_fn(telefone, montar_menu_cestas())
            return None

        cesta_info = CESTAS_BOX_CATALOGO[escolha]
        dados["cesta_numero"] = escolha
        dados["cesta_nome"] = cesta_info["nome"]
        dados["cesta_preco"] = cesta_info["preco"]
        dados["cesta_descricao"] = cesta_info["descricao"]
        dados["cesta_serve"] = cesta_info["serve"]
        dados["categoria"] = "cesta_box"
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="coletando_dados",
            dados=dados,
        )

        estado["etapa"] = "data_entrega"
        await responder_usuario_fn(
            telefone,
            f"✅ Cesta selecionada: *{cesta_info['nome']}*\n"
            f"R${cesta_info['preco']:.2f}\n\n"
            f"📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):",
        )
        return None

    if etapa == "data_entrega":
        texto_limpo = (texto or "").strip()

        if not texto_limpo:
            await responder_usuario_fn(telefone, "⚠️ Por favor, informe uma data válida (DD/MM/AAAA).")
            return None

        if not _valida_data(texto_limpo):
            await responder_usuario_fn(telefone, "⚠️ Data inválida. Digite no formato DD/MM/AAAA.")
            return None

        dados["data_entrega"] = texto_limpo
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="coletando_dados",
            dados=dados,
        )
        estado["etapa"] = "hora_retirada"
        await responder_usuario_fn(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
        return None

    if etapa == "hora_retirada":
        if not _parse_hora(texto):
            await responder_usuario_fn(telefone, "⚠️ Horário inválido. Digite no formato HH:MM (ex: 14:30).")
            return None

        dados["horario_retirada"] = (texto or "").strip()
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="coletando_dados",
            dados=dados,
        )
        estado["etapa"] = "modo_recebimento"
        await responder_usuario_fn(
            telefone,
            "📍 Como você deseja receber?\n"
            "1️⃣ Retirada na loja\n"
            "2️⃣ Entrega em casa (taxa: R$10,00)",
        )
        return None

    if etapa == "modo_recebimento":
        modo = (texto or "").strip().lower()

        if modo in ["1", "retirada"]:
            dados["modo_recebimento"] = "retirada"
            dados["endereco"] = ""
            _sync_cesta_process(
                process_repository,
                phone=telefone,
                customer_id=cliente_id,
                stage="aguardando_confirmacao",
                dados=dados,
            )
            estado["etapa"] = "confirmar_pedido"
            await montar_resumo_e_confirmar(
                telefone,
                estado,
                dados,
                responder_usuario_fn=responder_usuario_fn,
            )
            return None

        if modo in ["2", "entrega"]:
            if not _horario_entrega_permitido(dados.get("horario_retirada")):
                estado["etapa"] = "hora_retirada"
                await responder_usuario_fn(
                    telefone,
                    f"🚚 As entregas são realizadas até as *{LIMITE_HORARIO_ENTREGA}*.\n"
                    f"Informe um horário até *{LIMITE_HORARIO_ENTREGA}* para entrega.",
                )
                return None

            dados["modo_recebimento"] = "entrega"
            dados["taxa_entrega"] = 10.0
            _sync_cesta_process(
                process_repository,
                phone=telefone,
                customer_id=cliente_id,
                stage="coletando_dados",
                dados=dados,
            )
            estado["etapa"] = "endereco"
            await responder_usuario_fn(
                telefone,
                "📍 Qual é o *endereço de entrega*? (logradouro, número, complemento)",
            )
            return None

        await responder_usuario_fn(
            telefone,
            "⚠️ Digite *1* para retirada ou *2* para entrega.",
        )
        return None

    if etapa == "endereco":
        endereco = (texto or "").strip()

        if not endereco:
            await responder_usuario_fn(telefone, "⚠️ Por favor, informe o endereço.")
            return None

        dados["endereco"] = endereco
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="aguardando_confirmacao",
            dados=dados,
        )
        estado["etapa"] = "confirmar_pedido"
        await montar_resumo_e_confirmar(
            telefone,
            estado,
            dados,
            responder_usuario_fn=responder_usuario_fn,
        )
        return None

    if etapa == "confirmar_pedido":
        resposta = (texto or "").strip().lower()

        if resposta in ["1", "sim", "confirmar"]:
            if "pagamento" not in dados:
                dados["pagamento"] = {}
                _sync_cesta_process(
                    process_repository,
                    phone=telefone,
                    customer_id=cliente_id,
                    stage="pagamento_pendente",
                    dados=dados,
                )
                await responder_usuario_fn(
                    telefone,
                    "💳 *Forma de pagamento*\n"
                    "1️⃣ PIX\n"
                    "2️⃣ Cartão (débito/crédito)\n"
                    "3️⃣ Dinheiro\n\n"
                    "Digite *1*, *2* ou *3*.",
                )
                estado["etapa"] = "pagamento_forma"
                return None

        elif resposta in ["2", "nao", "não", "corrigir"]:
            await responder_usuario_fn(telefone, "🔄 Vamos recomeçar...\n\n" + montar_menu_cestas())
            estado["etapa"] = "selecao"
            estado["dados"] = {}
            return None

        else:
            await responder_usuario_fn(
                telefone,
                "⚠️ Digite *1* para confirmar ou *2* para corrigir.",
            )
            return None

    if etapa == "pagamento_forma":
        escolha = (texto or "").strip()
        formas_pagamento = {
            "1": "PIX",
            "2": "Cartão",
            "3": "Dinheiro",
        }

        if escolha not in formas_pagamento:
            await responder_usuario_fn(
                telefone,
                "Não entendi.\n"
                "💳 *Forma de pagamento*\n"
                "1️⃣ PIX\n"
                "2️⃣ Cartão (débito/crédito)\n"
                "3️⃣ Dinheiro",
            )
            return None

        forma = formas_pagamento[escolha]
        dados["pagamento"]["forma"] = forma
        _sync_cesta_process(
            process_repository,
            phone=telefone,
            customer_id=cliente_id,
            stage="pagamento_pendente",
            dados=dados,
        )

        if forma == "Dinheiro":
            estado["etapa"] = "pagamento_troco"
            await responder_usuario_fn(
                telefone,
                "💸 Você escolheu *dinheiro*.\n"
                "Para facilitar, me diga: *troco para quanto?*\n"
                "Exemplos: 50, 100, 200.",
            )
            return None

        dados["pagamento"]["troco_para"] = None
        estado["etapa"] = "finalizar_venda"
        await responder_usuario_fn(telefone, f"✅ Pagamento registrado: *{forma}*")
        await salvar_pedido_cesta(
            telefone,
            estado,
            dados,
            nome_cliente,
            cliente_id,
            responder_usuario_fn=responder_usuario_fn,
            order_gateway=order_gateway,
            delivery_gateway=delivery_gateway,
            customer_process_repository=process_repository,
        )
        return "finalizar"

    if etapa == "pagamento_troco":
        valor = (texto or "").strip().replace(",", ".")
        try:
            troco = float(valor)
            if troco <= 0:
                raise ValueError()
        except Exception:
            await responder_usuario_fn(
                telefone,
                "Valor inválido. Informe apenas números. Exemplo: 50 ou 100.",
            )
            return None

        dados["pagamento"]["troco_para"] = troco
        estado["etapa"] = "finalizar_venda"
        await responder_usuario_fn(
            telefone,
            f"✅ Pagamento registrado: *Dinheiro* — troco para *R${troco:.2f}*",
        )
        await salvar_pedido_cesta(
            telefone,
            estado,
            dados,
            nome_cliente,
            cliente_id,
            responder_usuario_fn=responder_usuario_fn,
            order_gateway=order_gateway,
            delivery_gateway=delivery_gateway,
            customer_process_repository=process_repository,
        )
        return "finalizar"

    return None
