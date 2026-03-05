import asyncio
import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH para os imports funcionarem no script avulso
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.runner import process_message_with_ai

async def run_tests():
    telefone_teste = "5511999999999"
    nome_teste = "Cliente Teste"
    cliente_id = 9999
    
    print("="*50)
    print("INICIANDO TESTES DO AGENTE DE IA - CHOKOBOT")
    print("="*50)

    # Verifica chave da API
    if not os.getenv("OPENAI_API_KEY") or "sua_chave" in os.getenv("OPENAI_API_KEY"):
        print("⚠️  ERRO: Chave da OpenAI não configurada no ambiente!")
        print("Por favor, adicione uma chave válida no arquivo .env antes de rodar os testes.")
        return

    # Cenário 1: Saudação inicial e intenção genérica (Deveria acionar TriageAgent)
    print("\n[CENÁRIO 1] Cliente manda um 'Oi' genérico:")
    msg1 = "Oi, tudo bem? Queria saber se vocês fazem bolo pra festa."
    print(f"Cliente: {msg1}")
    res1 = await process_message_with_ai(telefone_teste, msg1, nome_teste, cliente_id)
    print(f"Trufinha (IA): {res1}")
    
    # Cenário 2: Dúvida sobre cardápio (Deveria acionar KnowledgeAgent e ler RAG)
    print("\n[CENÁRIO 2] Cliente faz uma pergunta de conhecimento (KnowledgeAgent):")
    msg2 = "Qual é o valor do bolo da linha mesversário e quais tamanhos tem?"
    print(f"Cliente: {msg2}")
    res2 = await process_message_with_ai(telefone_teste, msg2, nome_teste, cliente_id)
    print(f"Trufinha (IA): {res2}")

    # Cenário 3: Início de Pedido Natural Language (Deveria acionar CakeOrderAgent)
    print("\n[CENÁRIO 3] Cliente tenta fazer o pedido em linguagem natural:")
    msg3 = "Legal! Eu vou querer um P4 pra amanhã a tarde, pra retirar na loja."
    print(f"Cliente: {msg3}")
    res3 = await process_message_with_ai(telefone_teste, msg3, nome_teste, cliente_id)
    print(f"Trufinha (IA): {res3}")
    
    # Cenário 4: Preenchimento de dados faltantes (Agente precisa cobrar a massa e recheio)
    print("\n[CENÁRIO 4] Agente precisa insistir em dados faltantes para o Schema:")
    msg4 = "Massa de chocolate. Vou pagar no PIX."
    print(f"Cliente: {msg4}")
    res4 = await process_message_with_ai(telefone_teste, msg4, nome_teste, cliente_id)
    print(f"Trufinha (IA): {res4}")
    
    # Cenário 5: Escalada Humana (Deveria acionar a tool de escalate)
    print("\n[CENÁRIO 5] Cliente quer falar com humano (escalate_to_human):")
    msg5 = "Moça, não entendi nada, quero falar com um atendente real agora"
    print(f"Cliente: {msg5}")
    res5 = await process_message_with_ai(telefone_teste, msg5, nome_teste, cliente_id)
    print(f"Trufinha (IA): {res5}")
    
    print("\n" + "="*50)
    print("TESTES FINALIZADOS")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_tests())