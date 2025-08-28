from app.models.encomendas import criar_ou_atualizar_tabela_encomendas
from app.models.encomendas_doces import criar_tabela_encomenda_doces
from app.models.entregas import criar_tabela_entregas
from app.models.atendimentos import criar_tabela_atendimentos
from app.models.cafeteria import criar_tabela_pedidos_cafeteria
from app.db.database import get_connection

def criar_tabelas():
    conn = get_connection()
    # clientes já tem sua função; chame-a aqui também
    from app.models.clientes import criar_tabela_clientes
    criar_tabela_clientes(conn)

    criar_ou_atualizar_tabela_encomendas(conn)
    criar_tabela_encomenda_doces(conn)
    criar_tabela_entregas(conn)
    criar_tabela_atendimentos(conn)
    criar_tabela_pedidos_cafeteria(conn)
    conn.close()
