from datetime import datetime

def print_painel(body: dict):
    nome = body.get("chatName", "Desconhecido")
    numero = body.get("phone", "N/A")
    texto = body.get("text", {}).get("message", "")
    hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    print("\n" + "=" * 40)
    print("📬 MENSAGEM RECEBIDA")
    print(f"👤 Nome: {nome}")
    print(f"📱 Número: {numero}")
    print(f"💬 Mensagem: {texto}")
    print(f"🕐 Horário: {hora}")
    print("=" * 40 + "\n")
