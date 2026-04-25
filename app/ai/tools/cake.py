"""Cake-domain helpers, validations, pricing and public cake tools.

create_cake_order / save_cake_order_draft_process ainda vivem em
``app/ai/tools/__init__.py`` porque dependem dos helpers de orquestração
(_persist_order_with_optional_bundle, _sync_ai_process,
_build_draft_confirmation_message). A próxima extração (Fase A.3) move
esses orchestration helpers para `_orchestration.py` e completa o
isolamento de cake.
"""
from __future__ import annotations

from typing import Tuple

from app.ai.tools._common import (
    _apply_card_installment_rule,
    _format_currency_brl,
    _is_missing_field,
    _join_option_values,
    _match_catalog_value,
    _match_closest,
    _normalize_payment_data,
    _normalizar_data_iso,
    _validate_cash_change_requirement,
    _validate_required_payment_data,
)
from app.application.service_registry import get_catalog_gateway  # noqa: F401  (re-exported)
from app.services.commercial_rules import DELIVERY_FEE_STANDARD
from app.services.encomendas_utils import (
    GOURMET_ALIASES,
    LIMITE_HORARIO_ENTREGA,
    REDONDOS_ALIASES,
    TORTAS_ALIASES,
    _horario_entrega_permitido,
    _linha_canonica,
    _normaliza_produto,
    _normaliza_tamanho,
)
from app.services.precos import (
    INGLES,
    KIT_FESTOU_PRECO,
    LINHA_SIMPLES,
    MESVERSARIO,
    REDONDOS_P6,
    TORTAS,
    TRADICIONAL_BASE,
    _norm,
    calcular_total,
)
from app.services.store_schedule import validate_service_schedule


# ============================================================
#  Constantes do domínio cake
# ============================================================

MASSAS_TRADICIONAIS = ("Branca", "Chocolate", "Mesclada")
MASSAS_VALIDAS = set(MASSAS_TRADICIONAIS)
MASSA_SINONIMOS = {
    "preta": "Chocolate",
    "massa preta": "Chocolate",
    "escura": "Chocolate",
    "massa escura": "Chocolate",
}

RECHEIOS_TRADICIONAIS = (
    "Beijinho",
    "Brigadeiro",
    "Brigadeiro de Nutella",
    "Brigadeiro Branco Gourmet",
    "Brigadeiro Branco de Ninho",
    "Casadinho",
    "Doce de Leite",
)
RECHEIOS_VALIDOS = set(RECHEIOS_TRADICIONAIS)

MOUSSES_TRADICIONAIS = ("Ninho", "Trufa Branca", "Chocolate", "Trufa Preta")
MOUSSES_VALIDOS = set(MOUSSES_TRADICIONAIS)

ADICIONAIS_TRADICIONAIS = ("Morango", "Ameixa", "Nozes", "Cereja", "Abacaxi")
TAMANHOS_TRADICIONAIS = ("B3", "B4", "B6", "B7")

MASSAS_MESVERSARIO = ("Branca", "Chocolate")
RECHEIOS_MESVERSARIO = (
    "Brigadeiro com Ninho",
    "Brigadeiro de Nutella com Ninho",
    "Brigadeiro e Beijinho",
    "Casadinho",
    "Brigadeiro Branco Gourmet com Ninho",
    "Brigadeiro Branco de Ninho com Ninho",
    "Beijinho com Ninho",
    "Doce de Leite e Brigadeiro",
    "Doce de Leite com Ninho",
)
TAMANHOS_MESVERSARIO = ("P4", "P6")

CAKE_OPTION_LABELS = {
    "massa": "massas",
    "tamanho": "tamanhos",
    "recheio": "recheios",
    "mousse": "mousses",
    "adicional": "adicionais",
}

CAKE_OPTION_VALUES = {
    ("tradicional", "massa"): MASSAS_TRADICIONAIS,
    ("tradicional", "tamanho"): TAMANHOS_TRADICIONAIS,
    ("tradicional", "recheio"): RECHEIOS_TRADICIONAIS,
    ("tradicional", "mousse"): MOUSSES_TRADICIONAIS,
    ("tradicional", "adicional"): ADICIONAIS_TRADICIONAIS,
    ("mesversario", "massa"): MASSAS_MESVERSARIO,
    ("mesversario", "tamanho"): TAMANHOS_MESVERSARIO,
    ("mesversario", "recheio"): RECHEIOS_MESVERSARIO,
    ("mesversario", "mousse"): ("Chocolate",),
}

TAMANHOS_BOLO = {"B3", "B4", "B6", "B7", "P4", "P6"}

LINHAS_VALIDAS = {"tradicional", "gourmet", "mesversario", "babycake", "torta", "simples"}

CATEGORIAS_VALIDAS = {"tradicional", "ingles", "redondo", "torta", "mesversario", "simples", "babycake"}

LINE_SIMPLE_FLAVORS = ("Chocolate", "Cenoura")
LINE_SIMPLE_COVERAGES = ("Vulcão", "Simples")

TAXA_ENTREGA_PADRAO = DELIVERY_FEE_STANDARD


# ============================================================
#  Helpers cake
# ============================================================

def _normalizar_massa(massa_raw: str | None) -> str | None:
    if not massa_raw:
        return massa_raw
    key = _norm(str(massa_raw))
    return MASSA_SINONIMOS.get(key, massa_raw)


def _normalize_cake_option_category(category: str) -> str:
    normalized = (category or "tradicional").strip().lower()
    aliases = {
        "tradicional": "tradicional",
        "bolo tradicional": "tradicional",
        "mesversario": "mesversario",
        "mesversário": "mesversario",
        "revelacao": "mesversario",
        "revelação": "mesversario",
    }
    return aliases.get(normalized, normalized)


def _normalize_cake_option_type(option_type: str) -> str:
    normalized = (option_type or "recheio").strip().lower()
    aliases = {
        "massa": "massa",
        "massas": "massa",
        "tamanho": "tamanho",
        "tamanhos": "tamanho",
        "recheio": "recheio",
        "recheios": "recheio",
        "mousse": "mousse",
        "mousses": "mousse",
        "adicional": "adicional",
        "adicionais": "adicional",
    }
    return aliases.get(normalized, normalized)


def _normalize_cake_pricing_category(category: str) -> str:
    normalized = _normalize_cake_option_category(category)
    aliases = {
        "gourmet": "gourmet",
        "gourmet ingles": "ingles",
        "gourmet inglês": "ingles",
        "ingles": "ingles",
        "inglês": "ingles",
        "redondo": "redondo",
        "redondo p6": "redondo",
        "gourmet redondo": "redondo",
        "gourmet redondo p6": "redondo",
        "torta": "torta",
        "simples": "simples",
        "linha simples": "simples",
        "bolo simples": "simples",
        "caseiro": "simples",
        "bolo caseiro": "simples",
        "caseirinho": "simples",
        "bolo caseirinho": "simples",
    }
    return aliases.get(normalized, normalized)


def _normalize_simple_cake_flavor(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _norm(value)
    aliases = {
        "chocolate": "Chocolate",
        "bolo de chocolate": "Chocolate",
        "cenoura": "Cenoura",
        "bolo de cenoura": "Cenoura",
    }
    canonical = aliases.get(normalized)
    if canonical:
        return canonical
    return _match_catalog_value(value, LINE_SIMPLE_FLAVORS)


def _normalize_simple_cake_coverage(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _norm(value)
    aliases = {
        "vulcao": "Vulcão",
        "vulcão": "Vulcão",
        "bolo vulcao": "Vulcão",
        "bolo vulcão": "Vulcão",
        "simples": "Simples",
        "tradicional": "Simples",
    }
    canonical = aliases.get(normalized)
    if canonical:
        return canonical
    return _match_catalog_value(value, LINE_SIMPLE_COVERAGES)


def _extract_simple_cake_details(*values: str | None) -> tuple[str | None, str | None]:
    joined = " ".join((value or "") for value in values if value)
    flavor = _normalize_simple_cake_flavor(joined)
    coverage = _normalize_simple_cake_coverage(joined)
    return flavor, coverage


# ============================================================
#  Pricing helpers
# ============================================================

def _build_cake_pricing_payload(
    *,
    category: str,
    tamanho: str | None,
    produto: str | None,
    adicional: str | None,
    cobertura: str | None,
    kit_festou: bool,
    quantidade: int,
) -> tuple[dict | None, str | None]:
    try:
        normalized_quantity = max(1, int(quantidade or 1))
    except (TypeError, ValueError):
        normalized_quantity = 1

    payload: dict = {
        "categoria": category,
        "kit_festou": kit_festou,
        "quantidade": normalized_quantity,
    }

    if category == "tradicional":
        normalized_size = _normaliza_tamanho(tamanho or "")
        if normalized_size not in TAMANHOS_TRADICIONAIS:
            return None, "Informe um tamanho valido da linha tradicional: B3, B4, B6 ou B7."
        payload["tamanho"] = normalized_size
        payload["fruta_ou_nozes"] = _match_closest(adicional or "", set(ADICIONAIS_TRADICIONAIS)) or adicional
        return payload, None

    if category == "mesversario":
        normalized_size = _normaliza_tamanho(tamanho or "")
        if normalized_size not in TAMANHOS_MESVERSARIO:
            return None, "Informe um tamanho valido do mesversario: P4 ou P6."
        payload["tamanho"] = normalized_size
        return payload, None

    if category == "ingles":
        matched = _match_catalog_value(produto, tuple(INGLES.keys()), aliases=GOURMET_ALIASES)
        if not matched:
            return None, "Informe um sabor valido do gourmet ingles."
        payload["produto"] = matched
        return payload, None

    if category == "redondo":
        matched = _match_catalog_value(produto, tuple(REDONDOS_P6.keys()), aliases=REDONDOS_ALIASES)
        if not matched:
            return None, "Informe um sabor valido do gourmet redondo P6."
        payload["produto"] = matched
        return payload, None

    if category == "torta":
        matched = _match_catalog_value(produto, tuple(TORTAS.keys()), aliases=TORTAS_ALIASES)
        if not matched:
            return None, "Informe um sabor valido de torta."
        payload["produto"] = matched
        return payload, None

    if category == "simples":
        flavor, inferred_cover = _extract_simple_cake_details(produto, cobertura)
        normalized_cover = _normalize_simple_cake_coverage(cobertura) or inferred_cover
        if not normalized_cover:
            return None, "Informe uma cobertura valida da linha simples: Vulcao ou Simples."
        payload["cobertura"] = normalized_cover
        payload["sabor"] = flavor or "Chocolate"
        return payload, None

    return None, "Categoria de bolo invalida para consulta de preco."


def _build_cake_pricing_overview(category: str) -> str:
    if category == "tradicional":
        lines = ["Precos canonicos da linha tradicional:"]
        for size in TAMANHOS_TRADICIONAIS:
            info = TRADICIONAL_BASE[size]
            lines.append(f"- {size} (ate {info['serve']} pessoas): {_format_currency_brl(info['preco'])}")
        lines.append("- Adicionais alteram o valor final: Morango, Ameixa, Nozes, Cereja e Abacaxi.")
        return "\n".join(lines)

    if category == "mesversario":
        lines = ["Precos canonicos do mesversario:"]
        for size in TAMANHOS_MESVERSARIO:
            info = MESVERSARIO[size]
            lines.append(f"- {size} (ate {info['serve']} pessoas): {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "ingles":
        lines = ["Precos canonicos do gourmet ingles (serve cerca de 10 pessoas):"]
        for name, info in INGLES.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "redondo":
        lines = ["Precos canonicos do gourmet redondo P6 (serve cerca de 20 pessoas):"]
        for name, info in REDONDOS_P6.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "torta":
        lines = ["Precos canonicos das tortas (serve 16 fatias):"]
        for name, info in TORTAS.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "simples":
        lines = ["Precos canonicos da linha simples (serve 8 fatias):"]
        for cover, price in LINHA_SIMPLES["coberturas"].items():
            lines.append(f"- {cover}: {_format_currency_brl(price)}")
        lines.append("- Sabores disponiveis: Chocolate e Cenoura.")
        return "\n".join(lines)

    if category == "gourmet":
        return (
            "A linha gourmet tem dois formatos com precos diferentes:\n"
            "- Gourmet ingles: serve cerca de 10 pessoas.\n"
            "- Gourmet redondo P6: serve cerca de 20 pessoas.\n"
            "Informe se o cliente quer ingles ou redondo P6 antes de citar o preco."
        )

    return "Categoria de bolo invalida para consulta de preco."


# ============================================================
#  Validations
# ============================================================

def _validar_campos_bolo(dados: dict) -> list[str]:
    """Valida campos do pedido e retorna lista de erros descritivos."""
    erros: list[str] = []
    linha = (dados.get("linha") or "").lower()
    categoria = (dados.get("categoria") or "").lower()

    if linha not in LINHAS_VALIDAS:
        erros.append(f"Linha '{dados.get('linha')}' invalida. Opcoes: {', '.join(sorted(LINHAS_VALIDAS))}.")

    if categoria not in CATEGORIAS_VALIDAS:
        erros.append(f"Categoria '{dados.get('categoria')}' invalida. Opcoes: {', '.join(sorted(CATEGORIAS_VALIDAS))}.")

    if categoria == "tradicional":
        tam = _normaliza_tamanho(dados.get("tamanho") or "")
        if tam not in TAMANHOS_BOLO:
            erros.append(f"Tamanho '{dados.get('tamanho')}' invalido. Use: B3, B4, B6 ou B7.")
        if not _match_closest(dados.get("massa") or "", MASSAS_VALIDAS):
            erros.append(f"Massa '{dados.get('massa')}' invalida. Opcoes: Branca, Chocolate ou Mesclada.")
        if not dados.get("recheio"):
            erros.append("Recheio e obrigatorio para linha tradicional.")
        if not dados.get("mousse") and (dados.get("recheio") or "").lower() != "casadinho":
            erros.append("Mousse e obrigatorio (exceto recheio Casadinho). Opcoes: Ninho, Trufa Branca, Chocolate, Trufa Preta.")

    elif categoria == "mesversario":
        tam = _normaliza_tamanho(dados.get("tamanho") or "")
        if tam not in {"P4", "P6"}:
            erros.append(f"Tamanho '{dados.get('tamanho')}' invalido para mesversario. Use: P4 ou P6.")

    elif categoria in ("ingles", "redondo", "torta"):
        if not dados.get("produto"):
            erros.append(f"Produto/sabor e obrigatorio para categoria {categoria}.")

    elif categoria == "simples":
        pass

    if dados.get("modo_recebimento") == "entrega":
        if not dados.get("endereco"):
            erros.append("Endereco e obrigatorio quando o modo de recebimento for entrega.")

    return erros


def _validate_required_cake_fields(dados: dict) -> list[str]:
    categoria = (dados.get("categoria") or "").strip().lower()
    missing: list[str] = []

    by_category = {
        "tradicional": ("massa", "recheio", "tamanho", "data_entrega", "modo_recebimento", "pagamento"),
        "ingles": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "redondo": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "torta": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "mesversario": ("tamanho", "data_entrega", "modo_recebimento", "pagamento"),
        "simples": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "babycake": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
    }
    required = by_category.get(categoria, ("data_entrega", "modo_recebimento", "pagamento"))
    for field_name in required:
        if _is_missing_field(dados.get(field_name)):
            missing.append(field_name)

    if categoria == "tradicional":
        recheio = str(dados.get("recheio") or "").strip().casefold()
        if recheio != "casadinho" and _is_missing_field(dados.get("mousse")):
            missing.append("mousse")

    if str(dados.get("modo_recebimento") or "").strip().lower() == "entrega" and _is_missing_field(dados.get("endereco")):
        missing.append("endereco")

    return sorted(set(missing))


def _calcular_preco_pedido(dados: dict) -> Tuple[float, int]:
    """Calcula preço a partir dos dados do CakeOrderSchema mapeados para calcular_total."""
    categoria = (dados.get("categoria") or "").lower()

    payload: dict = {
        "categoria": categoria,
        "kit_festou": dados.get("kit_festou", False),
        "quantidade": dados.get("quantidade", 1),
    }

    if categoria == "tradicional":
        payload["tamanho"] = _normaliza_tamanho(dados.get("tamanho") or "")
        payload["fruta_ou_nozes"] = dados.get("adicional")
    elif categoria in ("ingles", "redondo", "torta"):
        payload["produto"] = dados.get("produto")
    elif categoria == "mesversario":
        payload["tamanho"] = _normaliza_tamanho(dados.get("tamanho") or "")
    elif categoria == "simples":
        payload["cobertura"] = dados.get("cobertura") or _normalize_simple_cake_coverage(dados.get("produto")) or "Simples"
        payload["sabor"] = dados.get("produto")

    return calcular_total(payload)


# ============================================================
#  Builders (process payload, confirmation title, flavor line)
# ============================================================

def _build_cake_process_payload(dados: dict) -> dict:
    return {
        "categoria": dados.get("categoria"),
        "linha": dados.get("linha"),
        "produto": dados.get("produto"),
        "cobertura": dados.get("cobertura"),
        "tamanho": dados.get("tamanho"),
        "massa": dados.get("massa"),
        "recheio": dados.get("recheio"),
        "mousse": dados.get("mousse"),
        "adicional": dados.get("adicional"),
        "descricao": dados.get("descricao"),
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados.get("modo_recebimento"),
        "endereco": dados.get("endereco"),
        "pagamento": dados.get("pagamento"),
        "quantidade": dados.get("quantidade"),
        "valor_total": dados.get("valor_total"),
    }


def _build_cake_confirmation_title(dados: dict) -> str:
    categoria = (dados.get("categoria") or "").strip().lower()
    tamanho = (dados.get("tamanho") or "").strip()
    massa = (dados.get("massa") or "").strip()
    produto = (dados.get("produto") or "").strip()
    descricao = (dados.get("descricao") or "").strip()

    if categoria == "tradicional" and tamanho and massa:
        return f"Bolo {tamanho} de {massa.lower()}"
    if categoria == "mesversario" and tamanho:
        return f"Bolo mesversario {tamanho}"
    if categoria == "ingles" and produto:
        return f"Bolo gourmet ingles {produto}"
    if categoria == "redondo" and produto:
        return f"Bolo gourmet redondo {produto}"
    if categoria == "torta" and produto:
        return f"Torta {produto}"
    if categoria == "simples" and produto:
        coverage = (dados.get("cobertura") or "").strip()
        if coverage:
            return f"Bolo simples de {produto.lower()} ({coverage.lower()})"
        return f"Bolo simples de {produto.lower()}"
    return descricao or "Pedido"


def _build_cake_flavor_line(dados: dict) -> str:
    recheio = (dados.get("recheio") or "").strip()
    mousse = (dados.get("mousse") or "").strip()
    adicional = (dados.get("adicional") or "").strip()

    if not recheio and not mousse and not adicional:
        return ""

    base = recheio
    if mousse and recheio.casefold() != "casadinho":
        base = f"{recheio} com {mousse}" if recheio else mousse

    if adicional:
        if base:
            return f"Recheio: {base} e adicional de {adicional.lower()}"
        return f"Adicional: {adicional}"

    if base:
        return f"Recheio: {base}"
    return ""


# ============================================================
#  Order data preparation
# ============================================================

def _prepare_cake_order_data(order_details) -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["linha"] = _linha_canonica(dados.get("linha"))
    categoria = (dados.get("categoria") or "").lower()
    dados["categoria"] = categoria
    dados["pagamento"] = _normalize_payment_data(dados.get("pagamento"))
    payment_error = _validate_cash_change_requirement(dados.get("pagamento"))
    if payment_error:
        return None, payment_error

    schedule_error = validate_service_schedule(dados.get("data_entrega"), dados.get("horario_retirada"))
    if schedule_error:
        return None, schedule_error

    if dados.get("tamanho"):
        dados["tamanho"] = _normaliza_tamanho(dados["tamanho"])

    if dados.get("massa"):
        dados["massa"] = _normalizar_massa(dados.get("massa"))
        matched = _match_closest(dados["massa"], MASSAS_VALIDAS)
        if matched:
            dados["massa"] = matched

    if dados.get("produto") and dados["linha"] in ("gourmet", "torta"):
        normalizado = _normaliza_produto(
            "torta" if categoria == "torta" else ("redondo" if categoria == "redondo" else "gourmet"),
            dados["produto"],
        )
        if normalizado:
            dados["produto"] = normalizado

    if categoria == "simples":
        inferred_flavor, inferred_coverage = _extract_simple_cake_details(
            dados.get("produto"),
            dados.get("cobertura"),
            dados.get("descricao"),
        )
        if inferred_flavor:
            dados["produto"] = inferred_flavor
        if inferred_coverage:
            dados["cobertura"] = inferred_coverage

    if dados["modo_recebimento"] == "entrega" and not _horario_entrega_permitido(dados.get("horario_retirada")):
        return None, (
            f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
            "Ajuste o horario ou altere para retirada."
        )

    erros = _validar_campos_bolo(dados)
    if erros:
        return None, "Erro de validacao:\n- " + "\n- ".join(erros)

    payment_error = _validate_required_payment_data(dados.get("pagamento"))
    if payment_error:
        return None, payment_error

    missing_required = _validate_required_cake_fields(dados)
    if missing_required:
        return None, "Campos obrigatorios pendentes: " + ", ".join(missing_required) + "."

    try:
        valor_total, serve_pessoas = _calcular_preco_pedido(dados)
        if dados["modo_recebimento"] == "entrega":
            valor_total += dados.get("taxa_entrega", 0) or TAXA_ENTREGA_PADRAO
        dados["valor_total"] = valor_total
        dados["serve_pessoas"] = serve_pessoas
    except Exception:
        return None, "Nao consegui calcular o valor total com os dados informados. Revise os campos do pedido."

    if float(dados.get("valor_total") or 0) <= 0:
        return None, "Valor total invalido. Revise os itens para gerar um total maior que R$0,00."

    dados["pagamento"] = _apply_card_installment_rule(
        dados.get("pagamento"),
        float(dados.get("valor_total") or 0),
    )

    if dados["modo_recebimento"] == "entrega" and dados.get("taxa_entrega", 0) == 0:
        dados["taxa_entrega"] = TAXA_ENTREGA_PADRAO

    dados["data_entrega"] = _normalizar_data_iso(dados["data_entrega"])
    return dados, None


# ============================================================
#  Public tools (chamadas pelos agentes da IA)
# ============================================================

def get_cake_pricing(
    category: str = "tradicional",
    tamanho: str | None = None,
    produto: str | None = None,
    adicional: str | None = None,
    cobertura: str | None = None,
    kit_festou: bool = False,
    quantidade: int = 1,
) -> str:
    """Retorna precos canonicos de bolos e tortas a partir da base estruturada do sistema."""
    normalized_category = _normalize_cake_pricing_category(category)
    try:
        normalized_quantity = max(1, int(quantidade or 1))
    except (TypeError, ValueError):
        normalized_quantity = 1

    if (
        not tamanho
        and not produto
        and not adicional
        and not cobertura
        and not kit_festou
        and normalized_quantity == 1
    ):
        return _build_cake_pricing_overview(normalized_category)

    payload, error = _build_cake_pricing_payload(
        category=normalized_category,
        tamanho=tamanho,
        produto=produto,
        adicional=adicional,
        cobertura=cobertura,
        kit_festou=kit_festou,
        quantidade=normalized_quantity,
    )
    if error:
        return error
    assert payload is not None

    total_price, serve_people = calcular_total(payload)
    unit_payload = dict(payload)
    unit_payload["quantidade"] = 1
    unit_price, _ = calcular_total(unit_payload)

    description = ""
    if normalized_category == "tradicional":
        description = f"Bolo tradicional {payload['tamanho']}"
        if adicional:
            matched_additional = _match_closest(adicional, set(ADICIONAIS_TRADICIONAIS)) or adicional
            description += f" com adicional {matched_additional}"
    elif normalized_category == "mesversario":
        description = f"Bolo mesversario {payload['tamanho']}"
    elif normalized_category == "ingles":
        description = f"Gourmet ingles {payload['produto']}"
    elif normalized_category == "redondo":
        description = f"Gourmet redondo P6 {payload['produto']}"
    elif normalized_category == "torta":
        description = f"Torta {payload['produto']}"
    elif normalized_category == "simples":
        flavor_label = payload.get("sabor") or "Chocolate"
        description = f"Bolo simples de {str(flavor_label).lower()} com cobertura {payload['cobertura']}"

    lines = [
        "Preco canonico consultado no sistema:",
        f"- Item: {description}",
        f"- Valor unitario: {_format_currency_brl(unit_price)}",
    ]
    if serve_people:
        lines.append(f"- Serve aproximadamente: {serve_people} pessoas")
    if kit_festou:
        lines.append(f"- Kit Festou incluido: +{_format_currency_brl(KIT_FESTOU_PRECO)} por unidade")
    if normalized_quantity > 1:
        lines.append(f"- Quantidade: {normalized_quantity}")
        lines.append(f"- Total calculado: {_format_currency_brl(total_price)}")
    else:
        lines.append(f"- Total calculado: {_format_currency_brl(total_price)}")
    lines.append("Use este valor como referencia oficial e nao invente preco fora deste retorno.")
    return "\n".join(lines)


def get_cake_options(category: str = "tradicional", option_type: str = "recheio") -> str:
    """Retorna a lista canonica de opcoes de bolo em formato pronto para resposta ao cliente."""
    normalized_category = _normalize_cake_option_category(category)
    normalized_option_type = _normalize_cake_option_type(option_type)
    values = CAKE_OPTION_VALUES.get((normalized_category, normalized_option_type))

    if not values:
        return (
            "Nao encontrei opcoes cadastradas para "
            f"{normalized_option_type} na categoria {normalized_category}."
        )

    label = CAKE_OPTION_LABELS.get(normalized_option_type, normalized_option_type)
    joined_values = _join_option_values(values)

    if normalized_category == "tradicional":
        if normalized_option_type == "recheio":
            return f"Temos estes recheios: {joined_values}. Se escolher Casadinho, nao precisa de mousse."
        if normalized_option_type == "mousse":
            return f"Temos estes mousses: {joined_values}."
        if normalized_option_type == "adicional":
            return f"Temos estes adicionais: {joined_values}."
        if normalized_option_type == "massa":
            return f"Temos estas massas: {joined_values}."
        if normalized_option_type == "tamanho":
            return f"Os tamanhos disponiveis para bolo tradicional sao: {joined_values}."

    if normalized_category == "mesversario":
        if normalized_option_type == "recheio":
            return f"Temos estes recheios para mesversario: {joined_values}."
        if normalized_option_type == "mousse":
            return "No mesversario, a troca opcional de mousse disponivel e Chocolate."
        if normalized_option_type == "massa":
            return f"As massas disponiveis para mesversario sao: {joined_values}."
        if normalized_option_type == "tamanho":
            return f"Os tamanhos disponiveis para mesversario sao: {joined_values}."

    return f"Temos estes {label}: {joined_values}."
