import os
from database import create_connection
from mysql.connector import Error

def add_admin(telegram_id):
    """Adiciona um administrador ao sistema"""
    connection = create_connection()
    if connection is None:
        print("❌ Erro: Não foi possível conectar ao banco de dados.")
        return False
    
    try:
        cursor = connection.cursor()
        
        # Verificar se o admin já existe
        check_admin = "SELECT id FROM admin_config WHERE admin_telegram_id = %s"
        cursor.execute(check_admin, (telegram_id,))
        admin_exists = cursor.fetchone()
        
        if admin_exists:
            print(f"✅ Admin com ID {telegram_id} já existe no sistema.")
            return True
        
        # Inserir novo admin
        insert_admin = "INSERT INTO admin_config (admin_telegram_id) VALUES (%s)"
        cursor.execute(insert_admin, (telegram_id,))
        connection.commit()
        
        print(f"✅ Admin com ID {telegram_id} adicionado com sucesso!")
        return True
        
    except Error as e:
        print(f"❌ Erro ao adicionar admin: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def list_admins():
    """Lista todos os administradores"""
    connection = create_connection()
    if connection is None:
        print("❌ Erro: Não foi possível conectar ao banco de dados.")
        return
    
    try:
        cursor = connection.cursor()
        
        query = "SELECT admin_telegram_id, created_at FROM admin_config ORDER BY created_at"
        cursor.execute(query)
        admins = cursor.fetchall()
        
        if admins:
            print("\n📋 **Administradores:**")
            print("-" * 40)
            for admin in admins:
                print(f"ID: {admin[0]} | Criado: {admin[1]}")
            print("-" * 40)
        else:
            print("❌ Nenhum administrador encontrado.")
            
    except Error as e:
        print(f"❌ Erro ao listar admins: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def main():
    """Função principal"""
    print("🔧 **Sistema de Administração**")
    print("=" * 40)
    
    while True:
        print("\nEscolha uma opção:")
        print("1. Adicionar administrador")
        print("2. Listar administradores")
        print("3. Sair")
        
        choice = input("\nOpção: ").strip()
        
        if choice == "1":
            try:
                telegram_id = int(input("Digite o ID do Telegram do admin: "))
                add_admin(telegram_id)
            except ValueError:
                print("❌ ID inválido. Digite apenas números.")
        
        elif choice == "2":
            list_admins()
        
        elif choice == "3":
            print("👋 Saindo...")
            break
        
        else:
            print("❌ Opção inválida.")

if __name__ == '__main__':
    main() 