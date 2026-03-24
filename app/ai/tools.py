from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.application.service_registry import (
    get_attention_gateway,
    get_catalog_gateway,
    get_customer_process_repository,
    get_delivery_gateway,
    get_order_gateway,
)
from app.db.database import get_connection
from app.security import ai_learning_enabled, security_audit
from app.services.encomendas_utils import (
    LIMITE_HORARIO_ENTREGA,
    _horario_entrega_permitido,
    _linha_canonica,
    _normaliza_tamanho,
    _normaliza_produto,
)
from app.services.precos import (
    DOCES_UNITARIOS,
    DOCES_ALIASES,
    KIT_FESTOU_PRECO,
    calcular_total,
    _canonical_doce,
    _norm,
)

# ============================================================
#  Constantes de validação
# ============================================================

MASSAS_TRADICIONAIS = ("Branca", "Chocolate", "Mesclada")
MASSAS_VALIDAS = set(MASSAS_TRADICIONAIS)

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

TAXA_ENTREGA_PADRAO = 10.0


# ============================================================
#  Helpers
# ============================================================

def _normalizar_data_iso(data_str: str) -> str:
    """Converte DD/MM/YYYY → YYYY-MM-DD.  Se já estiver em ISO, retorna como está."""
    try:
        dt = datetime.strptime(data_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return data_str


def _match_closest(valor: str, validos: set[str]) -> str | None:
    """Busca case-insensitive em um conjunto de valores válidos."""
    if not valor:
        return None
    v = valor.strip()
    for valid in validos:
        if v.lower() == valid.lower():
            return valid
    return None


def _join_option_values(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" e {values[-1]}"


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


def _validar_campos_bolo(dados: dict) -> list[str]:
    """Valida campos do pedido e retorna lista de erros descritivos."""
    erros: list[str] = []
    linha = (dados.get("linha") or "").lower()
    categoria = (dados.get("categoria") or "").lower()

    if linha not in LINHAS_VALIDAS:
        erros.append(f"Linha '{dados.get('linha')}' invalida. Opcoes: {', '.join(sorted(LINHAS_VALIDAS))}.")

    if categoria not in CATEGORIAS_VALIDAS:
        erros.append(f"Categoria '{dados.get('categoria')}' invalida. Opcoes: {', '.join(sorted(CATEGORIAS_VALIDAS))}.")

    # --- Tradicional: precisa de tamanho, massa, recheio, mousse ---
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

    # --- Mesversário: precisa de tamanho P4/P6 ---
    elif categoria == "mesversario":
        tam = _normaliza_tamanho(dados.get("tamanho") or "")
        if tam not in {"P4", "P6"}:
            erros.append(f"Tamanho '{dados.get('tamanho')}' invalido para mesversario. Use: P4 ou P6.")

    # --- Gourmet / Torta: precisa de produto ---
    elif categoria in ("ingles", "redondo", "torta"):
        if not dados.get("produto"):
            erros.append(f"Produto/sabor e obrigatorio para categoria {categoria}.")

    # --- Simples: precisa de produto (sabor+cobertura na descricao) ---
    elif categoria == "simples":
        pass  # descricao cobre

    # --- Entrega: precisa de endereço ---
    if dados.get("modo_recebimento") == "entrega":
        if not dados.get("endereco"):
            erros.append("Endereco e obrigatorio quando o modo de recebimento for entrega.")

    return erros


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
        payload["cobertura"] = dados.get("produto") or "Simples"

    return calcular_total(payload)


def _build_cake_process_payload(dados: dict) -> dict:
    return {
        "categoria": dados.get("categoria"),
        "linha": dados.get("linha"),
        "produto": dados.get("produto"),
        "descricao": dados.get("descricao"),
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados.get("modo_recebimento"),
        "endereco": dados.get("endereco"),
        "pagamento": dados.get("pagamento"),
        "quantidade": dados.get("quantidade"),
        "valor_total": dados.get("valor_total"),
    }


def _build_sweet_process_payload(
    *,
    data_entrega: str,
    horario_retirada: str | None,
    modo_recebimento: str,
    endereco: str | None,
    pagamento: dict,
    itens_validados: list[dict],
    valor_total: float,
) -> dict:
    return {
        "categoria": "doces",
        "descricao": "Doces avulsos",
        "itens": [f"{item['nome']} x{item['qtd']}" for item in itens_validados],
        "data_entrega": data_entrega,
        "horario_retirada": horario_retirada,
        "modo_recebimento": modo_recebimento,
        "endereco": endereco,
        "pagamento": pagamento,
        "valor_total": valor_total,
    }


def _sync_ai_process(
    *,
    phone: str,
    customer_id: int,
    process_type: str,
    stage: str,
    status: str,
    draft_payload: dict,
    source: str,
    order_id: int | None = None,
) -> None:
    get_customer_process_repository().upsert_process(
        phone=phone,
        customer_id=customer_id,
        process_type=process_type,
        stage=stage,
        status=status,
        source=source,
        draft_payload=draft_payload,
        order_id=order_id,
    )


def _prepare_cake_order_data(order_details: "CakeOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["linha"] = _linha_canonica(dados.get("linha"))
    categoria = (dados.get("categoria") or "").lower()
    dados["categoria"] = categoria

    if dados.get("tamanho"):
        dados["tamanho"] = _normaliza_tamanho(dados["tamanho"])

    if dados.get("massa"):
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

    if dados["modo_recebimento"] == "entrega" and not _horario_entrega_permitido(dados.get("horario_retirada")):
        return None, (
            f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
            "Ajuste o horario ou altere para retirada."
        )

    erros = _validar_campos_bolo(dados)
    if erros:
        return None, "Erro de validacao:\n- " + "\n- ".join(erros)

    try:
        valor_total, serve_pessoas = _calcular_preco_pedido(dados)
        if dados["modo_recebimento"] == "entrega":
            valor_total += dados.get("taxa_entrega", 0) or TAXA_ENTREGA_PADRAO
        dados["valor_total"] = valor_total
        dados["serve_pessoas"] = serve_pessoas
    except Exception:
        dados["valor_total"] = 0
        dados["serve_pessoas"] = 0

    if dados["modo_recebimento"] == "entrega" and dados.get("taxa_entrega", 0) == 0:
        dados["taxa_entrega"] = TAXA_ENTREGA_PADRAO

    dados["data_entrega"] = _normalizar_data_iso(dados["data_entrega"])
    return dados, None


def _prepare_sweet_order_data(order_details: "SweetOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    itens_validados: List[Dict] = []
    total_doces = 0.0
    erros: list[str] = []

    for item in dados.get("itens", []):
        nome_raw = item.get("nome", "")
        qtd = item.get("quantidade", 1)

        nome_canonico = _canonical_doce(nome_raw)
        if not nome_canonico:
            erros.append(f"Doce nao reconhecido: '{nome_raw}'. Verifique o nome no cardapio.")
            continue

        preco_unit = DOCES_UNITARIOS[nome_canonico]
        preco_total = round(preco_unit * qtd, 2)
        total_doces += preco_total

        itens_validados.append(
            {
                "nome": nome_canonico,
                "qtd": qtd,
                "preco": preco_total,
                "unit": preco_unit,
            }
        )

    if erros:
        return None, "Erro de validacao:\n- " + "\n- ".join(erros)

    if not itens_validados:
        return None, "Nenhum doce valido foi informado."

    if dados["modo_recebimento"] == "entrega":
        if not dados.get("endereco"):
            return None, "Endereco e obrigatorio quando o modo de recebimento for entrega."
        if not _horario_entrega_permitido(dados.get("horario_retirada")):
            return None, (
                f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
                "Ajuste o horario ou altere para retirada."
            )

    taxa_entrega = TAXA_ENTREGA_PADRAO if dados["modo_recebimento"] == "entrega" else 0.0
    valor_final = round(total_doces + taxa_entrega, 2)
    data_iso = _normalizar_data_iso(dados["data_entrega"])
    desc_itens = ", ".join(f"{it['nome']} x{it['qtd']}" for it in itens_validados)
    order_data = {
        "categoria": "doces",
        "linha": "doces",
        "descricao": f"Doces Avulsos: {desc_itens}",
        "data_entrega": data_iso,
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados["modo_recebimento"],
        "valor_total": valor_final,
        "quantidade": 1,
        "pagamento": dados.get("pagamento", {}),
        "taxa_entrega": taxa_entrega,
        "endereco": dados.get("endereco"),
    }
    return {
        "dados": dados,
        "itens_validados": itens_validados,
        "total_doces": total_doces,
        "taxa_entrega": taxa_entrega,
        "valor_final": valor_final,
        "data_iso": data_iso,
        "desc_itens": desc_itens,
        "order_data": order_data,
    }, None


# ============================================================
#  Schemas
# ============================================================

class PagamentoSchema(BaseModel):
    forma: Literal["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"] = Field(
        ..., description="Forma de pagamento escolhida"
    )
    troco_para: Optional[float] = Field(None, description="Valor para troco, se a forma for Dinheiro")


class CakeOrderSchema(BaseModel):
    linha: str = Field(..., description="Linha do bolo. Ex: tradicional, gourmet, mesversario, babycake, torta, simples")
    categoria: str = Field(..., description="Categoria derivada da linha. Ex: tradicional, ingles, redondo, torta, mesversario, simples")
    produto: Optional[str] = Field(None, description="Nome do produto/sabor (obrigatorio para gourmet, torta, simples)")
    tamanho: Optional[str] = Field(None, description="Tamanho: B3, B4, B6, B7, P4 ou P6")
    massa: Optional[str] = Field(None, description="Massa: Branca, Chocolate ou Mesclada (so para tradicional)")
    recheio: Optional[str] = Field(None, description="Recheio principal (so para tradicional/mesversario)")
    mousse: Optional[str] = Field(None, description="Mousse (so para tradicional, exceto recheio Casadinho)")
    adicional: Optional[str] = Field(None, description="Fruta ou nozes adicionais (so para tradicional)")
    descricao: str = Field(..., description="Descricao completa do bolo para o painel")
    kit_festou: bool = Field(False, description="Se adicionou kit festou (+R$35)")
    quantidade: int = Field(1, description="Quantidade do item")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo (obrigatorio se entrega)")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


class SweetItemSchema(BaseModel):
    nome: str = Field(..., description="Nome do doce. Ex: Brigadeiro Escama, Bombom Camafeu")
    quantidade: int = Field(..., description="Quantidade do doce")


class SweetOrderSchema(BaseModel):
    itens: List[SweetItemSchema] = Field(..., description="Lista de doces com nome e quantidade")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo (obrigatorio se entrega)")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


# ============================================================
#  Tools
# ============================================================

def get_menu(category: str = "todas") -> str:
    """Retorna o cardapio completo ou filtrado entre pronta entrega e encomendas."""
    return get_catalog_gateway().get_menu(category)


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


def get_learnings() -> str:
    """Lê as instruções e regras aprendidas previamente pela IA."""
    return get_catalog_gateway().get_learnings()


def save_learning(aprendizado: str) -> str:
    """Salva uma nova regra de negócio, preferência do cliente ou correção aprendida para consultas futuras."""
    if not ai_learning_enabled():
        security_audit("ai_learning_blocked")
        return "Aprendizado persistente desativado neste ambiente."
    return get_catalog_gateway().save_learning(aprendizado)


def escalate_to_human(telefone: str, motivo: str):
    """Aciona o atendimento humano, pausando o bot para esse telefone."""
    return get_attention_gateway().activate_human_handoff(telefone=telefone, motivo=motivo)


def create_cake_order(telefone: str, nome_cliente: str, cliente_id: int, order_details: CakeOrderSchema) -> str:
    """Valida, calcula preço e salva o pedido de bolo no banco de dados."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    dados, error = _prepare_cake_order_data(order_details)
    if error:
        return error
    assert dados is not None

    # --- Salvar pedido ---
    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    # --- Salvar entrega ---
    if dados["modo_recebimento"] == "entrega":
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="entrega",
            data_agendada=dados["data_entrega"],
            status="pendente",
            endereco=dados.get("endereco"),
        )
    else:
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=dados["data_entrega"],
            status="Retirar na loja",
        )

    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cake_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_cake_order",
        draft_payload=_build_cake_process_payload(dados),
        order_id=encomenda_id,
    )

    preco_txt = f" | Valor: R${dados['valor_total']:.2f}" if dados.get("valor_total") else ""
    return f"Pedido salvo com sucesso! ID da Encomenda: {encomenda_id}{preco_txt}"


def create_sweet_order(telefone: str, nome_cliente: str, cliente_id: int, order_details: SweetOrderSchema) -> str:
    """Valida, calcula preço e salva o pedido de doces avulsos no banco de dados."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    prepared, error = _prepare_sweet_order_data(order_details)
    if error:
        return error
    assert prepared is not None
    dados = prepared["dados"]
    itens_validados = prepared["itens_validados"]
    total_doces = prepared["total_doces"]
    taxa_entrega = prepared["taxa_entrega"]
    valor_final = prepared["valor_final"]
    data_iso = prepared["data_iso"]
    desc_itens = prepared["desc_itens"]
    order_data = prepared["order_data"]

    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=order_data,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    # --- Salvar itens na tabela encomenda_doces ---
    try:
        conn = get_connection()
        cur = conn.cursor()
        for it in itens_validados:
            cur.execute(
                "INSERT INTO encomenda_doces (encomenda_id, nome, qtd, preco, unit) VALUES (?, ?, ?, ?, ?)",
                (encomenda_id, it["nome"], it["qtd"], it["preco"], it["unit"]),
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"⚠️ Erro ao salvar itens de doces: {exc}")

    # --- Salvar entrega ---
    if dados["modo_recebimento"] == "entrega":
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="entrega",
            data_agendada=data_iso,
            status="pendente",
            endereco=dados.get("endereco"),
        )
    else:
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=data_iso,
            status="Retirar na loja",
        )

    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_sweet_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_sweet_order",
        draft_payload=_build_sweet_process_payload(
            data_entrega=data_iso,
            horario_retirada=dados.get("horario_retirada"),
            modo_recebimento=dados["modo_recebimento"],
            endereco=dados.get("endereco"),
            pagamento=dados.get("pagamento", {}),
            itens_validados=itens_validados,
            valor_total=valor_final,
        ),
        order_id=encomenda_id,
    )

    return (
        f"Pedido de doces salvo com sucesso! ID: {encomenda_id}\n"
        f"Itens: {desc_itens}\n"
        f"Total doces: R${total_doces:.2f}\n"
        + (f"Taxa entrega: R${taxa_entrega:.2f}\n" if taxa_entrega else "")
        + f"Total final: R${valor_final:.2f}"
    )


def save_cake_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: CakeOrderSchema,
) -> str:
    dados, error = _prepare_cake_order_data(order_details)
    if error:
        return error
    assert dados is not None
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cake_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_cake_order",
        draft_payload=_build_cake_process_payload(dados),
    )
    preco_txt = f" Valor estimado: R${dados['valor_total']:.2f}." if dados.get("valor_total") else ""
    return (
        "Pedido em rascunho salvo no atendimento e aguardando confirmacao final explicita do cliente."
        f"{preco_txt} Peca a confirmacao antes de concluir."
    )


def save_sweet_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: SweetOrderSchema,
) -> str:
    prepared, error = _prepare_sweet_order_data(order_details)
    if error:
        return error
    assert prepared is not None
    dados = prepared["dados"]
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_sweet_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_sweet_order",
        draft_payload=_build_sweet_process_payload(
            data_entrega=prepared["data_iso"],
            horario_retirada=dados.get("horario_retirada"),
            modo_recebimento=dados["modo_recebimento"],
            endereco=dados.get("endereco"),
            pagamento=dados.get("pagamento", {}),
            itens_validados=prepared["itens_validados"],
            valor_total=prepared["valor_final"],
        ),
    )
    return (
        "Pedido de doces em rascunho salvo no atendimento e aguardando confirmacao final explicita do cliente. "
        "Peca a confirmacao antes de concluir."
    )
