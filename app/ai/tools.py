from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

from app.services.precos import DOCES_UNITARIOS, KIT_FESTOU_PRECO, TRADICIONAL_BASE

class PagamentoSchema(BaseModel):
    forma: Literal["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"] = Field(..., description="Forma de pagamento escolhida")
    troco_para: Optional[float] = Field(None, description="Valor para troco, se a forma for Dinheiro")

class CakeOrderSchema(BaseModel):
    linha: str = Field(..., description="Linha do bolo. Ex: normal, gourmet, mesversario, babycake, torta, simples")
    categoria: str = Field(..., description="Categoria derivada da linha. Ex: tradicional, ingles, redondo, torta")
    produto: Optional[str] = Field(None, description="Nome do produto específico (para gourmet, tortas, etc)")
    tamanho: Optional[str] = Field(None, description="Tamanho do bolo. Ex: B3, B4, P4, P6")
    massa: Optional[str] = Field(None, description="Sabor da massa")
    recheio: Optional[str] = Field(None, description="Sabor do recheio principal")
    mousse: Optional[str] = Field(None, description="Sabor do mousse/segundo recheio")
    adicional: Optional[str] = Field(None, description="Fruta ou nozes adicionais")
    descricao: str = Field(..., description="Descrição completa do bolo para o painel")
    kit_festou: bool = Field(False, description="Se o cliente adicionou o kit festou (+25 brigadeiros e balão)")
    quantidade: int = Field(1, description="Quantidade do item")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horário de retirada/entrega no formato HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="Se o cliente vai retirar ou pedir entrega")
    endereco: Optional[str] = Field(None, description="Endereço completo para entrega, obrigatório se modo for entrega")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega (0 se retirada)")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")

def _load_menu_text() -> str:
    menu_path = Path("app/ai/knowledge/menus.md")
    return menu_path.read_text(encoding="utf-8")


def _normalize_category(category: str | None) -> str:
    raw = (category or "todas").strip().lower()
    aliases = {
        "todas": "todas",
        "geral": "todas",
        "menu": "todas",
        "completo": "todas",
        "pronta entrega": "pronta_entrega",
        "pronta_entrega": "pronta_entrega",
        "pronta": "pronta_entrega",
        "vitrine": "pronta_entrega",
        "cafeteria": "pronta_entrega",
        "doces": "pronta_entrega",
        "avulsos": "pronta_entrega",
        "encomenda": "encomendas",
        "encomendas": "encomendas",
        "personalizado": "encomendas",
        "personalizados": "encomendas",
        "bolo personalizado": "encomendas",
        "bolos": "encomendas",
        "tortas": "encomendas",
        "cestas": "encomendas",
    }
    return aliases.get(raw, "todas")


def _build_ready_delivery_summary() -> str:
    b3 = TRADICIONAL_BASE["B3"]
    b4 = TRADICIONAL_BASE["B4"]
    doces = [
        "Brigadeiro Escama",
        "Brigadeiro De Ninho",
        "Casadinho",
        "Brigadeiro Belga Callebaut Ao Leite",
        "Chokobom",
        "Pirulito De Chocolate",
    ]
    doces_lines = "\n".join(
        f"- {nome}: R${DOCES_UNITARIOS[nome]:.2f}" for nome in doces
    )
    return (
        "PRONTA ENTREGA\n"
        "- Mostrar apenas itens prontos do dia, cafeteria, doces avulsos e bolo pronta entrega.\n"
        "- Nao misturar com encomendas personalizadas.\n\n"
        "BOLOS PRONTA ENTREGA DO FLUXO INTERNO\n"
        f"- B3 (ate {b3['serve']} pessoas): R${b3['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
        f"- B4 (ate {b4['serve']} pessoas): R${b4['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
        f"- Kit Festou opcional: +R${KIT_FESTOU_PRECO:.2f}\n"
        "- Regra atual: pronta entrega segue como retirada na loja no fluxo interno.\n\n"
        "CAFETERIA E VITRINE\n"
        "- Cardapio Cafeteria: http://bit.ly/44ZlKlZ\n"
        "- A vitrine pode variar no dia.\n\n"
        "DOCES AVULSOS\n"
        "- Cardapio de Doces: https://bit.ly/doceschoko\n"
        f"{doces_lines}\n"
    )


def _slice_section(text: str, start: str, end: str | None = None) -> str:
    start_idx = text.find(start)
    if start_idx == -1:
        return ""
    end_idx = text.find(end, start_idx) if end else -1
    if end_idx == -1:
        return text[start_idx:].strip()
    return text[start_idx:end_idx].strip()


def get_menu(category: str = "todas") -> str:
    """Retorna o cardapio completo ou filtrado entre pronta entrega e encomendas."""
    try:
        text = _load_menu_text()
        normalized = _normalize_category(category)

        if normalized == "pronta_entrega":
            return _build_ready_delivery_summary()

        if normalized == "encomendas":
            encomendas = _slice_section(text, "## Encomendas", "## Entregas e Pagamento")
            pagamentos = _slice_section(text, "## Entregas e Pagamento")
            return f"{encomendas}\n\n{pagamentos}".strip()

        return text
    except Exception as e:
        return "Erro ao carregar cardapio: " + str(e)

def get_learnings() -> str:
    """Lê as instruções e regras aprendidas previamente pela IA."""
    try:
        with open("app/ai/knowledge/learnings.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def save_learning(aprendizado: str) -> str:
    """Salva uma nova regra de negócio, preferência do cliente ou correção aprendida para consultas futuras."""
    with open("app/ai/knowledge/learnings.md", "a", encoding="utf-8") as f:
        f.write(f"- {aprendizado}\n")
    return "Aprendizado salvo com sucesso! Vou me lembrar disso."

def escalate_to_human(telefone: str, motivo: str):
    """Aciona o atendimento humano, pausando o bot para esse telefone."""
    from app.services.estados import estados_atendimento
    import datetime
    
    estados_atendimento[telefone] = {
        "humano": True,
        "inicio": datetime.datetime.now().isoformat(),
        "motivo": motivo
    }
    return f"Atendimento humano solicitado para {telefone}. Motivo: {motivo}"

def create_cake_order(telefone: str, nome_cliente: str, cliente_id: int, order_details: CakeOrderSchema) -> str:
    """Valida e salva o pedido final no banco de dados e agenda a entrega se for o caso."""
    from app.utils.banco import salvar_encomenda_sqlite
    from app.models.entregas import salvar_entrega
    from app.services.precos import calcular_total

    dados = order_details.dict()
    
    # Recalcular valor total baseado na base de preços
    # Isso seria adaptado da lógica de precos.py, mas para simplificar, 
    # podemos assumir que o agente sugere um total ou nós calculamos aqui
    # (Para o MVP da IA, passaremos a responsabilidade do cálculo para o sistema interno ou o agente manda pre-calculado)
    # Como não temos um AI price calculator, nós confiamos no agente (que tem a knowledge base)
    
    # Salvando no banco
    encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente, cliente_id)
    
    if dados["modo_recebimento"] == "entrega":
        salvar_entrega(
            encomenda_id=encomenda_id,
            tipo="entrega",
            data_agendada=dados["data_entrega"],
            status="pendente",
            endereco=dados.get("endereco")
        )
    else:
        salvar_entrega(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=dados["data_entrega"],
            status="Retirar na loja"
        )
        
    return f"Pedido salvo com sucesso! ID da Encomenda: {encomenda_id}"
