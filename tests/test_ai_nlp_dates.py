import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ai.runner import process_message_with_ai

async def run_tests():
    telefone = "5516999990000"
    cliente_id = 999
    
    print("="*60)
    print("TESTE DE CONVERSÃO NLP PARA DATAS E HORÁRIOS")
    print("="*60)

    # Passo 1
    msg1 = "Quero encomendar um bolo B3 de chocolate com brigadeiro."
    print(f"\n🗣️ Cliente: {msg1}")
    res1 = await process_message_with_ai(telefone, msg1, "Teste", cliente_id)
    print(f"🤖 IA: {res1}")
    
    # Passo 2
    msg2 = "Recheio e mousse de brigadeiro."
    print(f"\n🗣️ Cliente: {msg2}")
    res2 = await process_message_with_ai(telefone, msg2, "Teste", cliente_id)
    print(f"🤖 IA: {res2}")

    # Passo 3: O cliente fala gírias temporais (desafio para a IA)
    msg3 = "Pra amanhã no meio da tarde, lá pras três horas. Retiro aí. Pix."
    print(f"\n🗣️ Cliente: {msg3}")
    res3 = await process_message_with_ai(telefone, msg3, "Teste", cliente_id)
    print(f"🤖 IA: {res3}")

if __name__ == "__main__":
    asyncio.run(run_tests())
