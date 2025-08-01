from database import create_connection
from mysql.connector import Error

connection = create_connection()
if connection:
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Verificar fluxos
        cursor.execute("SELECT * FROM flows WHERE is_default = TRUE")
        flows = cursor.fetchall()
        print("Fluxos padrão:")
        for flow in flows:
            print(f"- {flow['name']} (ID: {flow['id']})")
        
        # Verificar etapas do fluxo 2
        cursor.execute("""
            SELECT * FROM flow_steps 
            WHERE flow_id = 2 AND is_active = TRUE 
            ORDER BY step_order
        """)
        steps = cursor.fetchall()
        print(f"\nEtapas do fluxo 2 ({len(steps)} encontradas):")
        for step in steps:
            print(f"- ID: {step['id']}, Ordem: {step['step_order']}, Tipo: {step['step_type']}")
            print(f"  Conteúdo: {step.get('content', '')[:50]}...")
            if step.get('media_url'):
                print(f"  Mídia: {step['media_url']}")
            print()
        
    except Error as e:
        print(f"Erro: {e}")
    finally:
        cursor.close()
        connection.close()
else:
    print("Erro ao conectar ao banco de dados") 