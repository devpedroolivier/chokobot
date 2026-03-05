from pydantic import BaseModel, Field
from typing import Optional, List, Literal

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

def get_menu(category: str = "todas") -> str:
    """Retorna os cardápios da doceria como texto em Markdown para o agente consultar."""
    try:
        with open("app/ai/knowledge/menus.md", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return "Erro ao carregar cardápio: " + str(e)

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
