import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.runner import process_message_with_ai, CONVERSATIONS

async def run_tests():
    telefone_teste = "5516999999999"
    nome_teste = "Cliente Flow"
    cliente_id = 1000
    
    print("="*60)
    print("TESTE DE TODOS OS FLUXOS & LOOP DE APRENDIZAGEM")
    print("="*60)

    # ---------------------------------------------------------
    # FLUXO 1: CAFETERIA
    # ---------------------------------------------------------
    print("\n[FLUXO 1: CAFETERIA]")
    msg = "Oi, queria ver o cardápio da cafeteria"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    msg = "Quero um espresso duplo e um pão de queijo"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # FLUXO 2: TORTAS
    # ---------------------------------------------------------
    print("\n[FLUXO 2: TORTAS]")
    msg = "Vocês tem torta de limão?"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    msg = "Isso, vou querer uma torta de limão para retirar sabado as 15h. Pago em dinheiro, troco pra 200."
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    msg = "Pode fechar"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # FLUXO 3: BABY CAKE
    # ---------------------------------------------------------
    print("\n[FLUXO 3: BABY CAKE]")
    msg = "Eu quero um baby cake"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    msg = "O de doce de leite. Quero que escreva 'Te amo'. Retiro amanhã de manha, pix."
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    msg = "sim, confirma"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # FLUXO 4: PRONTA ENTREGA
    # ---------------------------------------------------------
    print("\n[FLUXO 4: PRONTA ENTREGA]")
    msg = "Tem bolo pra hoje?"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # FLUXO 5: CESTAS BOX
    # ---------------------------------------------------------
    print("\n[FLUXO 5: CESTAS BOX]")
    msg = "Quero dar uma cesta de presente"
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # FLUXO 6: LOOP DE APRENDIZAGEM
    # ---------------------------------------------------------
    print("\n[FLUXO 6: LOOP DE APRENDIZAGEM]")
    msg = "Aprenda essa regra: sempre que alguém pedir bolo de cenoura, avise que ele vem com muita calda de chocolate extra."
    print(f"Cliente: {msg}")
    res = await process_message_with_ai(telefone_teste, msg, nome_teste, cliente_id)
    print(f"IA: {res}")
    
    CONVERSATIONS.clear() # Limpa a sessão simulando outro cliente
    
    msg2 = "Queria um bolo simples de cenoura"
    print(f"Cliente 2: {msg2}")
    res2 = await process_message_with_ai("5516999999998", msg2, "Outro Cliente", 1001)
    print(f"IA (Lembrando da regra): {res2}")

if __name__ == "__main__":
    asyncio.run(run_tests())