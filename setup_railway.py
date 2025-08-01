#!/usr/bin/env python3
"""
Script de setup para deploy no Railway
Executa todos os scripts necessários para configurar o bot
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def check_environment():
    """Verifica se as variáveis de ambiente estão configuradas"""
    required_vars = [
        'BOT_TOKEN',
        'MYSQL_HOST',
        'MYSQL_USER',
        'MYSQL_PASSWORD',
        'MYSQL_DATABASE'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Variáveis de ambiente faltando:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nConfigure as variáveis de ambiente no Railway ou no arquivo .env")
        return False
    
    print("✅ Todas as variáveis de ambiente estão configuradas")
    return True

def run_script(script_name, description):
    """Executa um script Python"""
    print(f"\n🔄 Executando: {description}")
    print(f"📁 Script: {script_name}")
    
    try:
        # Importar e executar o script
        if script_name == "create_tables":
            from bot import create_tables
            create_tables()
        elif script_name == "check_database":
            from check_database import check_database_connection
            check_database_connection()
        else:
            print(f"❌ Script {script_name} não encontrado")
            return False
        
        print(f"✅ {description} executado com sucesso")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao executar {script_name}: {e}")
        return False

def main():
    """Função principal"""
    print("🚀 Setup do Bot Influenciador para Railway")
    print("=" * 50)
    
    # Verificar ambiente
    if not check_environment():
        sys.exit(1)
    
    # Lista de scripts para executar
    scripts = [
        ("create_tables", "Criando tabelas do banco de dados"),
        ("check_database", "Verificando conexão com banco de dados")
    ]
    
    success_count = 0
    total_scripts = len(scripts)
    
    for script_name, description in scripts:
        if run_script(script_name, description):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Resumo: {success_count}/{total_scripts} scripts executados com sucesso")
    
    if success_count == total_scripts:
        print("🎉 Setup concluído com sucesso!")
        print("\n📝 Próximos passos:")
        print("1. Teste o bot enviando /start")
        print("2. Acesse o menu admin com /admin")
    else:
        print("⚠️  Alguns scripts falharam. Verifique os logs acima.")
        sys.exit(1)

if __name__ == "__main__":
    main() 