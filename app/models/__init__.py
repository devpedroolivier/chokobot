from app.db.database import get_connection
from .clientes import criar_tabela_clientes
from .encomendas import criar_tabela_encomendas
from .entregas import criar_tabela_entregas
from .cafeteria import criar_tabela_pedidos_cafeteria
from .atendimentos import criar_tabela_atendimentos

def criar_tabelas():
    conn = get_connection()
    criar_tabela_clientes(conn)
    criar_tabela_encomendas(conn)
    criar_tabela_entregas(conn)
    criar_tabela_pedidos_cafeteria(conn)
    criar_tabela_atendimentos(conn)
    conn.close()
