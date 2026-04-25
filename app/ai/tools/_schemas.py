"""Pydantic schemas usadas pelas tools de pedido."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PagamentoSchema(BaseModel):
    forma: Literal["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"] = Field(
        ..., description="Forma de pagamento escolhida"
    )
    troco_para: Optional[float] = Field(None, description="Valor para troco, se a forma for Dinheiro")
    parcelas: Optional[int] = Field(
        None,
        description="Parcelas no Cartao. So permitido acima de R$100,00 e no maximo 2x",
    )


class CakeOrderSchema(BaseModel):
    linha: str = Field(..., description="Linha do bolo. Ex: tradicional, gourmet, mesversario, babycake, torta, simples")
    categoria: str = Field(..., description="Categoria derivada da linha. Ex: tradicional, ingles, redondo, torta, mesversario, simples")
    produto: Optional[str] = Field(None, description="Nome do produto ou sabor. Na linha simples, use o sabor: Chocolate ou Cenoura")
    cobertura: Optional[str] = Field(None, description="Cobertura da linha simples: Vulcao ou Simples")
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


class CafeteriaOrderItemSchema(BaseModel):
    nome: str = Field(..., description="Nome base do item da cafeteria. Ex: Croissant, Coca Cola KS, Agua")
    variante: Optional[str] = Field(None, description="Sabor, versao ou opcao quando existir. Ex: Frango com requeijao, com gas")
    quantidade: int = Field(..., description="Quantidade do item")
    observacao: Optional[str] = Field(None, description="Observacao opcional do item")


class CafeteriaOrderSchema(BaseModel):
    itens: List[CafeteriaOrderItemSchema] = Field(..., description="Lista de itens da cafeteria com quantidade e variacoes")
    data_entrega: Optional[str] = Field(None, description="Data do atendimento no formato DD/MM/AAAA quando o cliente informar")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo se for entrega")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega, se aplicavel")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


class GiftOrderSchema(BaseModel):
    categoria: Literal["cesta_box", "caixinha_chocolate", "flores"] = Field(
        ...,
        description="Categoria do presente regular. O fluxo automatico hoje so fecha cesta_box.",
    )
    produto: str = Field(..., description="Nome do presente ou da cesta box")
    descricao: Optional[str] = Field(None, description="Descricao opcional do item")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo se for entrega")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")
