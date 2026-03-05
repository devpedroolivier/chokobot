import asyncio
import os
import sys

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ai.runner import process_message_with_ai

async def run_tests():
    telefone_teste = "5516999999999"
    nome_teste = "Cliente Teste"
    cliente_id = 9999
    
    print("="*60)
    print("TESTES AVANÇADOS: CASOS REAIS DO BANCO DE DADOS")
    print("="*60)

    # ---------------------------------------------------------
    # CASO REAL 1: "Flavia Cliente IGOR" - Bolo Tradicional Complexo
    # Produto: Tradicional | Massa: Mesclada | Recheio: Doce de leite com nozes | Mousse: Ninho | Tam: B3 | Adicional: Nozes
    # Desafio para a IA: Extrair tudo isso de uma ou duas mensagens confusas.
    # ---------------------------------------------------------
    print("\n[CENÁRIO 1] Cliente Flavia (Pedido completo em uma linha + correção):")
    
    msg1 = "Oi, quero encomendar um bolo mesclado B3 com recheio de doce de leite com nozes e mousse de ninho, adiciona nozes."
    print(f"\nFlavia: {msg1}")
    res1 = await process_message_with_ai(telefone_teste, msg1, nome_teste, cliente_id)
    print(f"IA: {res1}")
    
    msg2 = "Ah, pra retirar na loja amanhã umas 14h. Pagamento no pix."
    print(f"\nFlavia: {msg2}")
    res2 = await process_message_with_ai(telefone_teste, msg2, nome_teste, cliente_id)
    print(f"IA: {res2}")

    msg3 = "Pode fechar o pedido!"
    print(f"\nFlavia: {msg3}")
    res3 = await process_message_with_ai(telefone_teste, msg3, nome_teste, cliente_id)
    print(f"IA: {res3}")

    # Resetar sessão para o próximo cliente
    from app.ai.runner import CONVERSATIONS
    CONVERSATIONS.clear()
    
    # ---------------------------------------------------------
    # CASO REAL 2: "Erica Novais" - Casadinho (Regra de Exceção Mousse)
    # Produto: Tradicional | Massa: Chocolate | Recheio: Casadinho | Mousse: Vazio | Tam: B3
    # Desafio para a IA: O Prompt diz que "Casadinho não precisa de Mousse". A IA tem que respeitar essa regra de negócio e não ficar cobrando mousse.
    # ---------------------------------------------------------
    print("\n" + "-"*60)
    print("[CENÁRIO 2] Cliente Erica (Regra do Casadinho - não pedir Mousse):")
    
    msg1_erica = "Quero um bolo B3 de chocolate com recheio casadinho."
    print(f"\nErica: {msg1_erica}")
    res1_erica = await process_message_with_ai(telefone_teste, msg1_erica, nome_teste, cliente_id)
    print(f"IA: {res1_erica}")

    msg2_erica = "Entrega aqui em casa na Rua das Flores, sexta de manha. Pagamento no cartão."
    print(f"\nErica: {msg2_erica}")
    res2_erica = await process_message_with_ai(telefone_teste, msg2_erica, nome_teste, cliente_id)
    print(f"IA: {res2_erica}")

    msg3_erica = "Pode fechar"
    print(f"\nErica: {msg3_erica}")
    res3_erica = await process_message_with_ai(telefone_teste, msg3_erica, nome_teste, cliente_id)
    print(f"IA: {res3_erica}")
    
    CONVERSATIONS.clear()

    # ---------------------------------------------------------
    # CASO REAL 3: "Elaine Lovato" - Linha Gourmet Inglês
    # Produto: Inglês | Nome: Belga
    # Desafio para a IA: Cliente pede "Linha Gourmet", a IA tem que listar as opções em formato inglês.
    # ---------------------------------------------------------
    print("\n" + "-"*60)
    print("[CENÁRIO 3] Cliente Elaine (Fluxo Gourmet Inglês):")
    
    msg1_elaine = "Vocês tem aquele bolo formato inglês?"
    print(f"\nElaine: {msg1_elaine}")
    res1_elaine = await process_message_with_ai(telefone_teste, msg1_elaine, nome_teste, cliente_id)
    print(f"IA: {res1_elaine}")

    msg2_elaine = "Eu quero o de sabor Belga."
    print(f"\nElaine: {msg2_elaine}")
    res2_elaine = await process_message_with_ai(telefone_teste, msg2_elaine, nome_teste, cliente_id)
    print(f"IA: {res2_elaine}")

    msg3_elaine = "Sábado agora, retiro aí. Pago dinheiro troco pra 200."
    print(f"\nElaine: {msg3_elaine}")
    res3_elaine = await process_message_with_ai(telefone_teste, msg3_elaine, nome_teste, cliente_id)
    print(f"IA: {res3_elaine}")
    
    msg4_elaine = "Sim, confirma"
    print(f"\nElaine: {msg4_elaine}")
    res4_elaine = await process_message_with_ai(telefone_teste, msg4_elaine, nome_teste, cliente_id)
    print(f"IA: {res4_elaine}")

    print("\n" + "="*60)
    print("TESTES AVANÇADOS FINALIZADOS")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_tests())