from app.application.use_cases.process_delivery_flow import ProcessDeliveryFlow


_flow = ProcessDeliveryFlow()


async def processar_entrega(telefone, texto, estado):
    return await _flow.execute(telefone=telefone, texto=texto, estado=estado)
