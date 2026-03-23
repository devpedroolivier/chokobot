from __future__ import annotations

from pathlib import Path

from app.domain.repositories.order_repository import OrderRepository


def build_orders_export_text(rows: list[tuple]) -> str:
    lines: list[str] = []
    for cliente, produto, data, valor, status in rows:
        lines.append(f"{cliente} | {produto or '-'} | {data or '-'} | R${valor or '0,00'} | {status}")
    return "\n".join(lines) + ("\n" if lines else "")


def export_orders_txt(repository: OrderRepository, destination: str | Path) -> Path:
    output_path = Path(destination)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_orders_export_text(repository.export_rows()), encoding="utf-8")
    return output_path


def build_create_order_payload(
    *,
    nome: str,
    telefone: str,
    produto: str = "",
    categoria: str = "",
    linha: str = "",
    tamanho: str = "",
    massa: str = "",
    recheio: str = "",
    mousse: str = "",
    adicional: str = "",
    fruta_ou_nozes: str = "",
    valor_total: str = "0",
    data_entrega: str,
    horario: str = "",
    horario_retirada: str = "",
) -> dict[str, str]:
    categoria_final = categoria or linha or "tradicional"
    adicional_final = adicional or fruta_ou_nozes
    horario_final = horario or horario_retirada

    return {
        "nome": nome,
        "telefone": telefone,
        "categoria": categoria_final,
        "produto": produto,
        "tamanho": tamanho,
        "massa": massa,
        "recheio": recheio,
        "mousse": mousse,
        "adicional": adicional_final,
        "horario": horario_final,
        "valor_total": valor_total,
        "data_entrega": data_entrega,
    }
