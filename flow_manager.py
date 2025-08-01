import os
from database import create_connection
from mysql.connector import Error
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class FlowManager:
    def __init__(self):
        pass
    
    def get_active_flows(self):
        """Obtém todos os fluxos ativos"""
        connection = create_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM flows WHERE is_active = TRUE ORDER BY name"
            cursor.execute(query)
            return cursor.fetchall()
        except Error as e:
            print(f"Erro ao obter fluxos: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_flow_steps(self, flow_id):
        """Obtém todas as etapas de um fluxo"""
        connection = create_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
            SELECT fs.*
            FROM flow_steps fs
            WHERE fs.flow_id = %s AND fs.is_active = TRUE
            ORDER BY fs.step_order
            """
            cursor.execute(query, (flow_id,))
            steps = cursor.fetchall()
            
            # Para cada etapa, buscar os botões separadamente
            for step in steps:
                step['buttons'] = self.get_step_buttons(step['id'])
            
            return steps
        except Error as e:
            print(f"Erro ao obter etapas do fluxo: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def create_flow(self, name, description=""):
        """Cria um novo fluxo"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = "INSERT INTO flows (name, description) VALUES (%s, %s)"
            cursor.execute(query, (name, description))
            connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Erro ao criar fluxo: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def add_flow_step(self, flow_id, step_order, step_type, content, media_url=None):
        """Adiciona uma etapa ao fluxo"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = """
            INSERT INTO flow_steps (flow_id, step_order, step_type, content, media_url)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (flow_id, step_order, step_type, content, media_url))
            connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Erro ao adicionar etapa: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def add_button_to_step(self, step_id, button_text, button_type="callback", button_data=None):
        """Adiciona um botão a uma etapa"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = """
            INSERT INTO buttons (step_id, button_text, button_type, button_data)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (step_id, button_text, button_type, button_data))
            connection.commit()
            return cursor.lastrowid
        except Error as e:
            print(f"Erro ao adicionar botão: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def update_step_media(self, step_id, media_url):
        """Atualiza a mídia de uma etapa"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = "UPDATE flow_steps SET media_url = %s WHERE id = %s"
            cursor.execute(query, (media_url, step_id))
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao atualizar mídia: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_step_buttons(self, step_id):
        """Obtém todos os botões de uma etapa"""
        connection = create_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
            SELECT * FROM buttons 
            WHERE step_id = %s AND is_active = TRUE 
            ORDER BY button_order
            """
            cursor.execute(query, (step_id,))
            return cursor.fetchall()
        except Error as e:
            print(f"Erro ao obter botões: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def delete_step(self, step_id):
        """Deleta uma etapa e seus botões"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            # Deletar botões primeiro
            cursor.execute("DELETE FROM buttons WHERE step_id = %s", (step_id,))
            # Deletar etapa
            cursor.execute("DELETE FROM flow_steps WHERE id = %s", (step_id,))
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao deletar etapa: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def reorder_steps(self, flow_id):
        """Reordena as etapas de um fluxo"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Obter todas as etapas ordenadas
            select_query = """
            SELECT id FROM flow_steps 
            WHERE flow_id = %s 
            ORDER BY step_order
            """
            cursor.execute(select_query, (flow_id,))
            steps = cursor.fetchall()
            
            # Atualizar a ordem de cada etapa
            for i, step in enumerate(steps, 1):
                update_query = """
                UPDATE flow_steps 
                SET step_order = %s 
                WHERE id = %s
                """
                cursor.execute(update_query, (i, step[0]))
            
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao reordenar etapas: {e}")
            # Se falhar, tentar método mais simples
            return self.simple_reorder_steps(flow_id)
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def simple_reorder_steps(self, flow_id):
        """Método simples para reordenar etapas (fallback)"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Apenas verificar se existem etapas
            check_query = "SELECT COUNT(*) FROM flow_steps WHERE flow_id = %s"
            cursor.execute(check_query, (flow_id,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"Fluxo {flow_id} tem {count} etapas - reordenamento simples aplicado")
                return True
            else:
                return False
        except Error as e:
            print(f"Erro no reordenamento simples: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_next_step_order(self, flow_id):
        """Obtém a próxima ordem de etapa para um fluxo"""
        connection = create_connection()
        if not connection:
            return 1
        
        try:
            cursor = connection.cursor()
            query = "SELECT MAX(step_order) FROM flow_steps WHERE flow_id = %s"
            cursor.execute(query, (flow_id,))
            result = cursor.fetchone()
            
            if result and result[0]:
                return result[0] + 1
            else:
                return 1
        except Error as e:
            print(f"Erro ao obter próxima ordem: {e}")
            return 1
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def delete_flow(self, flow_id):
        """Deleta um fluxo e todas suas etapas"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Primeiro, deletar todos os botões das etapas do fluxo
            cursor.execute("""
                DELETE b FROM buttons b
                INNER JOIN flow_steps fs ON b.step_id = fs.id
                WHERE fs.flow_id = %s
            """, (flow_id,))
            
            # Depois, deletar todas as etapas do fluxo
            cursor.execute("DELETE FROM flow_steps WHERE flow_id = %s", (flow_id,))
            
            # Por fim, deletar o fluxo
            cursor.execute("DELETE FROM flows WHERE id = %s", (flow_id,))
            
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao deletar fluxo: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def save_flow_step(self, flow_id, step_data):
        """Salva uma etapa no fluxo com ordem automática"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Obter próxima ordem
            next_order = self.get_next_step_order(flow_id)
            
            # Inserir etapa
            insert_step = """
            INSERT INTO flow_steps (flow_id, step_order, step_type, content, media_url)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            # Determinar o step_type correto
            step_type = step_data.get('type', 'text')
            original_video = step_data.get('original_video', False)
            
            # Se for vídeo redondo, garantir que o step_type seja 'video_note'
            if step_type == 'video_note':
                step_type = 'video_note'
            elif step_type == 'video' and original_video:
                # Se for vídeo convertido para vídeo redondo
                step_type = 'video_note'
            
            cursor.execute(insert_step, (
                flow_id,
                next_order,
                step_type,
                step_data.get('content', ''),
                step_data.get('media_url')
            ))
            
            step_id = cursor.lastrowid
            
            # Adicionar botões se existirem
            buttons = step_data.get('buttons', [])
            for i, button in enumerate(buttons):
                insert_button = """
                INSERT INTO buttons (step_id, button_text, button_type, button_data, button_order)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_button, (
                    step_id,
                    button.get('text', ''),
                    button.get('type', 'callback'),
                    button.get('data', ''),
                    i + 1
                ))
            
            connection.commit()
            return step_id
        except Error as e:
            print(f"Erro ao salvar etapa: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_flow_summary(self, flow_id):
        """Obtém um resumo do fluxo"""
        connection = create_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Obter informações do fluxo
            flow_query = "SELECT * FROM flows WHERE id = %s"
            cursor.execute(flow_query, (flow_id,))
            flow = cursor.fetchone()
            
            if not flow:
                return None
            
            # Obter etapas do fluxo
            steps_query = """
            SELECT fs.*, COUNT(b.id) as button_count
            FROM flow_steps fs
            LEFT JOIN buttons b ON fs.id = b.step_id
            WHERE fs.flow_id = %s
            GROUP BY fs.id
            ORDER BY fs.step_order
            """
            cursor.execute(steps_query, (flow_id,))
            steps = cursor.fetchall()
            
            return {
                'flow': flow,
                'steps': steps,
                'total_steps': len(steps)
            }
        except Error as e:
            print(f"Erro ao obter resumo do fluxo: {e}")
            return None
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def is_admin(self, telegram_id):
        """Verifica se o usuário é admin"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = "SELECT id FROM admin_config WHERE admin_telegram_id = %s"
            cursor.execute(query, (telegram_id,))
            return cursor.fetchone() is not None
        except Error as e:
            print(f"Erro ao verificar admin: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def add_admin(self, telegram_id):
        """Adiciona um admin"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            query = "INSERT INTO admin_config (admin_telegram_id) VALUES (%s)"
            cursor.execute(query, (telegram_id,))
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao adicionar admin: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_default_flow(self):
        """Obtém o fluxo padrão"""
        connection = create_connection()
        if not connection:
            return None
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = "SELECT * FROM flows WHERE is_default = TRUE AND is_active = TRUE LIMIT 1"
            cursor.execute(query)
            return cursor.fetchone()
        except Error as e:
            print(f"Erro ao obter fluxo padrão: {e}")
            return None
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def set_default_flow(self, flow_id):
        """Define um fluxo como padrão"""
        connection = create_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Primeiro, remover o padrão atual
            cursor.execute("UPDATE flows SET is_default = FALSE WHERE is_default = TRUE")
            
            # Depois, definir o novo padrão
            cursor.execute("UPDATE flows SET is_default = TRUE WHERE id = %s", (flow_id,))
            
            connection.commit()
            return True
        except Error as e:
            print(f"Erro ao definir fluxo padrão: {e}")
            return False
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()
    
    def get_flows_for_default_selection(self):
        """Obtém todos os fluxos ativos para seleção de padrão"""
        connection = create_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            query = """
            SELECT id, name, description, is_default, 
                   (SELECT COUNT(*) FROM flow_steps WHERE flow_id = flows.id) as step_count
            FROM flows 
            WHERE is_active = TRUE 
            ORDER BY is_default DESC, name
            """
            cursor.execute(query)
            return cursor.fetchall()
        except Error as e:
            print(f"Erro ao obter fluxos para seleção: {e}")
            return []
        finally:
            if connection and connection.is_connected():
                cursor.close()
                connection.close()

def create_admin_keyboard():
    """Creates keyboard for admin menu"""
    keyboard = [
        [InlineKeyboardButton("📝 Manage Flows", callback_data="admin_flows")],
        [InlineKeyboardButton("⭐ Set Default Flow", callback_data="set_default_flow")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_config")],
        [InlineKeyboardButton("🔄 Reset Welcome Video", callback_data="reset_welcome_video")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_flow_management_keyboard():
    """Creates keyboard for flow management"""
    keyboard = [
        [InlineKeyboardButton("➕ Create New Flow", callback_data="create_flow")],
        [InlineKeyboardButton("📋 List Flows", callback_data="list_flows")],
        [InlineKeyboardButton("✏️ Edit Flow", callback_data="edit_flow")],
        [InlineKeyboardButton("🗑️ Delete Flow", callback_data="delete_flow")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_message_step_keyboard(step_number):
    """Creates keyboard for specific message step"""
    keyboard = [
        [InlineKeyboardButton(f"📝 Message + Text", callback_data="add_message_text")],
        [InlineKeyboardButton(f"🖼️ Message + Image", callback_data="add_message_image")],
        [InlineKeyboardButton(f"🎥 Message + Video", callback_data="add_message_video")],
        [InlineKeyboardButton(f"🎬 Message + Video Note", callback_data="add_message_video_note")],
        [InlineKeyboardButton(f"🔘 Message + Image + Button", callback_data="add_message_image_button")],
        [InlineKeyboardButton(f"🔘 Message + Text + Button", callback_data="add_message_text_button")],
        [InlineKeyboardButton(f"🔘 Message + Video + Button", callback_data="add_message_video_button")],
        [InlineKeyboardButton(f"🔘 Message + Video Note + Button", callback_data="add_message_video_note_button")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_flows")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_simple_flow_control_keyboard():
    """Creates simple keyboard for flow control"""
    keyboard = [
        [InlineKeyboardButton("⏭️ Continue Flow", callback_data="continue_flow")],
        [InlineKeyboardButton("🏁 Finish Flow", callback_data="finish_flow")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_flows")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_media_options_keyboard():
    """Creates keyboard for media options"""
    keyboard = [
        [InlineKeyboardButton("📎 Attach Media", callback_data="attach_media")],
        [InlineKeyboardButton("🔗 Use URL", callback_data="use_media_url")],
        [InlineKeyboardButton("📝 Text Only", callback_data="text_only")],
        [InlineKeyboardButton("🔙 Back", callback_data="step_type_selection")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_button_options_keyboard():
    """Creates keyboard for button options"""
    keyboard = [
        [InlineKeyboardButton("🔘 Simple Button", callback_data="button_simple")],
        [InlineKeyboardButton("🔗 URL Button", callback_data="button_url")],
        [InlineKeyboardButton("📞 Contact Button", callback_data="button_contact")],
        [InlineKeyboardButton("📍 Location Button", callback_data="button_location")],
        [InlineKeyboardButton("➕ Add More Buttons", callback_data="add_more_buttons")],
        [InlineKeyboardButton("✅ Finish Step", callback_data="finish_step")],
        [InlineKeyboardButton("🔙 Back", callback_data="step_type_selection")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_flow_control_keyboard():
    """Creates keyboard for flow control"""
    keyboard = [
        [InlineKeyboardButton("⏭️ Continue Flow", callback_data="continue_flow")],
        [InlineKeyboardButton("🏁 Finish Flow", callback_data="finish_flow")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_flows")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_step_preview_keyboard():
    """Creates keyboard for step preview"""
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Step", callback_data="confirm_step")],
        [InlineKeyboardButton("✏️ Edit Step", callback_data="edit_step")],
        [InlineKeyboardButton("🗑️ Delete Step", callback_data="delete_step")],
        [InlineKeyboardButton("🔙 Back", callback_data="step_type_selection")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_flow_content(flow_id):
    """Obtém o conteúdo completo de um fluxo"""
    flow_manager = FlowManager()
    steps = flow_manager.get_flow_steps(flow_id)
    
    content = []
    for step in steps:
        step_content = {
            'type': step['step_type'],
            'content': step['content'],
            'media_url': step['media_url'],
            'buttons': []
        }
        
        # Adicionar botões se existirem
        if step['button_id']:
            button = {
                'text': step['button_text'],
                'type': step['button_type'],
                'data': step['button_data']
            }
            step_content['buttons'].append(button)
        
        content.append(step_content)
    
    return content

def create_default_flow_keyboard(flows):
    """Cria teclado para seleção de fluxo padrão"""
    keyboard = []
    
    for flow in flows:
        # Criar texto do botão
        button_text = f"📋 {flow['name']}"
        if flow['is_default']:
            button_text += " ⭐"
        if flow['step_count'] > 0:
            button_text += f" ({flow['step_count']} etapas)"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"set_default_{flow['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="admin_menu")])
    return InlineKeyboardMarkup(keyboard)

def create_delete_flow_keyboard(flows):
    """Cria teclado para deletar fluxos"""
    keyboard = []
    for flow in flows:
        keyboard.append([InlineKeyboardButton(f"🗑️ {flow['name']}", callback_data=f"delete_flow_{flow['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")])
    return InlineKeyboardMarkup(keyboard)

def create_config_keyboard():
    """Creates keyboard for settings menu"""
    keyboard = [
        [InlineKeyboardButton("📱 Collect Phone Number", callback_data="config_phone")],
        [InlineKeyboardButton("📧 Collect Email", callback_data="config_email")],
        [InlineKeyboardButton("👤 Require Signup", callback_data="config_require_signup")],
        [InlineKeyboardButton("🎬 Welcome Message", callback_data="config_welcome")],
        [InlineKeyboardButton("🔗 Webhook CRM", callback_data="config_webhook")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_config_phone_keyboard():
    """Creates keyboard for phone collection configuration"""
    keyboard = [
        [InlineKeyboardButton("✅ Enable Phone Collection", callback_data="config_phone_enable")],
        [InlineKeyboardButton("❌ Disable Phone Collection", callback_data="config_phone_disable")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_config_email_keyboard():
    """Creates keyboard for email collection configuration"""
    keyboard = [
        [InlineKeyboardButton("✅ Enable Email Collection", callback_data="config_email_enable")],
        [InlineKeyboardButton("❌ Disable Email Collection", callback_data="config_email_disable")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_config_signup_keyboard():
    """Creates keyboard for signup requirement configuration"""
    keyboard = [
        [InlineKeyboardButton("✅ Enable Require Signup", callback_data="config_signup_enable")],
        [InlineKeyboardButton("❌ Disable Require Signup", callback_data="config_signup_disable")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_config_welcome_keyboard():
    """Creates keyboard for welcome message configuration"""
    welcome_enabled = get_config_value('welcome_enabled', 'false').lower() == 'true'
    welcome_media = get_config_value('welcome_media_url', '')
    welcome_text = get_config_value('welcome_text', '')
    welcome_media_type = get_config_value('welcome_media_type', '')
    
    keyboard = []
    
    if welcome_enabled:
        keyboard.append([InlineKeyboardButton("❌ Disable Message", callback_data="config_welcome_disable")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Enable Message", callback_data="config_welcome_enable")])
    
    keyboard.append([InlineKeyboardButton("📝 Edit Text", callback_data="config_welcome_text")])
    
    # Media options separated
    keyboard.append([InlineKeyboardButton("🖼️ Set Photo", callback_data="config_welcome_photo")])
    keyboard.append([InlineKeyboardButton("🎬 Set Video", callback_data="config_welcome_video")])
    keyboard.append([InlineKeyboardButton("⭕ Set Video Note", callback_data="config_welcome_video_note")])
    
    if welcome_media:
        media_type_text = {
            'photo': '🖼️ Photo',
            'video': '🎬 Video', 
            'video_note': '⭕ Video Note',
            'document': '📄 Document'
        }.get(welcome_media_type, '📁 File')
        
        keyboard.append([InlineKeyboardButton(f"🗑️ Remove {media_type_text}", callback_data="config_welcome_remove_media")])
    
    keyboard.append([InlineKeyboardButton("👁️ Preview", callback_data="config_welcome_preview")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_config")])
    
    return InlineKeyboardMarkup(keyboard)

def is_welcome_enabled():
    """Checks if welcome message is enabled"""
    return get_config_value('welcome_enabled', 'false').lower() == 'true'

def get_welcome_message():
    """Gets the configured welcome message"""
    return {
        'text': get_config_value('welcome_text', ''),
        'media_url': get_config_value('welcome_media_url', ''),
        'media_type': get_config_value('welcome_media_type', '')
    }

async def send_welcome_message(update, context):
    """Envia a mensagem de boas-vindas configurada"""
    if not is_welcome_enabled():
        return False
    
    welcome_data = get_welcome_message()
    
    if not welcome_data['text'] and not welcome_data['media_url']:
        return False
    
    try:
        if welcome_data['media_url']:
            # Enviar mídia com texto
            if welcome_data['media_type'] == 'photo':
                await update.message.reply_photo(
                    photo=welcome_data['media_url'],
                    caption=welcome_data['text'] if welcome_data['text'] else None
                )
            elif welcome_data['media_type'] == 'video':
                await update.message.reply_video(
                    video=welcome_data['media_url'],
                    caption=welcome_data['text'] if welcome_data['text'] else None
                )
            elif welcome_data['media_type'] == 'video_note':
                # Para vídeo redondo, enviar primeiro o vídeo e depois o texto separadamente
                await update.message.reply_video_note(
                    video_note=welcome_data['media_url']
                )
                # Enviar texto separadamente após o vídeo redondo
                if welcome_data['text']:
                    await update.message.reply_text(welcome_data['text'])
            else:
                # Fallback para arquivo local
                if welcome_data['media_url'].startswith('uploads/') or welcome_data['media_url'].startswith('uploads\\'):
                    with open(welcome_data['media_url'], 'rb') as f:
                        file_data = f.read()
                    
                    if welcome_data['media_type'] == 'photo':
                        await update.message.reply_photo(
                            photo=file_data,
                            caption=welcome_data['text'] if welcome_data['text'] else None
                        )
                    elif welcome_data['media_type'] == 'video':
                        await update.message.reply_video(
                            video=file_data,
                            caption=welcome_data['text'] if welcome_data['text'] else None
                        )
                    elif welcome_data['media_type'] == 'video_note':
                        # Para vídeo redondo local, enviar primeiro o vídeo e depois o texto
                        await update.message.reply_video_note(
                            video_note=file_data
                        )
                        if welcome_data['text']:
                            await update.message.reply_text(welcome_data['text'])
                    else:
                        # Enviar como documento
                        await update.message.reply_document(
                            document=file_data,
                            caption=welcome_data['text'] if welcome_data['text'] else None
                        )
        else:
            # Enviar apenas texto
            await update.message.reply_text(welcome_data['text'])
        
        return True
        
    except Exception as e:
        print(f"Erro ao enviar mensagem de boas-vindas: {e}")
        return False

async def send_welcome_video_note_for_signup(update, context):
    """Envia vídeo redondo de boas-vindas específico para cadastro"""
    user = update.effective_user
    print(f"🔍 DEBUG: send_welcome_video_note_for_signup - Iniciando para usuário {user.id}")
    
    if not is_welcome_enabled():
        print(f"🔍 DEBUG: Mensagem de boas-vindas não está habilitada")
        return False
    
    welcome_data = get_welcome_message()
    print(f"🔍 DEBUG: Dados da mensagem de boas-vindas: {welcome_data}")
    
    # Só enviar se for vídeo (normal ou redondo)
    if welcome_data['media_type'] not in ['video', 'video_note'] or not welcome_data['media_url']:
        print(f"🔍 DEBUG: Não é vídeo ou não tem URL - Tipo: {welcome_data['media_type']}, URL: {welcome_data['media_url']}")
        return False
    
    # Verificar se o usuário já recebeu o vídeo
    user = update.effective_user
    print(f"🔍 DEBUG: Verificando se usuário {user.id} já recebeu o vídeo")
    has_received = has_user_received_welcome_video(user.id)
    print(f"🔍 DEBUG: Usuário {user.id} já recebeu vídeo: {has_received}")
    if has_received:
        print(f"🔍 DEBUG: Usuário {user.id} já recebeu o vídeo redondo de boas-vindas")
        return False
    
    try:
        # Enviar vídeo (normal ou redondo)
        if welcome_data['media_url'].startswith('uploads/') or welcome_data['media_url'].startswith('uploads\\'):
            # Arquivo local
            # Verificar se o arquivo existe
            if not os.path.exists(welcome_data['media_url']):
                print(f"❌ Arquivo não encontrado: {welcome_data['media_url']}")
                return False
            
            # Enviar baseado no tipo de vídeo
            if welcome_data['media_type'] == 'video_note':
                # Enviar como video_note
                await update.message.reply_video_note(
                    video_note=open(welcome_data['media_url'], 'rb')
                )
            else:
                # Enviar como vídeo normal
                await update.message.reply_video(
                    video=open(welcome_data['media_url'], 'rb'),
                    caption=welcome_data['text'] if welcome_data['text'] else None
                )
        else:
            # URL remota
            if welcome_data['media_type'] == 'video_note':
                await update.message.reply_video_note(video_note=welcome_data['media_url'])
            else:
                await update.message.reply_video(
                    video=welcome_data['media_url'],
                    caption=welcome_data['text'] if welcome_data['text'] else None
                )
        
        # Enviar texto separadamente se for video_note e tiver texto
        if welcome_data['media_type'] == 'video_note' and welcome_data['text']:
            await update.message.reply_text(welcome_data['text'])
        
        # Marcar que o usuário já recebeu o vídeo
        mark_welcome_video_sent(user.id)
        print(f"🔍 DEBUG: Vídeo de boas-vindas enviado para usuário {user.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar vídeo redondo de boas-vindas para cadastro: {e}")
        return False

def get_config_value(config_key, default=None):
    """Obtém o valor de uma configuração do banco de dados"""
    connection = create_connection()
    if connection is None:
        return default
    
    try:
        cursor = connection.cursor()
        
        query = "SELECT config_value FROM bot_config WHERE config_key = %s"
        cursor.execute(query, (config_key,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            return default
            
    except Error as e:
        print(f"Erro ao obter configuração '{config_key}': {e}")
        return default
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def set_config_value(config_key, config_value):
    """Define o valor de uma configuração no banco de dados"""
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Verificar se a configuração já existe
        check_query = "SELECT id FROM bot_config WHERE config_key = %s"
        cursor.execute(check_query, (config_key,))
        exists = cursor.fetchone()
        
        if exists:
            # Atualizar configuração existente
            update_query = "UPDATE bot_config SET config_value = %s WHERE config_key = %s"
            cursor.execute(update_query, (config_value, config_key))
        else:
            # Inserir nova configuração
            insert_query = "INSERT INTO bot_config (config_key, config_value) VALUES (%s, %s)"
            cursor.execute(insert_query, (config_key, config_value))
        
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao definir configuração '{config_key}': {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def is_phone_collection_enabled():
    """Verifica se a coleta de número está ativada"""
    return get_config_value('collect_phone', 'false').lower() == 'true'

def is_email_collection_enabled():
    """Verifica se a coleta de email está ativada"""
    return get_config_value('collect_email', 'false').lower() == 'true'

def is_signup_required():
    """Verifica se o cadastro é obrigatório"""
    return get_config_value('require_signup', 'false').lower() == 'true'

def create_webhook_keyboard():
    """Creates keyboard for webhook configuration"""
    webhook_enabled = is_webhook_enabled()
    webhook_url = get_webhook_url()
    
    keyboard = []
    
    if webhook_enabled:
        keyboard.append([InlineKeyboardButton("❌ Disable Webhook", callback_data="webhook_disable")])
        if webhook_url:
            keyboard.append([InlineKeyboardButton("✏️ Change URL", callback_data="webhook_change_url")])
        else:
            keyboard.append([InlineKeyboardButton("🔗 Set URL", callback_data="webhook_set_url")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Enable Webhook", callback_data="webhook_enable")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_config")])
    return InlineKeyboardMarkup(keyboard)

def is_webhook_enabled():
    """Checks if webhook is enabled"""
    return get_config_value('webhook_enabled', 'false').lower() == 'true'

def get_webhook_url():
    """Gets the webhook URL"""
    return get_config_value('webhook_url', '')

def get_webhook_events():
    """Gets active webhook events"""
    events = get_config_value('webhook_events', 'bot_access,cadastro_concluido')
    return events.split(',')

def is_webhook_already_sent(telegram_id, event_type):
    """Checks if webhook was already sent to the user"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        if event_type == 'bot_access':
            cursor.execute("SELECT webhook_bot_access_sent FROM users WHERE telegram_id = %s", (telegram_id,))
        elif event_type == 'cadastro_concluido':
            cursor.execute("SELECT webhook_cadastro_sent FROM users WHERE telegram_id = %s", (telegram_id,))
        else:
            return False
        
        result = cursor.fetchone()
        return result[0] if result else False
        
    except Error as e:
        print(f"❌ Error checking webhook sent: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def mark_webhook_as_sent(telegram_id, event_type):
    """Marks webhook as sent to the user"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        if event_type == 'bot_access':
            cursor.execute("""
                UPDATE users 
                SET webhook_bot_access_sent = TRUE, webhook_sent_at = NOW() 
                WHERE telegram_id = %s
            """, (telegram_id,))
        elif event_type == 'cadastro_concluido':
            cursor.execute("""
                UPDATE users 
                SET webhook_cadastro_sent = TRUE, webhook_sent_at = NOW() 
                WHERE telegram_id = %s
            """, (telegram_id,))
        else:
            return False
        
        connection.commit()
        print(f"✅ Webhook {event_type} marked as sent for user {telegram_id}")
        return True
        
    except Error as e:
        print(f"❌ Error marking webhook as sent: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def send_webhook(event_type, user_data=None, flow_data=None):
    """Sends webhook to CRM"""
    if not is_webhook_enabled():
        return False
    
    webhook_url = get_webhook_url()
    if not webhook_url:
        return False
    
    # Check if event is active
    active_events = get_webhook_events()
    if event_type not in active_events:
        return False
    
    # For bot_access webhook, check if already sent
    if event_type == 'bot_access' and user_data and 'telegram_id' in user_data:
        if is_webhook_already_sent(user_data['telegram_id'], 'bot_access'):
            print(f"🔗 Webhook bot_access already sent for user {user_data['telegram_id']}")
            return True
    
    # For cadastro_concluido webhook, check if already sent
    if event_type == 'cadastro_concluido' and user_data and 'telegram_id' in user_data:
        if is_webhook_already_sent(user_data['telegram_id'], 'cadastro_concluido'):
            print(f"🔗 Webhook cadastro_concluido already sent for user {user_data['telegram_id']}")
            return True
    
    try:
        import aiohttp
        import asyncio
        import json
        from datetime import datetime
        
        # Prepare webhook data
        webhook_data = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'bot_token': get_config_value('bot_token', ''),
            'user_data': user_data or {},
            'flow_data': flow_data or {}
        }
        
        # Send webhook asynchronously
        async def send_webhook_async():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        webhook_url,
                        json=webhook_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            print(f"✅ Webhook sent successfully: {event_type}")
                            
                            # Mark as sent if it's bot_access or cadastro_concluido
                            if event_type in ['bot_access', 'cadastro_concluido'] and user_data and 'telegram_id' in user_data:
                                mark_webhook_as_sent(user_data['telegram_id'], event_type)
                            
                            return True
                        else:
                            print(f"❌ Webhook error: {response.status}")
                            return False
            except Exception as e:
                print(f"❌ Error sending webhook: {e}")
                return False
        
        # Execute asynchronously
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async loop, create task
            asyncio.create_task(send_webhook_async())
        else:
            # If not, execute directly
            loop.run_until_complete(send_webhook_async())
        
        return True
        
    except Exception as e:
        print(f"❌ Error preparing webhook: {e}")
        return False

def create_stats_keyboard():
    """Creates keyboard for statistics menu"""
    keyboard = [
        [InlineKeyboardButton("📊 Full Report", callback_data="stats_full_report")],
        [InlineKeyboardButton("👥 Users Report", callback_data="stats_users_report")],
        [InlineKeyboardButton("📝 Flows Report", callback_data="stats_flows_report")],
        [InlineKeyboardButton("📈 General Stats", callback_data="stats_general")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_general_stats():
    """Gets general system statistics"""
    connection = create_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        
        # Count users
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = TRUE")
        total_users = cursor.fetchone()[0]
        
        # Count users with complete data
        cursor.execute("SELECT COUNT(*) FROM users WHERE name IS NOT NULL AND phone IS NOT NULL AND email IS NOT NULL")
        users_with_data = cursor.fetchone()[0]
        
        # Count flows
        cursor.execute("SELECT COUNT(*) FROM flows WHERE is_active = TRUE")
        total_flows = cursor.fetchone()[0]
        
        # Count steps
        cursor.execute("SELECT COUNT(*) FROM flow_steps WHERE is_active = TRUE")
        total_steps = cursor.fetchone()[0]
        
        # Count buttons
        cursor.execute("SELECT COUNT(*) FROM buttons WHERE is_active = TRUE")
        total_buttons = cursor.fetchone()[0]
        
        # Users by month (last 6 months)
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
            FROM users 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month DESC
        """)
        users_by_month = cursor.fetchall()
        
        return {
            'total_users': total_users,
            'users_with_data': users_with_data,
            'total_flows': total_flows,
            'total_steps': total_steps,
            'total_buttons': total_buttons,
            'users_by_month': users_by_month
        }
        
    except Error as e:
        print(f"Error getting statistics: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_users_report_data():
    """Gets data for users report"""
    connection = create_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            telegram_id,
            username,
            first_name,
            last_name,
            name,
            phone,
            email,
            created_at,
            updated_at
        FROM users 
        WHERE is_active = TRUE
        ORDER BY created_at DESC
        """
        
        cursor.execute(query)
        return cursor.fetchall()
        
    except Error as e:
        print(f"Error getting users data: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def get_flows_report_data():
    """Gets data for flows report"""
    connection = create_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            f.id,
            f.name,
            f.description,
            f.is_default,
            f.created_at,
            f.updated_at,
            COUNT(fs.id) as step_count,
            COUNT(b.id) as button_count
        FROM flows f
        LEFT JOIN flow_steps fs ON f.id = fs.flow_id AND fs.is_active = TRUE
        LEFT JOIN buttons b ON fs.id = b.step_id AND b.is_active = TRUE
        WHERE f.is_active = TRUE
        GROUP BY f.id
        ORDER BY f.created_at DESC
        """
        
        cursor.execute(query)
        return cursor.fetchall()
        
    except Error as e:
        print(f"Error getting flows data: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def create_edit_flow_keyboard(flows):
    """Creates keyboard for flow selection to edit"""
    keyboard = []
    for flow in flows:
        keyboard.append([InlineKeyboardButton(f"✏️ {flow['name']}", callback_data=f"edit_flow_{flow['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_flows")])
    return InlineKeyboardMarkup(keyboard)

def create_edit_step_keyboard(flow_id):
    """Creates keyboard for editing flow steps"""
    # Use FlowManager to get steps
    flow_manager = FlowManager()
    steps = flow_manager.get_flow_steps(flow_id)
    keyboard = []
    
    for i, step in enumerate(steps, 1):
        step_type = step['step_type'].replace('_', ' ').title()
        keyboard.append([InlineKeyboardButton(f"📝 {i}. {step_type}", callback_data=f"edit_step_{step['id']}")])
    
    keyboard.append([InlineKeyboardButton("➕ Add Step", callback_data=f"add_step_{flow_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="edit_flow_list")])
    return InlineKeyboardMarkup(keyboard)

def get_step_details(step_id):
    """Gets complete details of a step"""
    connection = create_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT fs.*, f.name as flow_name
        FROM flow_steps fs
        JOIN flows f ON fs.flow_id = f.id
        WHERE fs.id = %s AND fs.is_active = TRUE
        """
        
        cursor.execute(query, (step_id,))
        step = cursor.fetchone()
        
        if step:
            # Buscar botões da etapa
            flow_manager = FlowManager()
            step['buttons'] = flow_manager.get_step_buttons(step_id)
        
        return step
        
    except Error as e:
        print(f"Erro ao obter detalhes da etapa: {e}")
        return None
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def update_step_content(step_id, content):
    """Atualiza o conteúdo de uma etapa"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        query = "UPDATE flow_steps SET content = %s WHERE id = %s"
        cursor.execute(query, (content, step_id))
        connection.commit()
        
        return True
        
    except Error as e:
        print(f"Erro ao atualizar etapa: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def update_step_media_url(step_id, media_url):
    """Atualiza a URL da mídia de uma etapa"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        query = "UPDATE flow_steps SET media_url = %s WHERE id = %s"
        cursor.execute(query, (media_url, step_id))
        connection.commit()
        
        return True
        
    except Error as e:
        print(f"Erro ao atualizar mídia da etapa: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def delete_step_completely(step_id):
    """Deleta uma etapa completamente (incluindo botões)"""
    connection = create_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Deletar botões primeiro
        cursor.execute("DELETE FROM buttons WHERE step_id = %s", (step_id,))
        
        # Deletar etapa
        cursor.execute("DELETE FROM flow_steps WHERE id = %s", (step_id,))
        
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao deletar etapa: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def generate_excel_report(report_type):
    """Gera relatório em Excel"""
    import pandas as pd
    from datetime import datetime
    import os
    
    try:
        if report_type == "users":
            data = get_users_report_data()
            if not data:
                return None
            
            df = pd.DataFrame(data)
            filename = f"relatorio_usuarios_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
        elif report_type == "flows":
            data = get_flows_report_data()
            if not data:
                return None
            
            df = pd.DataFrame(data)
            filename = f"relatorio_fluxos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
        elif report_type == "full":
            # Relatório completo com múltiplas abas
            users_data = get_users_report_data()
            flows_data = get_flows_report_data()
            stats_data = get_general_stats()
            
            if not users_data or not flows_data or not stats_data:
                return None
            
            filename = f"relatorio_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Aba de usuários
                df_users = pd.DataFrame(users_data)
                df_users.to_excel(writer, sheet_name='Usuários', index=False)
                
                # Aba de fluxos
                df_flows = pd.DataFrame(flows_data)
                df_flows.to_excel(writer, sheet_name='Fluxos', index=False)
                
                # Aba de estatísticas
                stats_df = pd.DataFrame([{
                    'Métrica': 'Total de Usuários',
                    'Valor': stats_data['total_users']
                }, {
                    'Métrica': 'Usuários com Dados Completos',
                    'Valor': stats_data['users_with_data']
                }, {
                    'Métrica': 'Total de Fluxos',
                    'Valor': stats_data['total_flows']
                }, {
                    'Métrica': 'Total de Etapas',
                    'Valor': stats_data['total_steps']
                }, {
                    'Métrica': 'Total de Botões',
                    'Valor': stats_data['total_buttons']
                }])
                stats_df.to_excel(writer, sheet_name='Estatísticas', index=False)
                
                # Aba de usuários por mês
                if stats_data['users_by_month']:
                    monthly_df = pd.DataFrame(stats_data['users_by_month'], columns=['Mês', 'Usuários'])
                    monthly_df.to_excel(writer, sheet_name='Usuários por Mês', index=False)
            
            return filename
        else:
            return None
        
        # Para relatórios simples (usuários ou fluxos)
        if report_type in ["users", "flows"]:
            df.to_excel(filename, index=False)
            return filename
        
    except Exception as e:
        print(f"Erro ao gerar relatório Excel: {e}")
        return None 

def has_user_received_welcome_video(telegram_id):
    """Verifica se o usuário já recebeu o vídeo redondo de boas-vindas"""
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        query = "SELECT welcome_video_sent FROM users WHERE telegram_id = %s"
        cursor.execute(query, (telegram_id,))
        result = cursor.fetchone()
        
        if result:
            return bool(result[0])
        else:
            return False
            
    except Error as e:
        print(f"Erro ao verificar vídeo de boas-vindas: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def mark_welcome_video_sent(telegram_id):
    """Marca que o usuário já recebeu o vídeo redondo de boas-vindas"""
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Verificar se o usuário existe
        check_query = "SELECT id FROM users WHERE telegram_id = %s"
        cursor.execute(check_query, (telegram_id,))
        user_exists = cursor.fetchone()
        
        if user_exists:
            # Atualizar campo welcome_video_sent
            update_query = "UPDATE users SET welcome_video_sent = TRUE WHERE telegram_id = %s"
            cursor.execute(update_query, (telegram_id,))
        else:
            # Inserir usuário com welcome_video_sent = TRUE
            insert_query = "INSERT INTO users (telegram_id, welcome_video_sent) VALUES (%s, TRUE)"
            cursor.execute(insert_query, (telegram_id,))
        
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao marcar vídeo de boas-vindas como enviado: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def reset_welcome_video_sent(telegram_id):
    """Reseta o controle de vídeo de boas-vindas para o usuário (para testes)"""
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        update_query = "UPDATE users SET welcome_video_sent = FALSE WHERE telegram_id = %s"
        cursor.execute(update_query, (telegram_id,))
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao resetar vídeo de boas-vindas: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close() 