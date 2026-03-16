from app.application.use_cases.process_cesta_box_flow import (
    CESTAS_BOX_CATALOGO,
    montar_menu_cestas,
    montar_resumo_e_confirmar,
    process_cesta_box_flow,
    salvar_pedido_cesta,
)


async def processar_cestas_box(telefone, texto, estado, nome_cliente, cliente_id):
    return await process_cesta_box_flow(telefone, texto, estado, nome_cliente, cliente_id)
