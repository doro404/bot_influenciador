import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def create_connection():
    try:
        # Verifica se está em ambiente de produção (Railway)
        if os.getenv('RAILWAY_ENVIRONMENT') == 'production':
            connection = mysql.connector.connect(
                host=os.getenv('MYSQL_HOST'),
                port=int(os.getenv('MYSQL_PORT', 3306)),
                database=os.getenv('MYSQL_DATABASE'),
                user=os.getenv('MYSQL_USER'),
                password=os.getenv('MYSQL_PASSWORD')
            )
        else:
            # Credenciais fixas para uso local
            connection = mysql.connector.connect(
                host='localhost',
                port=3306,  # Porta padrão do MySQL
                database='kpftdhra_bot_influenciador',
                user='root',
                password=''
            )

        if connection.is_connected():
            print("Conexão com o MySQL foi bem-sucedida.")
            return connection

    except Error as e:
        print(f"Erro ao conectar ao MySQL: {e}")
        return None

# Exemplo de uso
if __name__ == "__main__":
    conn = create_connection()
    # ... faça algo com a conexão ...
    if conn:
        conn.close() 