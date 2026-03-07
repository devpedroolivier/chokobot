from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.application.service_registry import (
    get_attention_gateway,
    get_catalog_gateway,
    get_delivery_gateway,
    get_order_gateway,
)
from app.security import ai_learning_enabled, security_audit
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido, _linha_canonica


class PagamentoSchema(BaseModel):
    forma: Literal["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"] = Field(..., description="Forma de pagamento escolhida")
    troco_para: Optional[float] = Field(None, description="Valor para troco, se a forma for Dinheiro")

class CakeOrderSchema(BaseModel):
    linha: str = Field(..., description="Linha do bolo. Ex: tradicional, gourmet, mesversario, babycake, torta, simples")
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
    """Retorna o cardapio completo ou filtrado entre pronta entrega e encomendas."""
    return get_catalog_gateway().get_menu(category)

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
    """Valida e salva o pedido final no banco de dados e agenda a entrega se for o caso."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    dados = order_details.model_dump()
    dados["linha"] = _linha_canonica(dados.get("linha"))

    if dados["modo_recebimento"] == "entrega" and not _horario_entrega_permitido(dados.get("horario_retirada")):
        return f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. Ajuste o horario ou altere para retirada."

    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )
    
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
        
    return f"Pedido salvo com sucesso! ID da Encomenda: {encomenda_id}"
