from app.application.use_cases.process_cafeteria_flow import PRONTA_ENTREGA_BOLOS_MSG, process_cafeteria_flow


async def processar_cafeteria(telefone, texto, estado):
    return await process_cafeteria_flow(telefone, texto, estado)
