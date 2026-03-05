import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ai.runner import process_message_with_ai, CONVERSATIONS

async def run_tests():
    telefone = "5516999999999"
    cliente_id = 9999
    
    print("="*60)
    print("TESTE DAS NOVAS REGRAS: SAUDAÇÃO, EVENTOS, PASSO A PASSO E UPSELL")
    print("="*60)

    # CENÁRIO 1: Saudação inicial simplificada
    print("\n[CENÁRIO 1: Saudação Genérica (Deve perguntar se é Pronta Entrega ou Encomenda)]")
    msg1 = "Oi"
    print(f"Cliente: {msg1}")
    res1 = await process_message_with_ai(telefone, msg1, "Teste", cliente_id)
    print(f"IA: {res1}")
    
    # CENÁRIO 2: Coleta Passo a Passo (O especialista não pode cuspir todas as perguntas)
    print("\n[CENÁRIO 2: Coleta Passo a Passo no Pedido de Bolo]")
    msg2 = "Quero fazer uma encomenda para o final de semana."
    print(f"Cliente: {msg2}")
    res2 = await process_message_with_ai(telefone, msg2, "Teste", cliente_id)
    print(f"IA: {res2}")
    CONVERSATIONS.clear()

    # CENÁRIO 3: Dia das Mulheres (Escalada imediata)
    print("\n[CENÁRIO 3: Dia das Mulheres (Deve escalar para humano imediatamente)]")
    msg3 = "Boa tarde, vocês têm alguma opção de presente pro Dia das mulheres?"
    print(f"Cliente: {msg3}")
    res3 = await process_message_with_ai(telefone, msg3, "Teste", cliente_id)
    print(f"IA: {res3}")
    CONVERSATIONS.clear()

    # CENÁRIO 4: Fora de Contexto (Escalada imediata)
    print("\n[CENÁRIO 4: Fora de Contexto (Anti-alucinação)]")
    msg4 = "Vocês trocam pneu de carro aí perto da doceria?"
    print(f"Cliente: {msg4}")
    res4 = await process_message_with_ai(telefone, msg4, "Teste", cliente_id)
    print(f"IA: {res4}")
    CONVERSATIONS.clear()
    
    # CENÁRIO 5: Pronta Entrega + Upsell do Kit Festou
    print("\n[CENÁRIO 5: Pronta Entrega + Upsell do Kit Festou]")
    msg5 = "Tem bolo pra hoje?"
    print(f"Cliente: {msg5}")
    res5 = await process_message_with_ai(telefone, msg5, "Teste", cliente_id)
    print(f"IA: {res5}")
    
    msg6 = "Quero um B3 de chocolate."
    print(f"Cliente: {msg6}")
    res6 = await process_message_with_ai(telefone, msg6, "Teste", cliente_id)
    print(f"IA: {res6}")

if __name__ == "__main__":
    asyncio.run(run_tests())
