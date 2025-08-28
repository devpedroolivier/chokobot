from datetime import datetime
import os
from sqlite3 import Connection
from app.db.database import get_connection
from app.utils.mensagens import responder_usuario
from app.services.estados import estados_entrega


# 🔧 Criar tabela se não existir
def criar_tabela_entregas(conn: Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            encomenda_id INTEGER NOT NULL,
            tipo TEXT DEFAULT 'entrega',
            endereco TEXT,
            data_agendada TEXT,
            status TEXT DEFAULT 'pendente',
            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (encomenda_id) REFERENCES encomendas(id)
        );
    """)
    conn.commit()

# 💾 Salvar entrega no banco SQLite
def salvar_entrega(
    encomenda_id: int,
    tipo: str = "entrega",
    endereco: str = None,
    data_agendada: str = None,
    status: str = "pendente"
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO entregas (encomenda_id, tipo, endereco, data_agendada, status)
        VALUES (?, ?, ?, ?, ?)
    """, (encomenda_id, tipo, endereco, data_agendada, status))

    conn.commit()
    conn.close()
    print(f"📦 Entrega registrada no banco - Tipo: {tipo}, Status: {status}")

# 📂 Redundância no .txt
def salvar_entrega_txt(telefone, nome, dados):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linha = f"{agora} - {nome} | {telefone} | Endereço: {dados.get('endereco', 'Retirada')} | Referência: {dados.get('referencia', '---')}\n"

    try:
        os.makedirs("dados", exist_ok=True)
        with open("dados/entregas.txt", "a", encoding="utf-8") as f:
            f.write(linha)
        print("📝 Entrega registrada no .txt:", linha.strip())
    except Exception as e:
        print("❌ Erro ao salvar entrega:", e)

# 🤖 Processar fluxo de entrega
async def processar_entrega(telefone, texto, estado):
    etapa = estado["etapa"]
    dados = estado["dados"]
    nome = estado["nome"]

    print(f"📍 ETAPA ATUAL: {etapa}")

    # 🚶‍♂️ Caso especial: retirada
    if etapa == "retirada":
        encomenda_id = dados.get("encomenda_id")
        data_agendada = dados.get("data")

        if encomenda_id:
            salvar_entrega(
                encomenda_id=encomenda_id,
                tipo="retirada",
                data_agendada=data_agendada,
                status="Retirada na loja"
            )
        await responder_usuario(telefone, "✅ Encomenda registrada com sucesso 🎂")
        return "finalizar"

    # 🏠 Etapa 1: endereço
    if etapa == 1:
        dados["endereco"] = texto
        estado["etapa"] = 2
        await responder_usuario(telefone, "📞 Informe um telefone alternativo ou referência, se tiver:")

    # 📝 Etapa 2: referência e salvar entrega
    elif etapa == 2:
        dados["referencia"] = texto
        encomenda_id = dados.get("encomenda_id")
        data_agendada = dados.get("data")

        if encomenda_id:
            try:
                salvar_entrega(
                    encomenda_id=encomenda_id,
                    tipo="entrega",
                    endereco=dados["endereco"],
                    data_agendada=data_agendada,
                    status="pendente"
                )
                print(f"✅ Entrega registrada com encomenda_id {encomenda_id}")
            except Exception as e:
                print(f"❌ ERRO ao salvar entrega no banco: {e}")

        salvar_entrega_txt(telefone, nome, dados)

        await responder_usuario(telefone, "🚚 Endereço registrado! Em breve confirmaremos o envio com você.")
        return "finalizar"
