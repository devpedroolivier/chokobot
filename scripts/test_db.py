# scripts/test_db.py
import sqlite3
from pprint import pprint

# importa sua infra de DB e models
from app.db.database import get_connection
from app.models.clientes import criar_tabela_clientes
from app.models.encomendas import criar_ou_atualizar_tabela_encomendas, salvar_encomenda_dict
from app.models.encomendas_doces import criar_tabela_encomenda_doces, salvar_varios_doces
from app.models.entregas import criar_tabela_entregas, salvar_entrega

# util de clientes (get_or_create)
def get_or_create_cliente(phone: str, nome: str = "Nome não informado") -> int:
    conn = get_connection()
    cur = conn.cursor()
    # garantir tabela clientes
    criar_tabela_clientes(conn)
    cur.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
    row = cur.fetchone()
    if row:
        cid = row[0] if not isinstance(row, sqlite3.Row) else row["id"]
    else:
        cur.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome, phone))
        cid = cur.lastrowid
        conn.commit()
    conn.close()
    return cid

def init_schema():
    conn = get_connection()
    criar_tabela_clientes(conn)
    criar_ou_atualizar_tabela_encomendas(conn)
    criar_tabela_encomenda_doces(conn)
    criar_tabela_entregas(conn)
    conn.close()

def main():
    print("🔧 Inicializando schema…")
    init_schema()

    telefone_teste = "5511999999999"
    nome_teste = "Cliente Teste"

    print("👤 Resolvendo cliente…")
    cliente_id = get_or_create_cliente(telefone_teste, nome_teste)
    print(f"cliente_id = {cliente_id}")

    # monta um pedido 'tradicional' (B4 + Kit Festou)
    pedido = {
        "categoria": "tradicional",
        "tamanho": "B4",
        "fruta_ou_nozes": "Morango",
        "descricao": "Massa Branca | Brigadeiro + Ninho",
        "kit_festou": True,
        "quantidade": 1,
        "data_entrega": "25/12/2025",
        "horario_retirada": "15:30",
        "doces_itens": [
            {"nome": "Brigadeiro De Ninho", "qtd": 25, "preco": 37.50, "unit": 1.50},
            {"nome": "Bombom Prestigio", "qtd": 30, "preco": 90.00, "unit": 3.00},
        ],
        "doces_total": 127.50,
        # valores simulados (no fluxo real você calcula via precificação)
        "valor_total": 210.00,     # exemplo: B4 com Morango
        "serve_pessoas": 30,
    }

    print("🧾 Salvando encomenda…")
    encomenda_id = salvar_encomenda_dict(cliente_id, pedido)
    print(f"encomenda_id = {encomenda_id}")

    print("🍬 Salvando doces da encomenda…")
    salvar_varios_doces(encomenda_id, pedido["doces_itens"])

    print("🚚 Registrando entrega/retirada…")
    # aqui vamos registrar retirada; troque para tipo="entrega" e passe endereco se quiser
    salvar_entrega(
        encomenda_id=encomenda_id,
        tipo="retirada",
        endereco=None,
        data_agendada=pedido["data_entrega"],
        status="Retirar na loja"
    )

    # --------- CONSULTAS / CHECKS ---------
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("\n📋 CLIENTES")
    for r in cur.execute("SELECT * FROM clientes ORDER BY id DESC LIMIT 3"):
        pprint(dict(r))

    print("\n🎂 ENCOMENDAS (últimas 3)")
    for r in cur.execute("SELECT * FROM encomendas ORDER BY id DESC LIMIT 3"):
        pprint(dict(r))

    print("\n🍬 DOCES DA ENCOMENDA (atual)")
    for r in cur.execute("SELECT * FROM encomenda_doces WHERE encomenda_id = ?", (encomenda_id,)):
        pprint(dict(r))

    print("\n📦 ENTREGAS DA ENCOMENDA (atual)")
    for r in cur.execute("SELECT * FROM entregas WHERE encomenda_id = ?", (encomenda_id,)):
        pprint(dict(r))

    conn.close()
    print("\n✅ Teste finalizado.")

if __name__ == "__main__":
    main()
