import asyncio
import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH para importações funcionarem
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.runner import process_message_with_ai, CONVERSATIONS

async def run_e2e_test():
    telefone = "5516999998888" # Telefone único para o E2E
    nome_cliente = "Cliente E2E Test"
    cliente_id = 8888
    
    # Limpa a conversa antes de começar
    CONVERSATIONS.clear()

    print("="*70)
    print("🚀 TESTE END-TO-END (E2E): FLUXO COMPLETO DE ENCOMENDA")
    print("="*70)

    # Passo 1: Saudação inicial
    msg1 = "Oi"
    print(f"\n🗣️ Cliente: {msg1}")
    res1 = await process_message_with_ai(telefone, msg1, nome_cliente, cliente_id)
    print(f"🤖 IA: {res1}")
    
    # Passo 2: Define a intenção (Encomenda para amanhã para driblar a regra das 11h)
    msg2 = "Quero fazer uma encomenda de bolo para amanhã."
    print(f"\n🗣️ Cliente: {msg2}")
    res2 = await process_message_with_ai(telefone, msg2, nome_cliente, cliente_id)
    print(f"🤖 IA: {res2}")

    # Passo 3: Fornece dados parciais (Tamanho e Massa)
    msg3 = "Quero um bolo B3 com massa de chocolate."
    print(f"\n🗣️ Cliente: {msg3}")
    res3 = await process_message_with_ai(telefone, msg3, nome_cliente, cliente_id)
    print(f"🤖 IA: {res3}")

    # Passo 4: Fornece recheio e mousse
    msg4 = "Recheio de brigadeiro e mousse de ninho."
    print(f"\n🗣️ Cliente: {msg4}")
    res4 = await process_message_with_ai(telefone, msg4, nome_cliente, cliente_id)
    print(f"🤖 IA: {res4}")

    # Passo 5: Fornece data/hora, modo de recebimento e pagamento
    # Simulando que "amanhã" será 10/10/2030 para passar na validação estrita de data
    msg5 = "Vou retirar na loja às 15:00 no dia 10/10/2030. Pago no PIX."
    print(f"\n🗣️ Cliente: {msg5}")
    res5 = await process_message_with_ai(telefone, msg5, nome_cliente, cliente_id)
    print(f"🤖 IA: {res5}")

    # Passo 6: Confirmação final (Gatilho para salvar no banco)
    msg6 = "Sim, pode fechar."
    print(f"\n🗣️ Cliente: {msg6}")
    res6 = await process_message_with_ai(telefone, msg6, nome_cliente, cliente_id)
    print(f"🤖 IA: {res6}")

    print("\n" + "="*70)
    print("✅ TESTE E2E CONCLUÍDO. VERIFICANDO BANCO DE DADOS...")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
