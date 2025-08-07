import os
from datetime import datetime

def salvar_cliente(phone: str, nome: str = "Nome não informado"):
    try:
        caminho = "dados/clientes.txt"
        if os.path.exists(caminho):
            with open(caminho, "r", encoding="utf-8") as f:
                if any(phone in linha for linha in f):
                    print(f"🔁 Número já registrado: {phone}")
                    return

        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        linha = f"{agora} - {nome} | {phone}\n"
        with open(caminho, "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Cliente salvo:", linha.strip())

    except Exception as e:
        print("❌ Erro ao salvar cliente:", e)


def salvar_encomenda(phone: str, dados: dict, nome: str = "Nome não informado"):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha_bolo = dados.get("linha", "Normal").lower()

    if linha_bolo in ["gourmet", "redondo", "torta"]:
        linha = (
            f"{agora} - {nome} | {phone} | "
            f"Linha: {dados.get('linha')} | "
            f"Bolo: {dados.get('gourmet', 'Não informado')} | "
            f"Data: {dados.get('data', dados.get('pronta_entrega', '-'))}\n"
        )
    else:
        linha = (
            f"{agora} - {nome} | {phone} | "
            f"Linha: {dados.get('linha', 'Normal')} | "
            f"Massa: {dados.get('massa', '-') } | "
            f"Recheio: {dados.get('recheio', '-') } | "
            f"Mousse: {dados.get('mousse', '-') } | "
            f"Adicional: {dados.get('adicional', 'Nenhum')} | "
            f"Tamanho: {dados.get('tamanho', '-')} | "
            f"Data: {dados.get('data', dados.get('pronta_entrega', '-'))}\n"
        )

    try:
        with open("dados/encomendas.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Encomenda salva:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar encomenda:", e)
