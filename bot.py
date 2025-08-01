import os
import asyncio
import logging
import aiohttp
import aiofiles
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from mysql.connector import Error
from database import create_connection
from flow_manager import (
    FlowManager, 
    create_admin_keyboard, 
    create_flow_management_keyboard, 
    create_message_step_keyboard,
    create_simple_flow_control_keyboard,
    create_default_flow_keyboard,
    create_delete_flow_keyboard,
    create_edit_flow_keyboard,
    create_edit_step_keyboard,
    create_config_keyboard,
    create_config_phone_keyboard,
    create_config_email_keyboard,
    create_config_signup_keyboard,
    create_config_welcome_keyboard,
    create_webhook_keyboard,
    create_stats_keyboard,
    get_general_stats,
    generate_excel_report,
    get_step_details,
    update_step_content,
    update_step_media_url,
    delete_step_completely,
    get_config_value,
    set_config_value,
    is_phone_collection_enabled,
    is_email_collection_enabled,
    is_signup_required,
    is_welcome_enabled,
    get_welcome_message,
    send_welcome_message,
    is_webhook_enabled,
    get_webhook_url,
    send_webhook,
    is_webhook_already_sent,
    mark_webhook_as_sent,
    get_flow_content
)

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuração da pasta de uploads
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

async def download_and_save_file(file_url, file_type, file_id):
    """
    Baixa um arquivo do Telegram e salva localmente
    
    Args:
        file_url: URL do arquivo no Telegram
        file_type: Tipo do arquivo (image, video, video_note, document)
        file_id: ID do arquivo no Telegram
    
    Returns:
        str: Caminho local do arquivo salvo ou None se houver erro
    """
    try:
        # Criar pasta específica para o tipo de arquivo
        type_dir = UPLOADS_DIR / file_type
        type_dir.mkdir(exist_ok=True)
        
        # Gerar nome do arquivo baseado no file_id
        if file_type == 'image':
            extension = '.jpg'
        elif file_type == 'video':
            extension = '.mp4'
        elif file_type == 'video_note':
            extension = '.mp4'
        elif file_type == 'document':
            extension = '.pdf'  # Padrão, pode ser alterado
        else:
            extension = '.bin'
        
        filename = f"{file_id}{extension}"
        file_path = type_dir / filename
        
        # Garantir que o caminho use barras normais
        file_path = Path(str(file_path).replace('\\', '/'))
        
        # Verificar se o arquivo já existe
        if file_path.exists():
            print(f"Arquivo já existe: {file_path}")
            return str(file_path)
        
        # Baixar o arquivo
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    # Salvar o arquivo
                    async with aiofiles.open(file_path, 'wb') as f:
                        await f.write(await response.read())
                    
                    print(f"Arquivo salvo: {file_path}")
                    return str(file_path)
                else:
                    print(f"Erro ao baixar arquivo: HTTP {response.status}")
                    return None
                    
    except Exception as e:
        print(f"Erro ao baixar e salvar arquivo: {e}")
        return None

def normalize_path(path):
    """Normaliza o caminho do arquivo para usar barras normais"""
    return str(path).replace('\\', '/')

# Função para validar requisitos do video note
async def validate_video_note_requirements(file_data, file_path=None):
    """
    Valida se o video note atende aos requisitos obrigatórios do Telegram:
    - Formato Quadrado (1:1 aspect ratio)
    - Duração Máxima: 60 segundos
    - Tamanho Máximo: 100MB para bots
    - Codec: H.264/MPEG-4
    - Resolução recomendada: 512x512 px
    """
    try:
        import cv2
        import tempfile
        from moviepy.editor import VideoFileClip
        
        print(f"🔍 DEBUG: Iniciando validação de video note")
        
        # Verificar tamanho do arquivo
        file_size = len(file_data) if file_data else os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        print(f"🔍 DEBUG: Tamanho do arquivo: {file_size_mb:.2f} MB")
        
        if file_size_mb > 100:
            return False, f"❌ Tamanho do arquivo ({file_size_mb:.2f} MB) excede o limite de 100MB para bots"
        
        # Criar arquivo temporário para análise
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            if file_data:
                temp_file.write(file_data)
            else:
                with open(file_path, 'rb') as f:
                    temp_file.write(f.read())
            temp_file_path = temp_file.name
        
        try:
            # Verificar duração
            video_clip = VideoFileClip(temp_file_path)
            duration = video_clip.duration
            
            print(f"🔍 DEBUG: Duração do vídeo: {duration:.2f} segundos")
            
            if duration > 60:
                video_clip.close()
                return False, f"❌ Duração do vídeo ({duration:.2f}s) excede o limite de 60 segundos"
            
            # Verificar dimensões
            width = video_clip.w
            height = video_clip.h
            
            print(f"🔍 DEBUG: Dimensões do vídeo: {width}x{height}")
            
            # Verificar se é quadrado (1:1 aspect ratio)
            aspect_ratio = width / height
            if not (0.95 <= aspect_ratio <= 1.05):  # Permitir pequena tolerância
                video_clip.close()
                return False, f"❌ Vídeo não é quadrado (aspect ratio: {aspect_ratio:.2f}). Deve ser 1:1"
            
            # Verificar resolução recomendada (512x512)
            if width < 256 or height < 256:
                video_clip.close()
                return False, f"❌ Resolução muito baixa ({width}x{height}). Recomendado: 512x512"
            
            # Verificar codec usando OpenCV
            cap = cv2.VideoCapture(temp_file_path)
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec_name = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            cap.release()
            
            print(f"🔍 DEBUG: Codec detectado: {codec_name}")
            
            # Verificar se é H.264/MPEG-4
            # Aceitar variações do codec H.264 (h264, H264, avc1, etc.)
            h264_variants = ['avc1', 'H264', 'h264', 'mp4v', 'XVID', 'mp4a']
            if codec_name.lower() not in [codec.lower() for codec in h264_variants]:
                video_clip.close()
                return False, f"❌ Codec não suportado: {codec_name}. Use H.264/MPEG-4"
            
            video_clip.close()
            
            print(f"🔍 DEBUG: ✅ Video note atende a todos os requisitos")
            return True, "✅ Video note válido"
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except ImportError as e:
        print(f"🔍 DEBUG: Bibliotecas de validação não disponíveis: {e}")
        # Se as bibliotecas não estiverem disponíveis, fazer validação básica
        file_size = len(file_data) if file_data else os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        if file_size_mb > 100:
            return False, f"❌ Tamanho do arquivo ({file_size_mb:.2f} MB) excede o limite de 100MB para bots"
        
        return True, "✅ Validação básica passou (bibliotecas não disponíveis)"
        
    except Exception as e:
        print(f"🔍 DEBUG: Erro na validação: {e}")
        return False, f"❌ Erro na validação: {str(e)}"

# Função para converter vídeo para formato de video note
async def convert_video_to_video_note(file_data, file_path=None):
    """
    Converte um vídeo para o formato de video note do Telegram:
    - Redimensiona para 512x512 (quadrado)
    - Limita duração para 60 segundos
    - Converte para H.264/MPEG-4
    - Comprime para menos de 100MB
    """
    try:
        import cv2
        import tempfile
        from moviepy.editor import VideoFileClip, CompositeVideoClip
        from moviepy.video.fx import resize
        
        print(f"🔧 DEBUG: Iniciando conversão de vídeo para video note")
        
        # Criar arquivo temporário para processamento
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_input:
            if file_data:
                temp_input.write(file_data)
            else:
                with open(file_path, 'rb') as f:
                    temp_input.write(f.read())
            temp_input_path = temp_input.name
        
        # Criar arquivo temporário para saída
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_output:
            temp_output_path = temp_output.name
        
        try:
            # Carregar vídeo
            video_clip = VideoFileClip(temp_input_path)
            
            # Verificar duração e cortar se necessário
            if video_clip.duration > 60:
                print(f"🔧 DEBUG: Cortando vídeo de {video_clip.duration:.2f}s para 60s")
                video_clip = video_clip.subclip(0, 60)
            
            # Redimensionar para 512x512 (quadrado)
            print(f"🔧 DEBUG: Redimensionando de {video_clip.w}x{video_clip.h} para 512x512")
            video_clip = video_clip.resize((512, 512))
            
            # Configurar codec e qualidade para otimizar tamanho
            video_clip.write_videofile(
                temp_output_path,
                codec='libx264',
                audio_codec='aac',
                bitrate='400k',  # Bitrate ainda mais baixo para garantir < 100MB
                fps=20,  # FPS reduzido para economizar espaço
                preset='ultrafast',  # Preset rápido
                threads=2,
                ffmpeg_params=['-crf', '28']  # Compressão adicional
            )
            
            video_clip.close()
            
            # Verificar tamanho do arquivo convertido
            converted_size = os.path.getsize(temp_output_path)
            converted_size_mb = converted_size / (1024 * 1024)
            
            print(f"🔧 DEBUG: Arquivo convertido: {converted_size_mb:.2f} MB")
            
            # Se ainda estiver muito grande, comprimir mais
            if converted_size_mb > 100:
                print(f"🔧 DEBUG: Comprimindo mais para reduzir tamanho...")
                
                # Ler o arquivo convertido
                with open(temp_output_path, 'rb') as f:
                    video_data = f.read()
                
                # Tentar com bitrate ainda menor
                video_clip = VideoFileClip(temp_output_path)
                video_clip.write_videofile(
                    temp_output_path,
                    codec='libx264',
                    audio_codec='aac',
                    bitrate='250k',  # Bitrate ainda menor
                    fps=18,  # FPS ainda menor
                    preset='ultrafast',
                    threads=2,
                    ffmpeg_params=['-crf', '30']  # Compressão mais agressiva
                )
                video_clip.close()
                
                # Verificar tamanho final
                final_size = os.path.getsize(temp_output_path)
                final_size_mb = final_size / (1024 * 1024)
                print(f"🔧 DEBUG: Tamanho final após compressão: {final_size_mb:.2f} MB")
                
                if final_size_mb > 100:
                    print(f"🔧 DEBUG: Ainda muito grande, tentando sem áudio...")
                    # Tentar sem áudio
                    video_clip = VideoFileClip(temp_output_path)
                    video_clip.write_videofile(
                        temp_output_path,
                        codec='libx264',
                        audio=False,  # Sem áudio
                        bitrate='150k',  # Bitrate muito baixo
                        fps=15,
                        preset='ultrafast',
                        threads=2,
                        ffmpeg_params=['-crf', '32', '-movflags', '+faststart']  # Compressão máxima + otimização
                    )
                    video_clip.close()
            
            # Ler o arquivo convertido
            with open(temp_output_path, 'rb') as f:
                converted_data = f.read()
            
            final_size_mb = len(converted_data) / (1024 * 1024)
            print(f"🔧 DEBUG: ✅ Conversão concluída: {final_size_mb:.2f} MB")
            
            return True, converted_data, f"✅ Vídeo convertido com sucesso ({final_size_mb:.2f} MB)"
            
        finally:
            # Limpar arquivos temporários
            if os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)
                
    except ImportError as e:
        print(f"🔧 DEBUG: Bibliotecas de conversão não disponíveis: {e}")
        return False, None, "❌ Bibliotecas de conversão não disponíveis"
        
    except Exception as e:
        print(f"🔧 DEBUG: Erro na conversão: {e}")
        return False, None, f"❌ Erro na conversão: {str(e)}"

# Função para criar as tabelas
def create_tables():
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Criar tabela bot_config
        create_bot_config_table = """
        CREATE TABLE IF NOT EXISTS bot_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        
        # Criar tabela users
        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT NOT NULL UNIQUE,
            username VARCHAR(100),
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            name VARCHAR(200),
            phone VARCHAR(20),
            email VARCHAR(200),
            additional_data TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            welcome_video_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
        
        cursor.execute(create_bot_config_table)
        cursor.execute(create_users_table)
        connection.commit()
        
        print("Tabelas criadas com sucesso!")
        return True
        
    except Error as e:
        print(f"Erro ao criar tabelas: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Função para inserir/atualizar usuário
def save_user(telegram_id, username=None, first_name=None, last_name=None):
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Verificar se o usuário já existe
        check_user = "SELECT id FROM users WHERE telegram_id = %s"
        cursor.execute(check_user, (telegram_id,))
        user_exists = cursor.fetchone()
        
        if user_exists:
            # Atualizar usuário existente
            update_user = """
            UPDATE users 
            SET username = %s, first_name = %s, last_name = %s, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = %s
            """
            cursor.execute(update_user, (username, first_name, last_name, telegram_id))
        else:
            # Inserir novo usuário
            insert_user = """
            INSERT INTO users (telegram_id, username, first_name, last_name)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_user, (telegram_id, username, first_name, last_name))
        
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao salvar usuário: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# Handlers do bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user = update.effective_user
    
    # Salvar usuário no banco de dados
    save_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Enviar webhook de acesso ao bot
    user_data = {
        'telegram_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    send_webhook('bot_access', user_data)
    
    # Verificar configurações de coleta de dados
    require_signup = is_signup_required()
    collect_phone = is_phone_collection_enabled()
    collect_email = is_email_collection_enabled()
    
    print(f"🔍 DEBUG: start - Usuário {user.id} - Configurações:")
    print(f"🔍 DEBUG: require_signup: {require_signup}")
    print(f"🔍 DEBUG: collect_phone: {collect_phone}")
    print(f"🔍 DEBUG: collect_email: {collect_email}")
    
    # Verificar se o usuário precisa de cadastro
    needs_signup = require_signup or collect_phone or collect_email
    print(f"🔍 DEBUG: needs_signup: {needs_signup}")
    
    # Verificar se existe um fluxo padrão
    flow_manager = FlowManager()
    default_flow = flow_manager.get_default_flow()
    print(f"🔍 DEBUG: default_flow: {default_flow}")
    
    if needs_signup:
        # Verificar se o usuário já tem as informações necessárias
        user_data = get_user_data(user.id)
        print(f"🔍 DEBUG: Dados do usuário {user.id}: {user_data}")
        
        missing_data = []
        if require_signup and not user_data.get('name'):
            missing_data.append("nome")
        if collect_phone and not user_data.get('phone'):
            missing_data.append("telefone")
        if collect_email and not user_data.get('email'):
            missing_data.append("email")
        
        print(f"🔍 DEBUG: Dados faltantes: {missing_data}")
        
        if missing_data:
            # Se há dados faltantes, enviar vídeo redondo específico para cadastro
            # (não enviar mensagem de boas-vindas geral)
            await request_missing_data(update, context, missing_data)
            return
        else:
            # Se não há dados faltantes, verificar se há fluxo padrão
            if default_flow:
                # Executar o fluxo padrão completo
                steps = flow_manager.get_flow_steps(default_flow['id'])
                if steps:
                    await execute_complete_flow(update, steps)
                    return
            else:
                # Se não há fluxo padrão, enviar mensagem de boas-vindas normal
                await send_welcome_message(update, context)
    else:
        # Se não precisa de cadastro, verificar se há fluxo padrão
        if default_flow:
            # Executar o fluxo padrão completo
            steps = flow_manager.get_flow_steps(default_flow['id'])
            if steps:
                await execute_complete_flow(update, steps)
                return
        else:
            # Se não há fluxo padrão, enviar mensagem de boas-vindas normal
            await send_welcome_message(update, context)
    
    # Se chegou até aqui, não há fluxo padrão nem cadastro necessário
    # Mostrar mensagem de boas-vindas padrão
    welcome_message = f"""
    👋 Olá {user.first_name}!
    
    Bem-vindo ao Bot Influenciador! 🚀
    
    Comandos disponíveis:
    /start - Iniciar o bot
    /help - Ver ajuda
    /status - Ver status do bot
    /admin - Painel de administração (apenas admins)
    
    Como posso te ajudar hoje?
    """
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    help_text = """
    🤖 **Bot Influenciador - Ajuda**
    
    **Comandos disponíveis:**
    /start - Iniciar o bot
    /help - Ver esta mensagem de ajuda
    /status - Ver status do bot
    
    **Funcionalidades:**
    - Gerenciamento de usuários
    - Configurações personalizáveis
    - Sistema de influenciadores
    
    Para mais informações, entre em contato com o administrador.
    """
    
    await update.message.reply_text(help_text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status"""
    connection = create_connection()
    if connection is None:
        await update.message.reply_text("❌ Erro: Não foi possível conectar ao banco de dados.")
        return
    
    try:
        cursor = connection.cursor()
        
        # Contar usuários
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        # Verificar configurações
        cursor.execute("SELECT COUNT(*) FROM bot_config")
        config_count = cursor.fetchone()[0]
        
        status_message = f"""
        📊 **Status do Bot**
        
        ✅ Banco de dados: Conectado
        👥 Usuários registrados: {user_count}
        ⚙️ Configurações: {config_count}
        
        Bot funcionando normalmente! 🚀
        """
        
        await update.message.reply_text(status_message)
        
    except Error as e:
        await update.message.reply_text(f"❌ Erro ao verificar status: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eco de mensagens"""
    await update.message.reply_text(f"Você disse: {update.message.text}")

async def handle_contact_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar dados de contato e localização compartilhados"""
    user = update.effective_user
    

    
    # Verificar se está esperando por contato
    if 'waiting_for_contact' in context.user_data and context.user_data['waiting_for_contact']:
        contact = update.message.contact
        
        if contact and contact.phone_number:
            # Processar telefone compartilhado
            context.user_data['collected_phone'] = contact.phone_number
            context.user_data.pop('waiting_for_contact', None)
            

            
            # Voltar para a tela de coleta de dados para mostrar botões atualizados
            if 'missing_data' in context.user_data:
                missing_data = context.user_data['missing_data']
                await request_missing_data(update, context, missing_data)
            else:
                # Se não há mais dados, finalizar
                await finish_data_collection(update, context)
        else:
            await update.message.reply_text(
                "❌ Erro ao processar contato. Tente novamente.",
                reply_markup=ReplyKeyboardRemove()
            )
        return
    else:
        # Contato compartilhado mas não estava esperando

        
        if update.message.contact and update.message.contact.phone_number:
            # Processar telefone compartilhado mesmo assim
            context.user_data['collected_phone'] = update.message.contact.phone_number
            

            
            # Voltar para a tela de coleta de dados para mostrar botões atualizados
            if 'missing_data' in context.user_data:
                missing_data = context.user_data['missing_data']
                await request_missing_data(update, context, missing_data)
            else:
                # Se não há mais dados, finalizar
                await finish_data_collection(update, context)
        else:
            await update.message.reply_text(
                "❌ Erro ao processar contato. Tente novamente.",
                reply_markup=ReplyKeyboardRemove()
            )
        return
    


async def handle_media_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar mídias enviadas (fotos, vídeos, documentos)"""
    user = update.effective_user
    flow_manager = FlowManager()
    
    # Verificar se está configurando mídia da mensagem de boas-vindas
    if 'configuring_welcome_media' in context.user_data and context.user_data['configuring_welcome_media']:
        if not flow_manager.is_admin(user.id):
            return
        
        try:
            expected_type = context.user_data.get('welcome_media_type', '')
            media_type = None
            file_id = None
            file_url = None
            file_data = None
            
            # Processar foto
            if update.message.photo:
                if expected_type and expected_type != 'photo':
                    await update.message.reply_text(
                        f"❌ **Tipo de mídia incorreto.**\n\nEsperado: {expected_type}\nEnviado: foto\n\nEnvie o tipo correto de mídia.",
                        reply_markup=create_config_welcome_keyboard()
                    )
                    return
                
                media_type = 'photo'
                photo = update.message.photo[-1]  # Pegar a maior resolução
                file_id = photo.file_id
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
            # Processar vídeo
            elif update.message.video:
                if expected_type == 'video_note':
                    # Permitir vídeo normal para vídeo redondo (conversão automática)
                    media_type = 'video_note'
                elif expected_type and expected_type != 'video':
                    await update.message.reply_text(
                        f"❌ **Tipo de mídia incorreto.**\n\nEsperado: {expected_type}\nEnviado: vídeo\n\nEnvie o tipo correto de mídia.",
                        reply_markup=create_config_welcome_keyboard()
                    )
                    return
                else:
                    media_type = 'video'
                
                video = update.message.video
                file_id = video.file_id
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
            # Processar vídeo redondo
            elif update.message.video_note:
                if expected_type and expected_type != 'video_note':
                    await update.message.reply_text(
                        f"❌ **Tipo de mídia incorreto.**\n\nEsperado: {expected_type}\nEnviado: vídeo redondo\n\nEnvie o tipo correto de mídia.",
                        reply_markup=create_config_welcome_keyboard()
                    )
                    return
                
                media_type = 'video_note'
                video_note = update.message.video_note
                file_id = video_note.file_id
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
            # Processar documento
            elif update.message.document:
                if expected_type and expected_type != 'document':
                    await update.message.reply_text(
                        f"❌ **Tipo de mídia incorreto.**\n\nEsperado: {expected_type}\nEnviado: documento\n\nEnvie o tipo correto de mídia.",
                        reply_markup=create_config_welcome_keyboard()
                    )
                    return
                
                media_type = 'document'
                document = update.message.document
                file_id = document.file_id
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
            
            if media_type and file_id and file_url:
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, media_type, file_id)
                
                # Se for vídeo redondo e foi enviado um vídeo normal, converter
                if media_type == 'video_note' and update.message.video:
                    try:
                        # Baixar o arquivo para conversão
                        import requests
                        response = requests.get(file_url)
                        if response.status_code == 200:
                            file_data = response.content
                            
                            # Validar e converter para vídeo redondo
                            is_valid, validation_message = await validate_video_note_requirements(file_data)
                            if not is_valid:
                                await update.message.reply_text(
                                    f"⚠️ **Vídeo não atende aos requisitos:**\n\n{validation_message}\n\n"
                                    f"Deseja converter mesmo assim?",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("✅ Sim, converter", callback_data="convert_welcome_video_note")],
                                        [InlineKeyboardButton("❌ Cancelar", callback_data="config_welcome")]
                                    ])
                                )
                                # Salvar dados temporários para conversão
                                context.user_data['temp_welcome_video_data'] = {
                                    'file_data': file_data,
                                    'local_path': local_path,
                                    'file_url': file_url
                                }
                                return
                            
                            # Converter automaticamente
                            conversion_success, converted_data, conversion_message = await convert_video_to_video_note(file_data)
                            if conversion_success:
                                # Salvar o vídeo convertido
                                import os
                                from pathlib import Path
                                UPLOADS_DIR = Path("uploads")
                                video_note_dir = UPLOADS_DIR / "video_note"
                                video_note_dir.mkdir(parents=True, exist_ok=True)
                                
                                temp_filename = f"welcome_video_note_{file_id}.mp4"
                                temp_path = video_note_dir / temp_filename
                                
                                with open(temp_path, 'wb') as f:
                                    f.write(converted_data)
                                
                                local_path = str(temp_path)
                                await update.message.reply_text(
                                    f"✅ **Vídeo Redondo da Mensagem de Boas-vindas Configurado!**\n\n"
                                    f"O vídeo foi convertido automaticamente para formato redondo.\n"
                                    f"Arquivo: {local_path}",
                                    reply_markup=create_config_welcome_keyboard()
                                )
                            else:
                                await update.message.reply_text(
                                    f"❌ **Erro na conversão:** {conversion_message}\n\nTente novamente.",
                                    reply_markup=create_config_welcome_keyboard()
                                )
                                return
                        else:
                            await update.message.reply_text(
                                "❌ **Erro ao baixar vídeo para conversão.**\n\nTente novamente.",
                                reply_markup=create_config_welcome_keyboard()
                            )
                            return
                    except Exception as e:
                        await update.message.reply_text(
                            f"❌ **Erro na conversão:** {str(e)}\n\nTente novamente.",
                            reply_markup=create_config_welcome_keyboard()
                        )
                        return
                
                # Salvar configurações
                if set_config_value('welcome_media_url', local_path or file_url) and set_config_value('welcome_media_type', media_type):
                    context.user_data.pop('configuring_welcome_media', None)
                    context.user_data.pop('welcome_media_type', None)
                    context.user_data.pop('temp_welcome_video_data', None)
                    
                    media_type_text = {
                        'photo': '🖼️ Foto',
                        'video': '🎬 Vídeo',
                        'video_note': '⭕ Vídeo Redondo',
                        'document': '📄 Documento'
                    }.get(media_type, media_type)
                    
                    await update.message.reply_text(
                        f"✅ **{media_type_text} da Mensagem de Boas-vindas Configurado!**\n\n"
                        f"Tipo: {media_type}\n"
                        f"Arquivo: {local_path or file_url}",
                        reply_markup=create_config_welcome_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Erro ao salvar mídia da mensagem de boas-vindas.**\n\nTente novamente.",
                        reply_markup=create_config_welcome_keyboard()
                    )
            else:
                expected_type_text = {
                    'photo': 'foto',
                    'video': 'vídeo',
                    'video_note': 'vídeo redondo',
                    'document': 'documento'
                }.get(expected_type, 'mídia')
                
                await update.message.reply_text(
                    f"❌ **Tipo de mídia não suportado.**\n\nEnvie uma {expected_type_text}.",
                    reply_markup=create_config_welcome_keyboard()
                )
        except Exception as e:
            await update.message.reply_text(
                f"❌ **Erro ao processar mídia:** {str(e)}\n\nTente novamente.",
                reply_markup=create_config_welcome_keyboard()
            )
        return
    
    if not flow_manager.is_admin(user.id):
        return
    
    # Verificar se está configurando etapa
    if 'current_step_type' in context.user_data:
        step_type = context.user_data['current_step_type']
        
        if 'current_step_data' not in context.user_data:
            context.user_data['current_step_data'] = {}
        
        # Processar foto
        if update.message.photo and step_type in ['message_image', 'message_image_button']:
            photo = update.message.photo[-1]  # Pegar a maior resolução
            file_id = photo.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, 'image', file_id)
                
                # Salvar informações da mídia
                context.user_data['current_step_data']['media_url'] = local_path or file_url
                context.user_data['current_step_data']['type'] = 'image'
                context.user_data['current_step_data']['file_id'] = file_id  # Backup do file_id
                
                await update.message.reply_text(
                    "📝 **Digite o texto da imagem:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_image_text'] = True
                if step_type == 'message_image_button':
                    context.user_data['waiting_for_button'] = True
                    print(f"🔍 DEBUG: handle_media_input - step_type: {step_type}, waiting_for_button definido como True")
                else:
                    print(f"🔍 DEBUG: handle_media_input - step_type: {step_type}, waiting_for_button NÃO definido")
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo: {e}")
                # Em caso de erro, usar apenas o file_id
                context.user_data['current_step_data']['file_id'] = file_id
                context.user_data['current_step_data']['type'] = 'image'
                
                await update.message.reply_text(
                    "📝 **Digite o texto da imagem:**\n\n⚠️ **Aviso:** Houve um problema ao obter a URL da imagem, mas ela será salva usando o ID interno.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_image_text'] = True
                if step_type == 'message_image_button':
                    context.user_data['waiting_for_button'] = True
                return
        
        # Processar vídeo (normal ou para conversão para vídeo redondo)
        elif update.message.video and step_type in ['message_video', 'message_video_button', 'message_video_note', 'message_video_note_button']:
            video = update.message.video
            file_id = video.file_id
            
            # Determinar o tipo baseado no step_type
            if step_type in ['message_video_note', 'message_video_note_button']:
                target_type = 'video_note'
                message_text = "📝 **Digite o texto do vídeo redondo:**"
                waiting_flag = 'waiting_for_video_note_text'
            else:
                target_type = 'video'
                message_text = "📝 **Digite o texto do vídeo:**"
                waiting_flag = 'waiting_for_video_text'
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, target_type, file_id)
                
                # Salvar informações da mídia
                context.user_data['current_step_data']['media_url'] = local_path or file_url
                context.user_data['current_step_data']['type'] = target_type
                context.user_data['current_step_data']['file_id'] = file_id  # Backup do file_id
                
                # Marcar como vídeo original se for para vídeo redondo
                if step_type in ['message_video_note', 'message_video_note_button']:
                    context.user_data['current_step_data']['original_video'] = True
                
                await update.message.reply_text(
                    message_text,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data[waiting_flag] = True
                if step_type in ['message_video_button', 'message_video_note_button']:
                    context.user_data['waiting_for_button'] = True
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de vídeo: {e}")
                # Em caso de erro, usar apenas o file_id
                context.user_data['current_step_data']['file_id'] = file_id
                context.user_data['current_step_data']['type'] = target_type
                context.user_data['current_step_data']['original_video'] = True
                
                await update.message.reply_text(
                    f"{message_text}\n\n⚠️ **Aviso:** Houve um problema ao obter a URL do vídeo, mas ele será salvo usando o ID interno.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data[waiting_flag] = True
                if step_type in ['message_video_button', 'message_video_note_button']:
                    context.user_data['waiting_for_button'] = True
                return
        
        # Processar vídeo redondo
        elif update.message.video_note and step_type in ['message_video_note', 'message_video_note_button']:
            video_note = update.message.video_note
            file_id = video_note.file_id
            
            # Garantir que current_step_data existe
            if 'current_step_data' not in context.user_data:
                context.user_data['current_step_data'] = {}
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar arquivo para validação
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as response:
                        if response.status == 200:
                            file_data = await response.read()
                            
                            # Validar requisitos do video note
                            print(f"🔍 DEBUG: Validando requisitos do video note...")
                            is_valid, validation_message = await validate_video_note_requirements(file_data)
                            
                            if not is_valid:
                                # Oferecer conversão automática
                                await update.message.reply_text(
                                    f"❌ **Video Note Inválido**\n\n{validation_message}\n\n"
                                    "📋 **Requisitos obrigatórios:**\n"
                                    "• Formato quadrado (1:1)\n"
                                    "• Duração máxima: 60 segundos\n"
                                    "• Tamanho máximo: 100MB\n"
                                    "• Codec: H.264/MPEG-4\n"
                                    "• Resolução recomendada: 512x512px\n\n"
                                    "🔄 **Deseja converter automaticamente?**",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("✅ Sim, converter", callback_data="convert_video_note")],
                                        [InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")]
                                    ])
                                )
                                
                                # Salvar dados do vídeo para conversão
                                context.user_data['video_to_convert'] = {
                                    'file_data': file_data,
                                    'step_type': step_type
                                }
                                return
                            
                            print(f"🔍 DEBUG: {validation_message}")
                            
                            # Salvar arquivo localmente após validação
                            local_path = await download_and_save_file(file_url, 'video_note', file_id)
                            
                            # Salvar informações da mídia
                            context.user_data['current_step_data']['media_url'] = local_path or file_url
                            context.user_data['current_step_data']['type'] = 'video_note'
                            context.user_data['current_step_data']['file_id'] = file_id  # Backup do file_id
                            
                            await update.message.reply_text(
                                f"✅ **Video Note Válido!**\n\n{validation_message}\n\n"
                                "📝 **Digite o texto do vídeo redondo:**",
                                reply_markup=InlineKeyboardMarkup([[
                                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                                ]])
                            )
                            context.user_data['waiting_for_video_note_text'] = True
                            if step_type == 'message_video_note_button':
                                context.user_data['waiting_for_button'] = True
                            return
                        else:
                            raise Exception(f"HTTP {response.status}")
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de vídeo redondo: {e}")
                # Em caso de erro, usar apenas o file_id
                context.user_data['current_step_data']['file_id'] = file_id
                context.user_data['current_step_data']['type'] = 'video_note'
                
                await update.message.reply_text(
                    "📝 **Digite o texto do vídeo redondo:**\n\n⚠️ **Aviso:** Houve um problema ao obter a URL do vídeo redondo, mas ele será salvo usando o ID interno.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_video_note_text'] = True
                if step_type == 'message_video_note_button':
                    context.user_data['waiting_for_button'] = True
                return
        
        # Processar documento
        elif update.message.document and step_type in ['message_image', 'message_video', 'message_video_note', 'message_image_button', 'message_video_button', 'message_video_note_button']:
            document = update.message.document
            file_id = document.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                if step_type in ['message_image', 'message_image_button']:
                    media_type = 'image'
                elif step_type in ['message_video', 'message_video_button']:
                    media_type = 'video'
                elif step_type in ['message_video_note', 'message_video_note_button']:
                    media_type = 'video_note'
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, media_type, file_id)
                
                context.user_data['current_step_data']['media_url'] = local_path or file_url
                context.user_data['current_step_data']['type'] = media_type
                
                await update.message.reply_text(
                    f"📝 **Digite o texto do {media_type}:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data[f'waiting_for_{media_type}_text'] = True
                if step_type in ['message_image_button', 'message_video_button', 'message_video_note_button']:
                    context.user_data['waiting_for_button'] = True
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de documento: {e}")
                # Em caso de erro, usar apenas o file_id
                if step_type in ['message_image', 'message_image_button']:
                    media_type = 'image'
                elif step_type in ['message_video', 'message_video_button']:
                    media_type = 'video'
                elif step_type in ['message_video_note', 'message_video_note_button']:
                    media_type = 'video_note'
                
                context.user_data['current_step_data']['file_id'] = file_id
                context.user_data['current_step_data']['type'] = media_type
                
                await update.message.reply_text(
                    f"📝 **Digite o texto do {media_type}:**\n\n⚠️ **Aviso:** Houve um problema ao obter a URL do arquivo, mas ele será salvo usando o ID interno.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data[f'waiting_for_{media_type}_text'] = True
                if step_type in ['message_image_button', 'message_video_button', 'message_video_note_button']:
                    context.user_data['waiting_for_button'] = True
                return
    
    # Verificar se está editando mídia de etapa
    if 'editing_step_media' in context.user_data and context.user_data['editing_step_media']:
        step_id = context.user_data['editing_step_id']
        
        # Processar foto para edição
        if update.message.photo:
            photo = update.message.photo[-1]  # Pegar a maior resolução
            file_id = photo.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, 'image', file_id)
                
                if update_step_media_url(step_id, local_path or file_url):
                    context.user_data.pop('editing_step_media', None)
                    context.user_data.pop('editing_step_id', None)
                    
                    await update.message.reply_text(
                        "✅ **Mídia da Etapa Atualizada!**\n\nA nova imagem foi salva com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                else:
                    await update.message.reply_text(
                        "❌ Erro ao atualizar mídia da etapa.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo para edição: {e}")
                await update.message.reply_text(
                    "❌ **Erro ao processar imagem!**\n\nHouve um problema de conexão. Tente novamente ou envie uma imagem menor.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
                return
        
        # Processar vídeo para edição
        elif update.message.video:
            video = update.message.video
            file_id = video.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, 'video', file_id)
                
                if update_step_media_url(step_id, local_path or file_url):
                    context.user_data.pop('editing_step_media', None)
                    context.user_data.pop('editing_step_id', None)
                    
                    await update.message.reply_text(
                        "✅ **Mídia da Etapa Atualizada!**\n\nO novo vídeo foi salvo com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                else:
                    await update.message.reply_text(
                        "❌ Erro ao atualizar mídia da etapa.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de vídeo para edição: {e}")
                await update.message.reply_text(
                    "❌ **Erro ao processar vídeo!**\n\nHouve um problema de conexão. Tente novamente ou envie um vídeo menor.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
                return
        
        # Processar vídeo redondo para edição
        elif update.message.video_note:
            video_note = update.message.video_note
            file_id = video_note.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar arquivo para validação
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as response:
                        if response.status == 200:
                            file_data = await response.read()
                            
                            # Validar requisitos do video note
                            print(f"🔍 DEBUG: Validando requisitos do video note para edição...")
                            is_valid, validation_message = await validate_video_note_requirements(file_data)
                            
                            if not is_valid:
                                await update.message.reply_text(
                                    f"❌ **Video Note Inválido**\n\n{validation_message}\n\n"
                                    "📋 **Requisitos obrigatórios:**\n"
                                    "• Formato quadrado (1:1)\n"
                                    "• Duração máxima: 60 segundos\n"
                                    "• Tamanho máximo: 100MB\n"
                                    "• Codec: H.264/MPEG-4\n"
                                    "• Resolução recomendada: 512x512px",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                                    ]])
                                )
                                return
                            
                            print(f"🔍 DEBUG: {validation_message}")
                            
                            # Salvar arquivo localmente após validação
                            local_path = await download_and_save_file(file_url, 'video_note', file_id)
                            
                            if update_step_media_url(step_id, local_path or file_url):
                                context.user_data.pop('editing_step_media', None)
                                context.user_data.pop('editing_step_id', None)
                                
                                await update.message.reply_text(
                                    f"✅ **Mídia da Etapa Atualizada!**\n\n{validation_message}\n\nO novo vídeo redondo foi salvo com sucesso.",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                                    ]])
                                )
                            else:
                                await update.message.reply_text(
                                    "❌ Erro ao atualizar mídia da etapa.",
                                    reply_markup=InlineKeyboardMarkup([[
                                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                                    ]])
                                )
                            return
                        else:
                            raise Exception(f"HTTP {response.status}")
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de vídeo redondo para edição: {e}")
                await update.message.reply_text(
                    "❌ **Erro ao processar vídeo redondo!**\n\nHouve um problema de conexão. Tente novamente ou envie um vídeo menor.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
                return
        
        # Processar documento para edição
        elif update.message.document:
            document = update.message.document
            file_id = document.file_id
            
            try:
                # Obter URL do arquivo
                file = await context.bot.get_file(file_id)
                file_url = file.file_path
                
                # Verificar se a URL é válida
                if not file_url.startswith('http'):
                    file_url = f"https://api.telegram.org/file/bot{context.bot.token}/{file_url}"
                
                # Baixar e salvar arquivo localmente
                local_path = await download_and_save_file(file_url, 'document', file_id)
                
                if update_step_media_url(step_id, local_path or file_url):
                    context.user_data.pop('editing_step_media', None)
                    context.user_data.pop('editing_step_id', None)
                    
                    await update.message.reply_text(
                        "✅ **Mídia da Etapa Atualizada!**\n\nO novo arquivo foi salvo com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                else:
                    await update.message.reply_text(
                        "❌ Erro ao atualizar mídia da etapa.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
                return
                
            except Exception as e:
                print(f"🔍 DEBUG: Erro ao obter arquivo de documento para edição: {e}")
                await update.message.reply_text(
                    "❌ **Erro ao processar arquivo!**\n\nHouve um problema de conexão. Tente novamente ou envie um arquivo menor.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
                return

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para processar entrada de texto durante criação de fluxos"""
    user = update.effective_user
    text = update.message.text
    flow_manager = FlowManager()
    
    print(f"DEBUG: ENTRANDO NA FUNÇÃO handle_text_input - Texto: {text}")
    
    # Verificar se está configurando mensagem de boas-vindas
    if 'configuring_welcome_text' in context.user_data and context.user_data['configuring_welcome_text']:
        if set_config_value('welcome_text', text):
            context.user_data.pop('configuring_welcome_text', None)
            await update.message.reply_text(
                "✅ **Texto da Mensagem de Boas-vindas Salvo!**\n\n"
                f"Texto configurado:\n{text}",
                reply_markup=create_config_welcome_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ **Erro ao salvar texto da mensagem de boas-vindas.**\n\nTente novamente.",
                reply_markup=create_config_welcome_keyboard()
            )
        return
    
    # Verificar se está coletando dados do usuário (não apenas admins)
    if 'waiting_for_name' in context.user_data and context.user_data['waiting_for_name']:
        # Processar nome
        context.user_data['collected_name'] = text
        context.user_data.pop('waiting_for_name', None)
        
        # Remover teclado personalizado
        await update.message.reply_text(
            "✅ Nome salvo!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Voltar para a tela de coleta de dados para mostrar botões atualizados
        if 'missing_data' in context.user_data:
            missing_data = context.user_data['missing_data']
            await request_missing_data(update, context, missing_data)
        else:
            # Se não há mais dados, finalizar
            await finish_data_collection(update, context)
        return
    
    elif 'waiting_for_phone' in context.user_data and context.user_data['waiting_for_phone']:
        # Processar telefone
        context.user_data['collected_phone'] = text
        context.user_data.pop('waiting_for_phone', None)
        
        # Remover teclado personalizado
        await update.message.reply_text(
            "✅ Telefone salvo!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Voltar para a tela de coleta de dados para mostrar botões atualizados
        if 'missing_data' in context.user_data:
            missing_data = context.user_data['missing_data']
            await request_missing_data(update, context, missing_data)
        else:
            # Se não há mais dados, finalizar
            await finish_data_collection(update, context)
        return
    
    elif 'waiting_for_email' in context.user_data and context.user_data['waiting_for_email']:
        # Processar email
        context.user_data['collected_email'] = text
        context.user_data.pop('waiting_for_email', None)
        
        # Remover teclado personalizado
        await update.message.reply_text(
            "✅ Email salvo!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Voltar para a tela de coleta de dados para mostrar botões atualizados
        if 'missing_data' in context.user_data:
            missing_data = context.user_data['missing_data']
            await request_missing_data(update, context, missing_data)
        else:
            # Se não há mais dados, finalizar
            await finish_data_collection(update, context)
        return
    
    elif 'waiting_for_email_or_contact' in context.user_data and context.user_data['waiting_for_email_or_contact']:
        # Processar email ou contato
        if text == "📧 Digitar Email":
            # Usuário escolheu digitar email
            await update.message.reply_text(
                "📧 **Digite seu email:**\n\nExemplo: usuario@exemplo.com",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data.pop('waiting_for_email_or_contact', None)
            context.user_data['waiting_for_email'] = True
        elif text == "📱 Compartilhar Telefone":
            # Usuário escolheu compartilhar telefone
            keyboard = [[KeyboardButton("📱 Compartilhar Telefone", request_contact=True)]]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                "📱 **Toque no botão abaixo para compartilhar seu telefone:**",
                reply_markup=reply_markup
            )
            context.user_data.pop('waiting_for_email_or_contact', None)
            context.user_data['waiting_for_contact'] = True
        elif text == "🔙 Voltar":
            # Usuário escolheu voltar
            await update.message.reply_text(
                "🔙 Voltando...",
                reply_markup=ReplyKeyboardRemove()
            )
            
            if 'missing_data' in context.user_data:
                missing_data = context.user_data['missing_data']
                await request_missing_data(update, context, missing_data)
            else:
                await update.message.reply_text("❌ Erro na coleta de dados.")
        else:
            # Usuário digitou um email diretamente
            context.user_data['collected_email'] = text
            context.user_data.pop('waiting_for_email_or_contact', None)
            context.user_data['current_data_index'] += 1
            
            # Remover teclado personalizado
            await update.message.reply_text(
                "✅ Email salvo!",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Verificar se há mais dados para coletar
            missing_data = context.user_data.get('missing_data', [])
            current_index = context.user_data['current_data_index']
            
            if current_index >= len(missing_data):
                # Todos os dados foram coletados
                await finish_data_collection(update, context)
        return
    
    # Processar botões do teclado personalizado
    elif text == "📧 Enviar Email":
        # Solicitar email
        keyboard = [
            [KeyboardButton("🔙 Voltar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "📧 **Digite seu email:**\n\nExemplo: usuario@exemplo.com",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_email'] = True
        return
    

    
    elif text == "❌ Cancelar":
        # Cancelar coleta de dados
        context.user_data.clear()
        await update.message.reply_text(
            "❌ **Coleta de Dados Cancelada**\n\nVocê pode tentar novamente enviando /start",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    elif text == "🔙 Voltar":
        # Voltar para a tela inicial de coleta de dados
        await update.message.reply_text(
            "🔙 Voltando...",
            reply_markup=ReplyKeyboardRemove()
        )
        
        if 'missing_data' in context.user_data:
            missing_data = context.user_data['missing_data']
            await request_missing_data(update, context, missing_data)
        else:
            await update.message.reply_text("❌ Erro na coleta de dados.")
        return
    
    # Verificar se é admin para outras funcionalidades
    if not flow_manager.is_admin(user.id):
        print("DEBUG: Usuário não é admin, saindo da função")
        return
    
    # Debug: verificar estados atuais
    print(f"DEBUG: Estados atuais - waiting_for_image_text: {context.user_data.get('waiting_for_image_text', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_button_text: {context.user_data.get('waiting_for_button_text', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_button: {context.user_data.get('waiting_for_button', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_video_text: {context.user_data.get('waiting_for_video_text', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_name: {context.user_data.get('waiting_for_name', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_phone: {context.user_data.get('waiting_for_phone', False)}")
    print(f"DEBUG: Estados atuais - waiting_for_email: {context.user_data.get('waiting_for_email', False)}")
    print(f"DEBUG: Texto recebido: {text}")
    
    # Verificar se está coletando dados do usuário
    if 'waiting_for_name' in context.user_data and context.user_data['waiting_for_name']:
        # Processar nome
        context.user_data['collected_name'] = text
        context.user_data.pop('waiting_for_name', None)
        context.user_data['current_data_index'] += 1
        
        # Verificar se há mais dados para coletar
        missing_data = context.user_data.get('missing_data', [])
        current_index = context.user_data['current_data_index']
        
        if current_index < len(missing_data):
            # Próximo dado
            next_data_type = missing_data[current_index]
            if next_data_type == "telefone":
                await update.message.reply_text(
                    "📱 **Digite seu número de telefone:**\n\nFormato: (11) 99999-9999",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                    ]])
                )
                context.user_data['waiting_for_phone'] = True
            elif next_data_type == "email":
                await update.message.reply_text(
                    "📧 **Digite seu email:**\n\nExemplo: usuario@exemplo.com",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                    ]])
                )
                context.user_data['waiting_for_email'] = True
        else:
            # Todos os dados foram coletados
            await finish_data_collection(update, context)
        return
    
    elif 'waiting_for_phone' in context.user_data and context.user_data['waiting_for_phone']:
        # Processar telefone
        context.user_data['collected_phone'] = text
        context.user_data.pop('waiting_for_phone', None)
        context.user_data['current_data_index'] += 1
        
        # Verificar se há mais dados para coletar
        missing_data = context.user_data.get('missing_data', [])
        current_index = context.user_data['current_data_index']
        
        if current_index < len(missing_data):
            # Próximo dado
            next_data_type = missing_data[current_index]
            if next_data_type == "email":
                await update.message.reply_text(
                    "📧 **Digite seu email:**\n\nExemplo: usuario@exemplo.com",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                    ]])
                )
                context.user_data['waiting_for_email'] = True
        else:
            # Todos os dados foram coletados
            await finish_data_collection(update, context)
        return
    
    elif 'waiting_for_email' in context.user_data and context.user_data['waiting_for_email']:
        # Processar email
        context.user_data['collected_email'] = text
        context.user_data.pop('waiting_for_email', None)
        context.user_data['current_data_index'] += 1
        
        # Verificar se há mais dados para coletar
        missing_data = context.user_data.get('missing_data', [])
        current_index = context.user_data['current_data_index']
        
        if current_index >= len(missing_data):
            # Todos os dados foram coletados
            await finish_data_collection(update, context)
        return
    
    # Verificar se está configurando URL do webhook
    elif 'setting_webhook_url' in context.user_data and context.user_data['setting_webhook_url']:
        # Validar URL
        if text.startswith(('http://', 'https://')):
            if set_config_value('webhook_url', text):
                context.user_data.pop('setting_webhook_url', None)
                await update.message.reply_text(
                    f"✅ **URL do Webhook Definida!**\n\n🔗 {text}\n\nO webhook será enviado para esta URL.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
            else:
                await update.message.reply_text(
                    "❌ Erro ao salvar URL do webhook.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
        else:
            await update.message.reply_text(
                "❌ **URL Inválida!**\n\nA URL deve começar com http:// ou https://\n\nTente novamente:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_webhook")
                ]])
            )
        return
    
    elif 'changing_webhook_url' in context.user_data and context.user_data['changing_webhook_url']:
        # Validar URL
        if text.startswith(('http://', 'https://')):
            if set_config_value('webhook_url', text):
                context.user_data.pop('changing_webhook_url', None)
                await update.message.reply_text(
                    f"✅ **URL do Webhook Alterada!**\n\n🔗 {text}\n\nO webhook será enviado para esta nova URL.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
            else:
                await update.message.reply_text(
                    "❌ Erro ao alterar URL do webhook.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
        else:
            await update.message.reply_text(
                "❌ **URL Inválida!**\n\nA URL deve começar com http:// ou https://\n\nTente novamente:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_webhook")
                ]])
            )
        return
    
    # Verificar se está editando texto de etapa
    elif 'editing_step_text' in context.user_data and context.user_data['editing_step_text']:
        step_id = context.user_data['editing_step_id']
        
        if update_step_content(step_id, text):
            context.user_data.pop('editing_step_text', None)
            context.user_data.pop('editing_step_id', None)
            
            await update.message.reply_text(
                "✅ **Texto da Etapa Atualizado!**\n\nO conteúdo foi modificado com sucesso.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                ]])
            )
        else:
            await update.message.reply_text(
                "❌ Erro ao atualizar texto da etapa.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                ]])
            )
        return
    
    # Verificar se está editando mídia de etapa
    elif 'editing_step_media' in context.user_data and context.user_data['editing_step_media']:
        step_id = context.user_data['editing_step_id']
        
        # Validar URL
        if text.startswith(('http://', 'https://')):
            if update_step_media_url(step_id, text):
                context.user_data.pop('editing_step_media', None)
                context.user_data.pop('editing_step_id', None)
                
                await update.message.reply_text(
                    "✅ **Mídia da Etapa Atualizada!**\n\nA URL da mídia foi modificada com sucesso.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
            else:
                await update.message.reply_text(
                    "❌ Erro ao atualizar mídia da etapa.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                    ]])
                )
        else:
            await update.message.reply_text(
                "❌ **URL Inválida!**\n\nA URL deve começar com http:// ou https://\n\nTente novamente:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data=f"edit_step_{step_id}")
                ]])
            )
        return
    
    # Verificar se está configurando texto de imagem/vídeo (PRIORIDADE ALTA)
    print(f"DEBUG: VERIFICANDO SEÇÃO waiting_for_image_text - Condição: {'waiting_for_image_text' in context.user_data} AND {context.user_data.get('waiting_for_image_text', False)}")
    if 'waiting_for_image_text' in context.user_data and context.user_data['waiting_for_image_text']:
        print(f"DEBUG: ENTRANDO NA SEÇÃO waiting_for_image_text - Processando texto da imagem: {text}")
        context.user_data['current_step_data']['content'] = text
        context.user_data.pop('waiting_for_image_text', None)
        
        # Verificar se precisa adicionar botão
        if 'waiting_for_button' in context.user_data and context.user_data['waiting_for_button']:
            print("DEBUG: Precisa adicionar botão, solicitando texto do botão")
            print("DEBUG: ENVIANDO MENSAGEM: 🔘 **Digite o texto do botão:**")
            await update.message.reply_text(
                "🔘 **Digite o texto do botão:**",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
            context.user_data['waiting_for_button_text'] = True
            print("DEBUG: waiting_for_button_text definido como True (linha 522)")
            return
        else:
            print("DEBUG: NÃO precisa adicionar botão, salvando etapa diretamente")
            print(f"DEBUG: waiting_for_button existe: {'waiting_for_button' in context.user_data}")
            print(f"DEBUG: waiting_for_button valor: {context.user_data.get('waiting_for_button', 'NÃO EXISTE')}")
        
        print("DEBUG: Não precisa botão, salvando etapa")
        # Salvar etapa automaticamente
        await save_current_step_and_continue(update, context, flow_manager)
        return
    else:
        print(f"DEBUG: NÃO ENTROU NA SEÇÃO waiting_for_image_text. waiting_for_image_text existe: {'waiting_for_image_text' in context.user_data}, valor: {context.user_data.get('waiting_for_image_text', 'NÃO EXISTE')}")
        print(f"DEBUG: Condição completa: {'waiting_for_image_text' in context.user_data} AND {context.user_data.get('waiting_for_image_text', False)}")
    
    # Verificar se está configurando texto do botão (PRIORIDADE ALTA)
    print(f"DEBUG: VERIFICANDO SEÇÃO waiting_for_button_text - Condição: {'waiting_for_button_text' in context.user_data} AND {context.user_data.get('waiting_for_button_text', False)}")
    if 'waiting_for_button_text' in context.user_data and context.user_data['waiting_for_button_text']:
        print(f"DEBUG: ENTRANDO NA SEÇÃO CORRETA - Processando texto do botão: {text}")
        
        # Se ainda não tem o texto do botão, salvar o texto e pedir o link
        if 'button_text' not in context.user_data:
            context.user_data['button_text'] = text
            print("DEBUG: Texto do botão salvo, pedindo link")
            await update.message.reply_text(
                "🔗 **Digite o link/URL do botão:**\n\nExemplo: https://exemplo.com",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
            context.user_data['waiting_for_button_url'] = True
            return
        else:
            # Se já tem o texto, agora é o link
            button_url = text
            
            # Adicionar botão à etapa
            if 'buttons' not in context.user_data['current_step_data']:
                context.user_data['current_step_data']['buttons'] = []
            
            button_data = {
                'text': context.user_data['button_text'],
                'type': 'url',
                'data': button_url
            }
            context.user_data['current_step_data']['buttons'].append(button_data)
            
            print(f"DEBUG: Botão adicionado. Total de botões: {len(context.user_data['current_step_data']['buttons'])}")
            print(f"DEBUG: Botão criado - Texto: {context.user_data['button_text']}, URL: {button_url}")
            
            # Limpar todos os estados de espera
            context.user_data.pop('waiting_for_button_text', None)
            context.user_data.pop('waiting_for_button', None)
            context.user_data.pop('waiting_for_image_text', None)
            context.user_data.pop('waiting_for_video_text', None)
            context.user_data.pop('button_text', None)
            context.user_data.pop('waiting_for_button_url', None)
            
            print("DEBUG: Estados limpos, salvando etapa...")
            
            # Salvar etapa automaticamente
            await save_current_step_and_continue(update, context, flow_manager)
            return
    else:
        print(f"DEBUG: NÃO ENTROU NA SEÇÃO waiting_for_button_text. waiting_for_button_text existe: {'waiting_for_button_text' in context.user_data}, valor: {context.user_data.get('waiting_for_button_text', 'NÃO EXISTE')}")
        print(f"DEBUG: Condição completa: {'waiting_for_button_text' in context.user_data} AND {context.user_data.get('waiting_for_button_text', False)}")
    
    # Verificar se está configurando URL do botão
    if 'waiting_for_button_url' in context.user_data and context.user_data['waiting_for_button_url']:
        print(f"DEBUG: ENTRANDO NA SEÇÃO waiting_for_button_url - Processando URL do botão: {text}")
        
        # Se já tem o texto, agora é o link
        button_url = text
        
        # Adicionar botão à etapa
        if 'buttons' not in context.user_data['current_step_data']:
            context.user_data['current_step_data']['buttons'] = []
        
        button_data = {
            'text': context.user_data['button_text'],
            'type': 'url',
            'data': button_url
        }
        context.user_data['current_step_data']['buttons'].append(button_data)
        
        print(f"DEBUG: Botão adicionado. Total de botões: {len(context.user_data['current_step_data']['buttons'])}")
        print(f"DEBUG: Botão criado - Texto: {context.user_data['button_text']}, URL: {button_url}")
        
        # Limpar todos os estados de espera
        context.user_data.pop('waiting_for_button_text', None)
        context.user_data.pop('waiting_for_button', None)
        context.user_data.pop('waiting_for_image_text', None)
        context.user_data.pop('waiting_for_video_text', None)
        context.user_data.pop('button_text', None)
        context.user_data.pop('waiting_for_button_url', None)
        
        print("DEBUG: Estados limpos, salvando etapa...")
        
        # Salvar etapa automaticamente
        await save_current_step_and_continue(update, context, flow_manager)
        return
    
    # Verificar se está configurando texto de vídeo
    if 'waiting_for_video_text' in context.user_data and context.user_data['waiting_for_video_text']:
        context.user_data['current_step_data']['content'] = text
        context.user_data.pop('waiting_for_video_text', None)
        
        # Salvar etapa automaticamente
        await save_current_step_and_continue(update, context, flow_manager)
        return
    
    # Verificar se está configurando texto de vídeo redondo
    if 'waiting_for_video_note_text' in context.user_data and context.user_data['waiting_for_video_note_text']:
        context.user_data['current_step_data']['content'] = text
        context.user_data.pop('waiting_for_video_note_text', None)
        
        # Salvar etapa automaticamente
        await save_current_step_and_continue(update, context, flow_manager)
        return
    
    # Verificar se está criando um fluxo
    print(f"DEBUG: Verificando se está criando fluxo - creating_flow: {context.user_data.get('creating_flow', False)}")
    if 'creating_flow' in context.user_data and context.user_data['creating_flow']:
        print("DEBUG: ENTRANDO NA SEÇÃO creating_flow")
        # Criar novo fluxo
        flow_id = flow_manager.create_flow(text)
        if flow_id:
            context.user_data['current_flow_id'] = flow_id
            context.user_data['creating_flow'] = False
            context.user_data['flow_data']['name'] = text
            
            await update.message.reply_text(
                f"✅ **Fluxo '{text}' criado!**\n\n📋 **Mensagem 1**\n\nEscolha o tipo de mensagem:",
                reply_markup=create_message_step_keyboard(1)
            )
        else:
            await update.message.reply_text(
                "❌ Erro ao criar fluxo. Tente novamente.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        return
    
    # Verificar se está configurando etapa
    print(f"DEBUG: Verificando se está configurando etapa - current_step_type: {context.user_data.get('current_step_type', 'NÃO EXISTE')}")
    if 'current_step_type' in context.user_data:
        print("DEBUG: ENTRANDO NA SEÇÃO current_step_type")
        step_type = context.user_data['current_step_type']
        
        if 'current_step_data' not in context.user_data:
            context.user_data['current_step_data'] = {}
        
        if step_type == 'message_text':
            # Configurar mensagem de texto simples
            context.user_data['current_step_data']['content'] = text
            context.user_data['current_step_data']['type'] = 'text'
            
            # Salvar etapa automaticamente
            await save_current_step_and_continue(update, context, flow_manager)
            
        elif step_type == 'message_image':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'image'
                
                await update.message.reply_text(
                    "📝 **Digite o texto da imagem:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_image_text'] = True
                return
            else:
                # Se não é URL, não processar aqui - deixar para a seção waiting_for_image_text
                await update.message.reply_text(
                    "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie a imagem diretamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                return
            
        elif step_type == 'message_video':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'video'
                
                await update.message.reply_text(
                    "📝 **Digite o texto do vídeo:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_video_text'] = True
                return
            else:
                # Se não é URL, tratar como texto do vídeo (quando já tem media_url)
                if 'current_step_data' in context.user_data and 'media_url' in context.user_data['current_step_data']:
                    context.user_data['current_step_data']['content'] = text
                    context.user_data.pop('waiting_for_video_text', None)
                    
                    # Salvar etapa automaticamente
                    await save_current_step_and_continue(update, context, flow_manager)
                    return
                else:
                    await update.message.reply_text(
                        "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie o vídeo diretamente.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                        ]])
                    )
                    return
        
        elif step_type == 'message_video_note':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'video_note'
                
                await update.message.reply_text(
                    "📝 **Digite o texto do vídeo redondo:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_video_note_text'] = True
                return
            else:
                # Se não é URL, tratar como texto do vídeo redondo (quando já tem media_url)
                if 'current_step_data' in context.user_data and 'media_url' in context.user_data['current_step_data']:
                    context.user_data['current_step_data']['content'] = text
                    context.user_data.pop('waiting_for_video_note_text', None)
                    
                    # Salvar etapa automaticamente
                    await save_current_step_and_continue(update, context, flow_manager)
                    return
                else:
                    await update.message.reply_text(
                        "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie o vídeo redondo diretamente.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                        ]])
                    )
                    return
            
        elif step_type == 'message_image_button':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'image'
                
                await update.message.reply_text(
                    "📝 **Digite o texto da imagem:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_image_text'] = True
                context.user_data['waiting_for_button'] = True
                return
            else:
                # Se não é URL, não processar aqui - deixar para a seção waiting_for_image_text
                await update.message.reply_text(
                    "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie a imagem diretamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                return
        
        elif step_type == 'message_video_button':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'video'
                
                await update.message.reply_text(
                    "📝 **Digite o texto do vídeo:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_video_text'] = True
                context.user_data['waiting_for_button'] = True
                return
            else:
                # Se não é URL, não processar aqui - deixar para a seção waiting_for_video_text
                await update.message.reply_text(
                    "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie o vídeo diretamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                return
        
        elif step_type == 'message_video_note_button':
            # Verificar se é uma URL válida
            if text.startswith(('http://', 'https://')):
                context.user_data['current_step_data']['media_url'] = text
                context.user_data['current_step_data']['type'] = 'video_note'
                
                await update.message.reply_text(
                    "📝 **Digite o texto do vídeo redondo:**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                context.user_data['waiting_for_video_note_text'] = True
                context.user_data['waiting_for_button'] = True
                return
            else:
                # Se não é URL, não processar aqui - deixar para a seção waiting_for_video_note_text
                await update.message.reply_text(
                    "❌ **URL inválida!**\n\nDigite uma URL válida (começando com http:// ou https://) ou envie o vídeo redondo diretamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                    ]])
                )
                return
        
        elif step_type == 'message_text_button':
            # Para texto + botão, o texto é o conteúdo da mensagem
            context.user_data['current_step_data']['content'] = text
            context.user_data['current_step_data']['type'] = 'text'
            
            await update.message.reply_text(
                "🔘 **Digite o texto do botão:**",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
            context.user_data['waiting_for_button_text'] = True
            return
        
        # Salvar etapa automaticamente
        if 'current_flow_id' in context.user_data:
            flow_id = context.user_data['current_flow_id']
            step_id = flow_manager.save_flow_step(flow_id, context.user_data['current_step_data'])
            
            if step_id:
                # Limpar dados da etapa
                context.user_data.pop('current_step_data', None)
                context.user_data.pop('current_step_type', None)
                context.user_data.pop('waiting_for_image_text', None)
                context.user_data.pop('waiting_for_video_text', None)
                
                await update.message.reply_text(
                    "✅ **Etapa salva automaticamente!**\n\nEscolha uma opção:",
                    reply_markup=create_simple_flow_control_keyboard()
                )
            else:
                await update.message.reply_text(
                    "❌ Erro ao salvar etapa.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        return
    
    # Se não estiver em nenhum modo de criação, usar echo normal
    print("DEBUG: NÃO ENTROU EM NENHUMA SEÇÃO ESPECÍFICA, USANDO ECHO")
    await echo(update, context)

async def save_current_step_and_continue(update, context, flow_manager):
    """Salva a etapa atual e mostra opções para continuar"""
    print(f"🔍 DEBUG: save_current_step_and_continue - current_flow_id existe: {'current_flow_id' in context.user_data}")
    print(f"🔍 DEBUG: save_current_step_and_continue - current_step_data existe: {'current_step_data' in context.user_data}")
    print(f"🔍 DEBUG: save_current_step_and_continue - current_flow_id: {context.user_data.get('current_flow_id', 'NÃO EXISTE')}")
    print(f"🔍 DEBUG: save_current_step_and_continue - current_step_data: {context.user_data.get('current_step_data', 'NÃO EXISTE')}")
    print(f"🔍 DEBUG: save_current_step_and_continue - editing_flow_id: {context.user_data.get('editing_flow_id', 'NÃO EXISTE')}")
    
    # Verificar se temos current_flow_id ou editing_flow_id
    flow_id = context.user_data.get('current_flow_id') or context.user_data.get('editing_flow_id')
    
    if flow_id and 'current_step_data' in context.user_data:
        step_data = context.user_data['current_step_data']
        
        print(f"🔍 DEBUG: Salvando etapa - flow_id: {flow_id}, step_data: {step_data}")
        
        # Salvar etapa
        step_id = flow_manager.save_flow_step(flow_id, step_data)
        
        if step_id:
            # Limpar dados da etapa atual
            context.user_data.pop('current_step_data', None)
            context.user_data.pop('current_step_type', None)
            context.user_data.pop('waiting_for_image_text', None)
            context.user_data.pop('waiting_for_video_text', None)
            context.user_data.pop('waiting_for_video_note_text', None)
            context.user_data.pop('waiting_for_button', None)
            context.user_data.pop('waiting_for_button_text', None)
            
            # Incrementar número da etapa
            current_step = context.user_data.get('current_step_number', 1)
            next_step = current_step + 1
            context.user_data['current_step_number'] = next_step
            
            await update.message.reply_text(
                f"✅ **Mensagem {current_step} salva!**\n\nEscolha uma opção:",
                reply_markup=create_simple_flow_control_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ Erro ao salvar etapa.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                ]])
            )
    else:
        print("DEBUG: ERRO - Dados da etapa não encontrados")
        await update.message.reply_text(
            "❌ Dados da etapa não encontrados.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
            ]])
        )

# Handlers para sistema de fluxo e admin
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /admin - Menu de administração"""
    user = update.effective_user
    flow_manager = FlowManager()
    
    if not flow_manager.is_admin(user.id):
        await update.message.reply_text("❌ Você não tem permissão de administrador.")
        return
    
    await update.message.reply_text(
        "🔧 **Painel de Administração**\n\nEscolha uma opção:",
        reply_markup=create_admin_keyboard()
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler para callbacks dos botões inline"""
    query = update.callback_query
    
    # DEBUG: Log do callback recebido
    print(f"🔍 DEBUG: Callback recebido: {query.data}")
    print(f"🔍 DEBUG: User ID: {update.effective_user.id}")
    print(f"🔍 DEBUG: Message ID: {query.message.message_id if query.message else 'N/A'}")
    
    await query.answer()
    
    # DEBUG: Verificar se o callback começa com edit_step_text_
    if query.data.startswith("edit_step_text_"):
        print(f"🔍 DEBUG: Callback edit_step_text_ detectado: {query.data}")
    elif query.data.startswith("edit_step_media_"):
        print(f"🔍 DEBUG: Callback edit_step_media_ detectado: {query.data}")
    else:
        print(f"🔍 DEBUG: Callback não é de edição: {query.data}")
    
    # Função auxiliar para editar mensagem com tratamento de erro
    async def safe_edit_message(text, reply_markup=None):
        print(f"🔍 DEBUG: safe_edit_message chamada - Texto: {text[:50]}...")
        print(f"🔍 DEBUG: Reply markup: {reply_markup}")
        try:
            await query.edit_message_text(text, reply_markup=reply_markup)
            print("🔍 DEBUG: Mensagem editada com sucesso")
        except Exception as e:
            print(f"🔍 DEBUG: Erro ao editar mensagem: {e}")
            if "Message is not modified" in str(e):
                # Ignorar erro de mensagem não modificada
                print("🔍 DEBUG: Ignorando erro 'Message is not modified'")
                pass
            else:
                # Re-raise outros erros
                print(f"🔍 DEBUG: Re-raise do erro: {e}")
                raise e
    
    user = update.effective_user
    flow_manager = FlowManager()
    
    if query.data == "admin_menu":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "🔧 **Painel de Administração**\n\nEscolha uma opção:",
                reply_markup=create_admin_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "admin_flows":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "📝 **Gerenciamento de Fluxos**\n\nEscolha uma opção:",
                reply_markup=create_flow_management_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "create_flow":
        if flow_manager.is_admin(user.id):
            context.user_data['creating_flow'] = True
            context.user_data['flow_data'] = {}
            context.user_data['current_step_number'] = 1
            await safe_edit_message(
                "📝 **Criar Novo Fluxo**\n\nDigite o nome do fluxo:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_text":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_text'
            await safe_edit_message(
                "📝 **Mensagem + Texto**\n\nDigite o texto da mensagem:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_image":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_image'
            await safe_edit_message(
                "🖼️ **Mensagem + Imagem**\n\n📤 **Envie a imagem diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_video":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_video'
            await safe_edit_message(
                "🎥 **Mensagem + Vídeo**\n\n📤 **Envie o vídeo diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_image_button":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_image_button'
            await safe_edit_message(
                "🖼️ **Mensagem + Imagem + Botão**\n\n📤 **Envie a imagem diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_text_button":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_text_button'
            await safe_edit_message(
                "🔘 **Mensagem + Texto + Botão**\n\n📝 **Digite o texto da mensagem:**",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_video_button":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_video_button'
            await safe_edit_message(
                "🎥 **Mensagem + Vídeo + Botão**\n\n📤 **Envie o vídeo diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_video_note":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_video_note'
            await safe_edit_message(
                "🎬 **Mensagem + Vídeo Redondo**\n\n📤 **Envie o vídeo redondo diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "add_message_video_note_button":
        if flow_manager.is_admin(user.id):
            context.user_data['current_step_type'] = 'message_video_note_button'
            await safe_edit_message(
                "🎬 **Mensagem + Vídeo Redondo + Texto**\n\n📤 **Envie o vídeo redondo diretamente** ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "convert_video_note":
        if flow_manager.is_admin(user.id):
            if 'video_to_convert' in context.user_data:
                video_data = context.user_data['video_to_convert']['file_data']
                step_type = context.user_data['video_to_convert']['step_type']
                
                await safe_edit_message(
                    "🔄 **Convertendo vídeo...**\n\n"
                    "Aguarde enquanto convertemos o vídeo para o formato correto.\n"
                    "Isso pode levar alguns segundos...",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⏳ Processando...", callback_data="processing")
                    ]])
                )
                
                # Converter vídeo
                success, converted_data, message = await convert_video_to_video_note(video_data)
                
                if success:
                    # Salvar vídeo convertido
                    if 'current_step_data' not in context.user_data:
                        context.user_data['current_step_data'] = {}
                    
                    # Salvar como arquivo temporário
                    temp_filename = f"converted_{int(asyncio.get_event_loop().time())}.mp4"
                    temp_path = UPLOADS_DIR / "video_note" / temp_filename
                    temp_path.parent.mkdir(exist_ok=True)
                    
                    with open(temp_path, 'wb') as f:
                        f.write(converted_data)
                    
                    context.user_data['current_step_data']['media_url'] = str(temp_path)
                    context.user_data['current_step_data']['type'] = 'video_note'
                    context.user_data['current_step_data']['converted'] = True
                    
                    # Limpar dados de conversão
                    context.user_data.pop('video_to_convert', None)
                    
                    await safe_edit_message(
                        f"✅ **Conversão Concluída!**\n\n{message}\n\n"
                        "📝 **Digite o texto do vídeo redondo:**",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="admin_flows")
                        ]])
                    )
                    
                    context.user_data['waiting_for_video_note_text'] = True
                    if step_type == 'message_video_note_button':
                        context.user_data['waiting_for_button'] = True
                else:
                    await safe_edit_message(
                        f"❌ **Erro na Conversão**\n\n{message}\n\n"
                        "Tente enviar um vídeo diferente ou verifique os requisitos.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                        ]])
                    )
            else:
                await safe_edit_message(
                    "❌ **Erro**\n\nDados do vídeo não encontrados. Tente novamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "convert_welcome_video_note":
        if flow_manager.is_admin(user.id):
            if 'temp_welcome_video_data' in context.user_data:
                video_data = context.user_data['temp_welcome_video_data']['file_data']
                
                await safe_edit_message(
                    "🔄 **Convertendo vídeo para boas-vindas...**\n\n"
                    "Aguarde enquanto convertemos o vídeo para o formato redondo.\n"
                    "Isso pode levar alguns segundos...",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⏳ Processando...", callback_data="processing")
                    ]])
                )
                
                # Converter vídeo
                success, converted_data, message = await convert_video_to_video_note(video_data)
                
                if success:
                    # Salvar vídeo convertido
                    import os
                    from pathlib import Path
                    UPLOADS_DIR = Path("uploads")
                    video_note_dir = UPLOADS_DIR / "video_note"
                    video_note_dir.mkdir(parents=True, exist_ok=True)
                    
                    temp_filename = f"welcome_video_note_{int(asyncio.get_event_loop().time())}.mp4"
                    temp_path = video_note_dir / temp_filename
                    
                    with open(temp_path, 'wb') as f:
                        f.write(converted_data)
                    
                    # Salvar configurações
                    if set_config_value('welcome_media_url', str(temp_path)) and set_config_value('welcome_media_type', 'video_note'):
                        context.user_data.pop('configuring_welcome_media', None)
                        context.user_data.pop('welcome_media_type', None)
                        context.user_data.pop('temp_welcome_video_data', None)
                        
                        await safe_edit_message(
                            f"✅ **Vídeo Redondo da Mensagem de Boas-vindas Configurado!**\n\n"
                            f"O vídeo foi convertido com sucesso para formato redondo.\n"
                            f"Arquivo: {temp_path}",
                            reply_markup=create_config_welcome_keyboard()
                        )
                    else:
                        await safe_edit_message(
                            "❌ **Erro ao salvar vídeo redondo.**\n\nTente novamente.",
                            reply_markup=create_config_welcome_keyboard()
                        )
                else:
                    await safe_edit_message(
                        f"❌ **Erro na Conversão**\n\n{message}\n\n"
                        "Tente enviar um vídeo diferente ou verifique os requisitos.",
                        reply_markup=create_config_welcome_keyboard()
                    )
            else:
                await safe_edit_message(
                    "❌ **Erro**\n\nDados do vídeo não encontrados. Tente novamente.",
                    reply_markup=create_config_welcome_keyboard()
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "finish_step":
        if flow_manager.is_admin(user.id):
            # Salvar etapa atual no banco de dados
            if 'current_flow_id' in context.user_data and 'current_step_data' in context.user_data:
                flow_id = context.user_data['current_flow_id']
                step_data = context.user_data['current_step_data']
                
                # Salvar etapa usando a nova função
                step_id = flow_manager.save_flow_step(flow_id, step_data)
                
                if step_id:
                    # Limpar dados da etapa atual
                    context.user_data.pop('current_step_data', None)
                    context.user_data.pop('current_step_type', None)
                    context.user_data.pop('media_option', None)
                    context.user_data.pop('current_button_type', None)
                    
                    await safe_edit_message(
                        "✅ **Etapa Salva!**\n\nEtapa adicionada com sucesso ao fluxo.",
                        reply_markup=create_flow_control_keyboard()
                    )
                else:
                    await safe_edit_message(
                        "❌ Erro ao salvar etapa. Tente novamente.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                        ]])
                    )
            else:
                await safe_edit_message(
                    "❌ Dados da etapa não encontrados.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "edit_flow":
        if flow_manager.is_admin(user.id):
            flows = flow_manager.get_active_flows()
            if flows:
                await safe_edit_message(
                    "✏️ **Editar Fluxo**\n\nEscolha o fluxo que deseja editar:",
                    reply_markup=create_edit_flow_keyboard(flows)
                )
            else:
                await safe_edit_message(
                    "📝 Nenhum fluxo encontrado para editar.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("edit_flow_") and query.data != "edit_flow_list":
        if flow_manager.is_admin(user.id):
            flow_id = int(query.data.split("_")[2])
            
            # Obter informações do fluxo
            flows = flow_manager.get_active_flows()
            flow_name = "Fluxo Desconhecido"
            for flow in flows:
                if flow['id'] == flow_id:
                    flow_name = flow['name']
                    break
            
            # Salvar flow_id no contexto para edição
            context.user_data['editing_flow_id'] = flow_id
            
            await safe_edit_message(
                f"✏️ **Editar Fluxo: {flow_name}**\n\nEscolha a etapa que deseja editar:",
                reply_markup=create_edit_step_keyboard(flow_id)
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("edit_step_") and not query.data.startswith("edit_step_text_") and not query.data.startswith("edit_step_media_"):
        print(f"🔍 DEBUG: Entrando no handler edit_step_ genérico - Callback: {query.data}")
        if flow_manager.is_admin(user.id):
            step_id = int(query.data.split("_")[-1])
            
            # Obter detalhes da etapa
            step = get_step_details(step_id)
            if step:
                # Salvar informações da etapa no contexto
                context.user_data['editing_step_id'] = step_id
                context.user_data['editing_step_type'] = step['step_type']
                context.user_data['editing_step_content'] = step['content']
                context.user_data['editing_step_media_url'] = step.get('media_url', '')
                
                # Criar mensagem de detalhes da etapa
                message = f"📝 **Editar Etapa**\n\n"
                message += f"**Fluxo:** {step['flow_name']}\n"
                message += f"**Tipo:** {step['step_type'].replace('_', ' ').title()}\n"
                message += f"**Conteúdo:** {step['content'][:100]}{'...' if len(step['content']) > 100 else ''}\n"
                
                if step.get('media_url'):
                    message += f"**Mídia:** {step['media_url'][:50]}...\n"
                
                if step.get('buttons'):
                    message += f"**Botões:** {len(step['buttons'])} botão(ões)\n"
                
                message += "\nEscolha o que deseja editar:"
                
                # Criar teclado de opções de edição
                keyboard = [
                    [InlineKeyboardButton("📝 Editar Texto", callback_data=f"edit_step_text_{step_id}")],
                    [InlineKeyboardButton("🖼️ Editar Mídia", callback_data=f"edit_step_media_{step_id}")],
                    [InlineKeyboardButton("🗑️ Deletar Etapa", callback_data=f"delete_step_{step_id}")],
                    [InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_flow_{step['flow_id']}")]
                ]
                
                await safe_edit_message(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await safe_edit_message(
                    "❌ Etapa não encontrada.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="edit_flow_list")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("edit_step_text_"):
        print(f"🔍 DEBUG: Entrando no handler edit_step_text_ - Callback: {query.data}")
        if flow_manager.is_admin(user.id):
            step_id = int(query.data.split("_")[-1])
            print(f"🔍 DEBUG: Step ID extraído: {step_id}")
            
            context.user_data['editing_step_text'] = True
            context.user_data['editing_step_id'] = step_id
            
            print("🔍 DEBUG: Tentando editar mensagem para edição de texto...")
            await safe_edit_message(
                "📝 **Editar Texto da Etapa**\n\nDigite o novo texto:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data=f"edit_step_{step_id}")
                ]])
            )
            print("🔍 DEBUG: Mensagem editada com sucesso para edição de texto")
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("edit_step_media_"):
        print(f"🔍 DEBUG: Entrando no handler edit_step_media_ - Callback: {query.data}")
        if flow_manager.is_admin(user.id):
            step_id = int(query.data.split("_")[-1])
            print(f"🔍 DEBUG: Step ID extraído: {step_id}")
            
            context.user_data['editing_step_media'] = True
            context.user_data['editing_step_id'] = step_id
            
            print("🔍 DEBUG: Tentando editar mensagem para edição de mídia...")
            await safe_edit_message(
                "🖼️ **Editar Mídia da Etapa**\n\nEnvie a nova imagem/vídeo ou digite a URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data=f"edit_step_{step_id}")
                ]])
            )
            print("🔍 DEBUG: Mensagem editada com sucesso para edição de mídia")
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("delete_step_"):
        if flow_manager.is_admin(user.id):
            step_id = int(query.data.split("_")[-1])
            
            # Obter detalhes da etapa antes de deletar
            step = get_step_details(step_id)
            if step:
                if delete_step_completely(step_id):
                    await safe_edit_message(
                        f"🗑️ **Etapa Deletada!**\n\nA etapa '{step['step_type'].replace('_', ' ').title()}' foi removida com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_flow_{step['flow_id']}")
                        ]])
                    )
                else:
                    await safe_edit_message(
                        "❌ Erro ao deletar etapa.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data=f"edit_step_{step_id}")
                        ]])
                    )
            else:
                await safe_edit_message(
                    "❌ Etapa não encontrada.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="edit_flow_list")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("add_step_"):
        print(f"🔍 DEBUG: Entrando no handler add_step_ - Callback: {query.data}")
        if flow_manager.is_admin(user.id):
            flow_id = int(query.data.split("_")[-1])
            print(f"🔍 DEBUG: Flow ID extraído: {flow_id}")
            
            # Salvar flow_id no contexto para adição de etapa
            context.user_data['current_flow_id'] = flow_id  # Corrigido: usar current_flow_id
            context.user_data['editing_flow_id'] = flow_id
            context.user_data['current_step_number'] = 1
            
            print(f"🔍 DEBUG: current_flow_id definido como: {flow_id}")
            
            await safe_edit_message(
                "📝 **Adicionar Etapa**\n\nEscolha o tipo de etapa:",
                reply_markup=create_message_step_keyboard(1)
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "edit_flow_list":
        if flow_manager.is_admin(user.id):
            flows = flow_manager.get_active_flows()
            if flows:
                await safe_edit_message(
                    "✏️ **Editar Fluxo**\n\nEscolha o fluxo que deseja editar:",
                    reply_markup=create_edit_flow_keyboard(flows)
                )
            else:
                await safe_edit_message(
                    "📝 Nenhum fluxo encontrado para editar.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "continue_flow":
        if flow_manager.is_admin(user.id):
            # Continuar adicionando etapas
            current_step = context.user_data.get('current_step_number', 1)
            await safe_edit_message(
                f"📋 **Mensagem {current_step}**\n\nEscolha o tipo de mensagem:",
                reply_markup=create_message_step_keyboard(current_step)
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "confirm_step":
        if flow_manager.is_admin(user.id):
            # Confirmar etapa atual (salvar no banco)
            if 'current_flow_id' in context.user_data and 'current_step_data' in context.user_data:
                flow_id = context.user_data['current_flow_id']
                step_data = context.user_data['current_step_data']
                
                # Salvar etapa
                step_id = flow_manager.save_flow_step(flow_id, step_data)
                
                if step_id:
                    # Limpar dados da etapa atual
                    context.user_data.pop('current_step_data', None)
                    context.user_data.pop('current_step_type', None)
                    context.user_data.pop('media_option', None)
                    context.user_data.pop('current_button_type', None)
                    
                    await safe_edit_message(
                        "✅ **Etapa Confirmada!**\n\nEtapa salva com sucesso.",
                        reply_markup=create_flow_control_keyboard()
                    )
                else:
                    await safe_edit_message(
                        "❌ Erro ao confirmar etapa.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                        ]])
                    )
            else:
                await safe_edit_message(
                    "❌ Dados da etapa não encontrados.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "preview_step":
        if flow_manager.is_admin(user.id):
            # Mostrar preview da etapa atual
            if 'current_step_data' in context.user_data:
                step_data = context.user_data['current_step_data']
                
                preview_text = f"�� **Preview da Etapa**\n\n"
                preview_text += f"**Tipo:** {step_data.get('type', 'text').upper()}\n"
                preview_text += f"**Conteúdo:** {step_data.get('content', '')[:100]}...\n"
                
                if step_data.get('media_url'):
                    preview_text += f"**Mídia:** {step_data.get('media_url')}\n"
                
                buttons = step_data.get('buttons', [])
                if buttons:
                    preview_text += f"**Botões:** {len(buttons)} botão(ões)\n"
                    for i, button in enumerate(buttons, 1):
                        preview_text += f"  {i}. {button.get('text', '')}\n"
                
                await safe_edit_message(
                    preview_text,
                    reply_markup=create_step_preview_keyboard()
                )
            else:
                await safe_edit_message(
                    "❌ Nenhuma etapa para preview.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="step_type_selection")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "finish_flow":
        if flow_manager.is_admin(user.id):
            # Finalizar fluxo
            if 'current_flow_id' in context.user_data:
                flow_id = context.user_data['current_flow_id']
                
                try:
                    # Reordenar etapas
                    if flow_manager.reorder_steps(flow_id):
                        print(f"Etapas reordenadas com sucesso para o fluxo {flow_id}")
                    else:
                        print(f"Aviso: Não foi possível reordenar etapas do fluxo {flow_id}")
                    
                    # Obter resumo do fluxo
                    summary = flow_manager.get_flow_summary(flow_id)
                except Exception as e:
                    print(f"Erro ao finalizar fluxo: {e}")
                    await safe_edit_message(
                        "❌ Erro ao finalizar fluxo. Tente novamente.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                        ]])
                    )
                    return
                
                if summary:
                    flow = summary['flow']
                    steps = summary['steps']
                    
                    finish_text = f"🎉 **Fluxo Finalizado com Sucesso!**\n\n"
                    finish_text += f"**Nome:** {flow['name']}\n"
                    finish_text += f"**Descrição:** {flow['description']}\n"
                    finish_text += f"**Total de Etapas:** {summary['total_steps']}\n\n"
                    
                    if steps:
                        finish_text += "**Ordem de Envio:**\n"
                        for i, step in enumerate(steps, 1):
                            finish_text += f"{i}. {step['step_type'].upper()}"
                            if step['button_count'] > 0:
                                finish_text += f" ({step['button_count']} botões)"
                            finish_text += "\n"
                    
                    finish_text += "\n✅ O fluxo foi salvo e está pronto para uso!"
                else:
                    finish_text = "🎉 **Fluxo Finalizado!**\n\nO fluxo foi salvo com sucesso."
                
                # Limpar dados temporários
                context.user_data.clear()
                
                await safe_edit_message(
                    finish_text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Ver Fluxos", callback_data="list_flows")],
                        [InlineKeyboardButton("➕ Criar Novo Fluxo", callback_data="create_flow")],
                        [InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")]
                    ])
                )
            else:
                await safe_edit_message(
                    "❌ Dados do fluxo não encontrados.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "list_flows":
        if flow_manager.is_admin(user.id):
            flows = flow_manager.get_active_flows()
            if flows:
                flow_list = "📋 **Fluxos Ativos:**\n\n"
                for flow in flows:
                    flow_list += f"• **{flow['name']}** (ID: {flow['id']})\n"
                    if flow['description']:
                        flow_list += f"  _{flow['description']}_\n"
                    flow_list += "\n"
                
                await safe_edit_message(
                    flow_list,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
            else:
                await safe_edit_message(
                    "📝 Nenhum fluxo encontrado.\n\nCrie um novo fluxo para começar!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "delete_flow":
        if flow_manager.is_admin(user.id):
            flows = flow_manager.get_active_flows()
            if flows:
                await safe_edit_message(
                    "🗑️ **Deletar Fluxo**\n\nEscolha o fluxo que deseja deletar:",
                    reply_markup=create_delete_flow_keyboard(flows)
                )
            else:
                await safe_edit_message(
                    "📝 Nenhum fluxo encontrado para deletar.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("delete_flow_"):
        if flow_manager.is_admin(user.id):
            flow_id = int(query.data.split("_")[2])
            
            # Obter informações do fluxo antes de deletar
            flows = flow_manager.get_active_flows()
            flow_name = "Fluxo Desconhecido"
            for flow in flows:
                if flow['id'] == flow_id:
                    flow_name = flow['name']
                    break
            
            # Deletar o fluxo
            if flow_manager.delete_flow(flow_id):
                await safe_edit_message(
                    f"✅ **Fluxo Deletado!**\n\n🗑️ **{flow_name}** foi deletado com sucesso.\n\nTodas as etapas e botões associados também foram removidos.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
            else:
                await safe_edit_message(
                    f"❌ **Erro ao Deletar Fluxo**\n\nNão foi possível deletar o fluxo **{flow_name}**.\n\nVerifique se o fluxo existe e tente novamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_flows")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "set_default_flow":
        if flow_manager.is_admin(user.id):
            flows = flow_manager.get_flows_for_default_selection()
            if flows:
                default_flow = flow_manager.get_default_flow()
                current_default = f"⭐ **Fluxo Padrão Atual:** {default_flow['name']}" if default_flow else "❌ **Nenhum fluxo padrão definido**"
                
                message = f"⭐ **Definir Fluxo Padrão**\n\n{current_default}\n\nEscolha um fluxo para definir como padrão:"
                
                await safe_edit_message(
                    message,
                    reply_markup=create_default_flow_keyboard(flows)
                )
            else:
                await safe_edit_message(
                    "📝 Nenhum fluxo encontrado.\n\nCrie um novo fluxo primeiro!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_menu")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data.startswith("set_default_"):
        if flow_manager.is_admin(user.id):
            flow_id = int(query.data.split("_")[2])
            
            if flow_manager.set_default_flow(flow_id):
                # Obter nome do fluxo
                flows = flow_manager.get_active_flows()
                flow_name = "Fluxo Desconhecido"
                for flow in flows:
                    if flow['id'] == flow_id:
                        flow_name = flow['name']
                        break
                
                await safe_edit_message(
                    f"✅ **Fluxo Padrão Definido!**\n\n⭐ **{flow_name}** agora é o fluxo padrão.\n\nEste fluxo será executado quando usuários enviarem /start.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_menu")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao definir fluxo padrão. Tente novamente.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_menu")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    

    
    elif query.data == "back_to_main":
        await safe_edit_message(
            "👋 **Bot Influenciador**\n\nEscolha uma opção:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Iniciar", callback_data="start_flow")],
                [InlineKeyboardButton("📋 Menu", callback_data="main_menu")],
                [InlineKeyboardButton("❓ Ajuda", callback_data="help_menu")]
            ])
        )
    
    elif query.data == "admin_config":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "⚙️ **Configurações do Bot**\n\nEscolha uma configuração para gerenciar:",
                reply_markup=create_config_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "admin_stats":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "📊 **Estatísticas e Relatórios**\n\nEscolha o tipo de relatório:",
                reply_markup=create_stats_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "reset_welcome_video":
        if flow_manager.is_admin(user.id):
            # Resetar controle de vídeo de boas-vindas para todos os usuários
            from flow_manager import reset_welcome_video_sent
            
            connection = create_connection()
            if connection is None:
                await safe_edit_message("❌ Erro ao conectar ao banco de dados.")
                return
            
            try:
                cursor = connection.cursor()
                
                # Resetar para todos os usuários
                cursor.execute("UPDATE users SET welcome_video_sent = FALSE")
                connection.commit()
                
                affected_rows = cursor.rowcount
                await safe_edit_message(
                    f"✅ **Controle de Vídeo Redondo Resetado!**\n\n"
                    f"Resetado para {affected_rows} usuários.\n\n"
                    f"Agora todos os usuários receberão o vídeo redondo novamente na próxima vez que precisarem de cadastro.",
                    reply_markup=create_admin_keyboard()
                )
                
            except Error as e:
                await safe_edit_message(f"❌ Erro ao resetar: {e}")
            finally:
                if connection.is_connected():
                    cursor.close()
                    connection.close()
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "stats_general":
        if flow_manager.is_admin(user.id):
            stats = get_general_stats()
            if stats:
                message = "📈 **Estatísticas Gerais**\n\n"
                message += f"👥 **Usuários:** {stats['total_users']}\n"
                message += f"✅ **Com dados completos:** {stats['users_with_data']}\n"
                message += f"📝 **Fluxos:** {stats['total_flows']}\n"
                message += f"📋 **Etapas:** {stats['total_steps']}\n"
                message += f"🔘 **Botões:** {stats['total_buttons']}\n\n"
                
                if stats['users_by_month']:
                    message += "📅 **Usuários por mês (últimos 6 meses):**\n"
                    for month, count in stats['users_by_month']:
                        message += f"  • {month}: {count} usuários\n"
                
                await safe_edit_message(
                    message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao obter estatísticas.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "stats_full_report":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "📊 **Gerando Relatório Completo...**\n\nAguarde um momento...",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏳ Processando...", callback_data="processing")
                ]])
            )
            
            filename = generate_excel_report("full")
            if filename:
                with open(filename, 'rb') as file:
                    await safe_edit_message(
                        "📊 **Relatório Completo Gerado!**\n\nO arquivo Excel foi criado com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                        ]])
                    )
                    await context.bot.send_document(
                        chat_id=query.from_user.id,
                        document=file,
                        filename=filename,
                        caption="📊 **Relatório Completo do Sistema**\n\nArquivo Excel com todas as estatísticas e dados."
                    )
                    # Remover arquivo após envio
                    import os
                    os.remove(filename)
            else:
                await safe_edit_message(
                    "❌ Erro ao gerar relatório completo.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "stats_users_report":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "👥 **Gerando Relatório de Usuários...**\n\nAguarde um momento...",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏳ Processando...", callback_data="processing")
                ]])
            )
            
            filename = generate_excel_report("users")
            if filename:
                with open(filename, 'rb') as file:
                    await safe_edit_message(
                        "👥 **Relatório de Usuários Gerado!**\n\nO arquivo Excel foi criado com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                        ]])
                    )
                    await context.bot.send_document(
                        chat_id=query.from_user.id,
                        document=file,
                        filename=filename,
                        caption="👥 **Relatório de Usuários**\n\nLista completa de todos os usuários registrados."
                    )
                    # Remover arquivo após envio
                    import os
                    os.remove(filename)
            else:
                await safe_edit_message(
                    "❌ Erro ao gerar relatório de usuários.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "stats_flows_report":
        if flow_manager.is_admin(user.id):
            await safe_edit_message(
                "📝 **Gerando Relatório de Fluxos...**\n\nAguarde um momento...",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⏳ Processando...", callback_data="processing")
                ]])
            )
            
            filename = generate_excel_report("flows")
            if filename:
                with open(filename, 'rb') as file:
                    await safe_edit_message(
                        "📝 **Relatório de Fluxos Gerado!**\n\nO arquivo Excel foi criado com sucesso.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                        ]])
                    )
                    await context.bot.send_document(
                        chat_id=query.from_user.id,
                        document=file,
                        filename=filename,
                        caption="📝 **Relatório de Fluxos**\n\nLista completa de todos os fluxos criados."
                    )
                    # Remover arquivo após envio
                    import os
                    os.remove(filename)
            else:
                await safe_edit_message(
                    "❌ Erro ao gerar relatório de fluxos.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_stats")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_phone":
        if flow_manager.is_admin(user.id):
            status = "✅ Ativada" if is_phone_collection_enabled() else "❌ Desativada"
            await safe_edit_message(
                f"📱 **Coleta de Número**\n\nStatus atual: {status}\n\nEscolha uma opção:",
                reply_markup=create_config_phone_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_phone_enable":
        if flow_manager.is_admin(user.id):
            if set_config_value('collect_phone', 'true'):
                await safe_edit_message(
                    "✅ **Coleta de Número Ativada!**\n\nAgora o bot irá solicitar o número de telefone dos usuários antes de exibir o fluxo.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao ativar coleta de número.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_phone_disable":
        if flow_manager.is_admin(user.id):
            if set_config_value('collect_phone', 'false'):
                await safe_edit_message(
                    "❌ **Coleta de Número Desativada!**\n\nO bot não irá mais solicitar o número de telefone dos usuários.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao desativar coleta de número.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_email":
        if flow_manager.is_admin(user.id):
            status = "✅ Ativada" if is_email_collection_enabled() else "❌ Desativada"
            await safe_edit_message(
                f"📧 **Coleta de Email**\n\nStatus atual: {status}\n\nEscolha uma opção:",
                reply_markup=create_config_email_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_email_enable":
        if flow_manager.is_admin(user.id):
            if set_config_value('collect_email', 'true'):
                await safe_edit_message(
                    "✅ **Coleta de Email Ativada!**\n\nAgora o bot irá solicitar o email dos usuários antes de exibir o fluxo.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao ativar coleta de email.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_email_disable":
        if flow_manager.is_admin(user.id):
            if set_config_value('collect_email', 'false'):
                await safe_edit_message(
                    "❌ **Coleta de Email Desativada!**\n\nO bot não irá mais solicitar o email dos usuários.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao desativar coleta de email.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_require_signup":
        if flow_manager.is_admin(user.id):
            status = "✅ Ativado" if is_signup_required() else "❌ Desativado"
            await safe_edit_message(
                f"👤 **Exigir Cadastro**\n\nStatus atual: {status}\n\nEscolha uma opção:",
                reply_markup=create_config_signup_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_webhook":
        if flow_manager.is_admin(user.id):
            webhook_enabled = is_webhook_enabled()
            webhook_url = get_webhook_url()
            
            status = "✅ Ativado" if webhook_enabled else "❌ Desativado"
            url_status = f"🔗 {webhook_url}" if webhook_url else "❌ Não definida"
            
            message = f"🔗 **Webhook CRM**\n\n"
            message += f"Status: {status}\n"
            message += f"URL: {url_status}\n\n"
            message += "**Eventos ativos:**\n"
            message += "• Acesso ao bot\n"
            message += "• Cadastro concluído\n\n"
            message += "Escolha uma opção:"
            
            await safe_edit_message(
                message,
                reply_markup=create_webhook_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "webhook_enable":
        if flow_manager.is_admin(user.id):
            if set_config_value('webhook_enabled', 'true'):
                await safe_edit_message(
                    "✅ **Webhook CRM Ativado!**\n\nAgora você precisa definir a URL do webhook.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔗 Definir URL", callback_data="webhook_set_url")],
                        [InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")]
                    ])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao ativar webhook.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "webhook_disable":
        if flow_manager.is_admin(user.id):
            if set_config_value('webhook_enabled', 'false'):
                await safe_edit_message(
                    "❌ **Webhook CRM Desativado!**\n\nO webhook não será mais enviado.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao desativar webhook.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="config_webhook")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "webhook_set_url":
        if flow_manager.is_admin(user.id):
            context.user_data['setting_webhook_url'] = True
            await safe_edit_message(
                "🔗 **Definir URL do Webhook**\n\nDigite a URL do seu CRM:\n\nExemplo: https://seu-crm.com/webhook",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_webhook")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "webhook_change_url":
        if flow_manager.is_admin(user.id):
            context.user_data['changing_webhook_url'] = True
            current_url = get_webhook_url()
            await safe_edit_message(
                f"✏️ **Alterar URL do Webhook**\n\nURL atual: {current_url}\n\nDigite a nova URL:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_webhook")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_signup_enable":
        if flow_manager.is_admin(user.id):
            if set_config_value('require_signup', 'true'):
                await safe_edit_message(
                    "✅ **Exigir Cadastro Ativado!**\n\nAgora o bot irá solicitar o cadastro completo dos usuários antes de exibir o fluxo.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao ativar exigir cadastro.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_signup_disable":
        if flow_manager.is_admin(user.id):
            if set_config_value('require_signup', 'false'):
                await safe_edit_message(
                    "❌ **Exigir Cadastro Desativado!**\n\nO bot não irá mais exigir cadastro dos usuários.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao desativar exigir cadastro.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="admin_config")
                    ]])
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome":
        if flow_manager.is_admin(user.id):
            welcome_enabled = is_welcome_enabled()
            welcome_data = get_welcome_message()
            
            status_text = "✅ **Ativada**" if welcome_enabled else "❌ **Desativada**"
            media_text = f"🖼️ **Mídia:** {welcome_data['media_type']}" if welcome_data['media_url'] else "🖼️ **Mídia:** Nenhuma"
            text_preview = welcome_data['text'][:50] + "..." if len(welcome_data['text']) > 50 else welcome_data['text']
            text_display = f"📝 **Texto:** {text_preview}" if welcome_data['text'] else "📝 **Texto:** Nenhum"
            
            await safe_edit_message(
                f"🎬 **Configuração de Mensagem de Boas-vindas**\n\n"
                f"**Status:** {status_text}\n"
                f"{text_display}\n"
                f"{media_text}\n\n"
                f"Configure uma mensagem que será enviada antes do cadastro do usuário.",
                reply_markup=create_config_welcome_keyboard()
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_enable":
        if flow_manager.is_admin(user.id):
            if set_config_value('welcome_enabled', 'true'):
                await safe_edit_message(
                    "✅ **Mensagem de Boas-vindas Ativada!**\n\nA mensagem será enviada antes do cadastro do usuário.",
                    reply_markup=create_config_welcome_keyboard()
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao ativar mensagem de boas-vindas.",
                    reply_markup=create_config_welcome_keyboard()
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_disable":
        if flow_manager.is_admin(user.id):
            if set_config_value('welcome_enabled', 'false'):
                await safe_edit_message(
                    "❌ **Mensagem de Boas-vindas Desativada!**\n\nA mensagem não será mais enviada.",
                    reply_markup=create_config_welcome_keyboard()
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao desativar mensagem de boas-vindas.",
                    reply_markup=create_config_welcome_keyboard()
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_text":
        if flow_manager.is_admin(user.id):
            context.user_data['configuring_welcome_text'] = True
            current_text = get_config_value('welcome_text', '')
            await safe_edit_message(
                f"📝 **Editar Texto da Mensagem de Boas-vindas**\n\n"
                f"Texto atual:\n{current_text}\n\n"
                f"Digite o novo texto da mensagem de boas-vindas:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_welcome")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_photo":
        if flow_manager.is_admin(user.id):
            context.user_data['configuring_welcome_media'] = True
            context.user_data['welcome_media_type'] = 'photo'
            current_media = get_config_value('welcome_media_url', '')
            current_type = get_config_value('welcome_media_type', '')
            
            media_info = f"Tipo: {current_type}\nArquivo: {current_media}" if current_media else "Nenhuma foto configurada"
            
            await safe_edit_message(
                f"🖼️ **Definir Foto da Mensagem de Boas-vindas**\n\n"
                f"Configuração atual:\n{media_info}\n\n"
                f"Envie uma foto para usar na mensagem de boas-vindas:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_welcome")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_video":
        if flow_manager.is_admin(user.id):
            context.user_data['configuring_welcome_media'] = True
            context.user_data['welcome_media_type'] = 'video'
            current_media = get_config_value('welcome_media_url', '')
            current_type = get_config_value('welcome_media_type', '')
            
            media_info = f"Tipo: {current_type}\nArquivo: {current_media}" if current_media else "Nenhum vídeo configurado"
            
            await safe_edit_message(
                f"🎬 **Definir Vídeo da Mensagem de Boas-vindas**\n\n"
                f"Configuração atual:\n{media_info}\n\n"
                f"Envie um vídeo para usar na mensagem de boas-vindas:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_welcome")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_video_note":
        if flow_manager.is_admin(user.id):
            context.user_data['configuring_welcome_media'] = True
            context.user_data['welcome_media_type'] = 'video_note'
            current_media = get_config_value('welcome_media_url', '')
            current_type = get_config_value('welcome_media_type', '')
            
            media_info = f"Tipo: {current_type}\nArquivo: {current_media}" if current_media else "Nenhum vídeo redondo configurado"
            
            await safe_edit_message(
                f"⭕ **Definir Vídeo Redondo da Mensagem de Boas-vindas**\n\n"
                f"Configuração atual:\n{media_info}\n\n"
                f"Envie um vídeo redondo (video note) para usar na mensagem de boas-vindas.\n\n"
                f"💡 **Dica**: Você pode enviar um vídeo normal e ele será convertido automaticamente para formato redondo.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Cancelar", callback_data="config_welcome")
                ]])
            )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_remove_media":
        if flow_manager.is_admin(user.id):
            if set_config_value('welcome_media_url', '') and set_config_value('welcome_media_type', ''):
                await safe_edit_message(
                    "🗑️ **Mídia Removida!**\n\nA mensagem de boas-vindas agora será apenas texto.",
                    reply_markup=create_config_welcome_keyboard()
                )
            else:
                await safe_edit_message(
                    "❌ Erro ao remover mídia.",
                    reply_markup=create_config_welcome_keyboard()
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "config_welcome_preview":
        if flow_manager.is_admin(user.id):
            welcome_data = get_welcome_message()
            
            if not welcome_data['text'] and not welcome_data['media_url']:
                await safe_edit_message(
                    "⚠️ **Nenhuma Mensagem Configurada**\n\nConfigure um texto ou mídia primeiro.",
                    reply_markup=create_config_welcome_keyboard()
                )
                return
            
            try:
                # Simular envio da mensagem de boas-vindas
                await send_welcome_message(update, context)
                
                await safe_edit_message(
                    "👁️ **Visualização Enviada!**\n\nA mensagem de boas-vindas foi enviada acima para visualização.",
                    reply_markup=create_config_welcome_keyboard()
                )
            except Exception as e:
                await safe_edit_message(
                    f"❌ **Erro na Visualização**\n\nErro: {str(e)}",
                    reply_markup=create_config_welcome_keyboard()
                )
        else:
            await safe_edit_message("❌ Você não tem permissão de administrador.")
    
    elif query.data == "share_phone":
        # Solicitar compartilhamento de telefone via teclado personalizado
        keyboard = [
            [KeyboardButton("📱 Compartilhar Telefone", request_contact=True)],
            [KeyboardButton("🔙 Voltar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await query.message.reply_text(
            "📱 **Compartilhe seu número de telefone:**\n\nToque no botão abaixo para compartilhar automaticamente.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_contact'] = True
    
    elif query.data == "share_email":
        # Solicitar email via teclado personalizado
        keyboard = [
            [KeyboardButton("📧 Digitar Email")],
            [KeyboardButton("📱 Compartilhar Telefone", request_contact=True)],
            [KeyboardButton("🔙 Voltar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await query.message.reply_text(
            "📧 **Digite seu email ou compartilhe seu telefone:**\n\nVocê pode digitar o email ou compartilhar o telefone para continuar.",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_email_or_contact'] = True
    
    elif query.data == "type_name":
        # Solicitar digitação do nome via teclado personalizado
        keyboard = [
            [KeyboardButton("🔙 Voltar")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await query.message.reply_text(
            "👤 **Digite seu nome completo:**",
            reply_markup=reply_markup
        )
        context.user_data['waiting_for_name'] = True
    
    elif query.data == "back_to_data_collection":
        # Voltar para a tela inicial de coleta de dados
        if 'missing_data' in context.user_data:
            missing_data = context.user_data['missing_data']
            await request_missing_data(update, context, missing_data)
        else:
            await update.effective_message.reply_text("❌ Erro na coleta de dados.")
    

    
    elif query.data == "start_data_collection":
        # Iniciar coleta de dados (mantido para compatibilidade)
        if 'missing_data' in context.user_data and 'current_data_index' in context.user_data:
            missing_data = context.user_data['missing_data']
            current_index = context.user_data['current_data_index']
            
            if current_index < len(missing_data):
                data_type = missing_data[current_index]
                
                if data_type == "nome":
                    await safe_edit_message(
                        "👤 **Digite seu nome completo:**",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                        ]])
                    )
                    context.user_data['waiting_for_name'] = True
                elif data_type == "telefone":
                    await safe_edit_message(
                        "📱 **Digite seu número de telefone:**\n\nFormato: (11) 99999-9999",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                        ]])
                    )
                    context.user_data['waiting_for_phone'] = True
                elif data_type == "email":
                    await safe_edit_message(
                        "📧 **Digite seu email:**\n\nExemplo: usuario@exemplo.com",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("🔙 Cancelar", callback_data="cancel_data_collection")
                        ]])
                    )
                    context.user_data['waiting_for_email'] = True
            else:
                # Todos os dados foram coletados
                await finish_data_collection(query, context)
        else:
            await query.message.reply_text("❌ Erro na coleta de dados.")
    
    elif query.data == "cancel_data_collection":
        # Cancelar coleta de dados
        context.user_data.clear()
        await query.message.reply_text(
            "❌ **Coleta de Dados Cancelada**\n\nVocê pode tentar novamente enviando /start",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Tentar Novamente", callback_data="restart_data_collection")
            ]])
        )
    
    elif query.data == "restart_data_collection":
        # Reiniciar coleta de dados
        user = update.effective_user
        
        # Verificar configurações novamente
        require_signup = is_signup_required()
        collect_phone = is_phone_collection_enabled()
        collect_email = is_email_collection_enabled()
        
        user_data = get_user_data(user.id)
        
        missing_data = []
        if require_signup and not user_data.get('name'):
            missing_data.append("nome")
        if collect_phone and not user_data.get('phone'):
            missing_data.append("telefone")
        if collect_email and not user_data.get('email'):
            missing_data.append("email")
        
        if missing_data:
            context.user_data['collecting_data'] = True
            context.user_data['missing_data'] = missing_data
            context.user_data['current_data_index'] = 0
            
            await request_missing_data(update, context, missing_data)
        else:
            await query.message.reply_text("✅ Todos os dados já foram fornecidos!")
    

    
    elif query.data == "start_flow":
        # Executar fluxo padrão
        flows = flow_manager.get_active_flows()
        if flows:
            default_flow = flows[0]  # Primeiro fluxo ativo
            await execute_flow(query, default_flow['id'])
        else:
            await query.message.reply_text("❌ Nenhum fluxo configurado.")

async def execute_flow(query, flow_id):
    """Executa um fluxo específico"""
    flow_manager = FlowManager()
    steps = flow_manager.get_flow_steps(flow_id)
    
    if not steps:
        await query.message.reply_text("❌ Fluxo vazio ou não encontrado.")
        return
    
    # Executar primeira etapa
    await execute_step(query, steps[0])

async def execute_complete_flow(update, steps):
    """Executa todas as etapas de um fluxo"""
    print(f"🔍 DEBUG: execute_complete_flow - Executando {len(steps)} steps")
    
    for i, step in enumerate(steps):
        try:
            print(f"🔍 DEBUG: Step {i+1}/{len(steps)} - Tipo: {step.get('step_type')} - ID: {step.get('id')}")
            
            # Pré-processamento comum para todos os steps com botões
            buttons = []
            if step.get('buttons'):
                for button in step['buttons']:
                    if button['button_type'] == 'url':
                        buttons.append([InlineKeyboardButton(button['button_text'], url=button['button_data'])])
                    else:
                        buttons.append([InlineKeyboardButton(button['button_text'], callback_data=button['button_data'])])
            
            keyboard = InlineKeyboardMarkup(buttons) if buttons else None

            if step['step_type'] == 'text':
                await update.message.reply_text(step['content'], reply_markup=keyboard)

            elif step['step_type'] == 'image':
                print(f"🔍 DEBUG: Processando step de imagem")
                print(f"🔍 DEBUG: Step completo: {step}")
                await handle_media_send(
                    update,
                    step,
                    keyboard,
                    media_type='photo',
                    method=update.message.reply_photo
                )

            elif step['step_type'] == 'video':
                await handle_media_send(
                    update,
                    step,
                    keyboard,
                    media_type='video',
                    method=update.message.reply_video
                )

            elif step['step_type'] == 'video_note':
                print(f"🔍 DEBUG: Tentando enviar video_note")
                
                if step.get('file_id'):
                    try:
                        print(f"🔍 DEBUG: Enviando video_note via file_id")
                        # Para vídeos redondos, usar reply_video_note
                        print(f"🔍 DEBUG: Enviando como reply_video_note")
                        await update.message.reply_video_note(
                            video_note=step['file_id']
                        )
                        
                        # Enviar texto separadamente (video notes não suportam caption)
                        if step.get('content'):
                            await update.message.reply_text(
                                step.get('content', ''),
                                reply_markup=keyboard
                            )
                    except Exception as e:
                        print(f"🔍 DEBUG: Erro no video_note (file_id): {e}")
                        await handle_video_note_fallback(update, step, keyboard)
                
                elif step.get('media_url'):
                    try:
                        print(f"🔍 DEBUG: Enviando video_note via media_url")
                        
                        if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                            print(f"🔍 DEBUG: Usando arquivo local: {step['media_url']}")
                            with open(step['media_url'], 'rb') as f:
                                file_data = f.read()
                            print(f"🔍 DEBUG: Arquivo lido, tamanho: {len(file_data)} bytes")
                            
                            # Validar requisitos antes de enviar
                            print(f"🔍 DEBUG: Validando requisitos do video note antes do envio...")
                            is_valid, validation_message = await validate_video_note_requirements(file_data)
                            
                            if not is_valid:
                                print(f"🔍 DEBUG: Video note inválido: {validation_message}")
                                
                                # Tentar conversão automática
                                print(f"🔧 DEBUG: Tentando conversão automática...")
                                conversion_success, converted_data, conversion_message = await convert_video_to_video_note(file_data)
                                
                                if conversion_success:
                                    print(f"🔧 DEBUG: Conversão bem-sucedida: {conversion_message}")
                                    
                                    # Substituir o arquivo original pelo convertido
                                    try:
                                        print(f"🔧 DEBUG: Substituindo arquivo original pelo convertido...")
                                        
                                        # Salvar vídeo convertido no lugar do original
                                        if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                                            # Para arquivos locais, substituir diretamente
                                            with open(step['media_url'], 'wb') as f:
                                                f.write(converted_data)
                                            
                                            print(f"🔧 DEBUG: ✅ Arquivo original substituído: {step['media_url']}")
                                            
                                            # Atualizar o banco de dados para marcar como convertido
                                            from flow_manager import update_step_media_url
                                            update_step_media_url(step['id'], step['media_url'])
                                            
                                        else:
                                            # Para URLs remotas, salvar localmente
                                            temp_filename = f"converted_{int(asyncio.get_event_loop().time())}.mp4"
                                            temp_path = UPLOADS_DIR / "video_note" / temp_filename
                                            temp_path.parent.mkdir(exist_ok=True)
                                            
                                            with open(temp_path, 'wb') as f:
                                                f.write(converted_data)
                                            
                                            # Atualizar o banco de dados com o novo caminho
                                            from flow_manager import update_step_media_url
                                            update_step_media_url(step['id'], str(temp_path))
                                            
                                            print(f"🔧 DEBUG: ✅ Arquivo convertido salvo: {temp_path}")
                                        
                                    except Exception as e:
                                        print(f"🔧 DEBUG: ⚠️ Erro ao substituir arquivo: {e}")
                                    
                                    # Enviar vídeo convertido com retry
                                    max_retries = 3
                                    for attempt in range(max_retries):
                                        try:
                                            print(f"🔧 DEBUG: Tentativa {attempt + 1}/{max_retries} de envio")
                                            
                                            # Enviar vídeo convertido como video_note com timeout
                                            await asyncio.wait_for(
                                                update.message.reply_video_note(
                                                    video_note=converted_data
                                                ),
                                                timeout=30.0  # 30 segundos de timeout
                                            )
                                            
                                            # Enviar texto separadamente (video notes não suportam caption)
                                            if step.get('content'):
                                                await update.message.reply_text(
                                                    step.get('content', ''),
                                                    reply_markup=keyboard
                                                )
                                            
                                            print(f"🔧 DEBUG: ✅ Envio bem-sucedido na tentativa {attempt + 1}")
                                            break
                                            
                                        except asyncio.TimeoutError:
                                            print(f"🔧 DEBUG: ⏰ Timeout na tentativa {attempt + 1}")
                                            if attempt == max_retries - 1:
                                                await update.message.reply_text(
                                                    f"⚠️ **Timeout no Envio**\n\n"
                                                    "O vídeo foi convertido com sucesso, mas houve timeout no envio.\n"
                                                    "Tente novamente em alguns segundos.",
                                                    reply_markup=keyboard
                                                )
                                            else:
                                                await asyncio.sleep(2)  # Aguardar 2 segundos antes da próxima tentativa
                                                
                                        except Exception as e:
                                            print(f"🔧 DEBUG: ❌ Erro na tentativa {attempt + 1}: {e}")
                                            if attempt == max_retries - 1:
                                                await update.message.reply_text(
                                                    f"❌ **Erro no Envio**\n\n"
                                                    "O vídeo foi convertido, mas houve erro no envio.\n"
                                                    "Tente novamente.",
                                                    reply_markup=keyboard
                                                )
                                            else:
                                                await asyncio.sleep(2)
                                else:
                                    print(f"🔧 DEBUG: Conversão falhou: {conversion_message}")
                                    await update.message.reply_text(
                                        f"❌ **Erro ao enviar video note**\n\n{validation_message}\n\n"
                                        "Tentativa de conversão automática falhou.\n"
                                        "O vídeo não atende aos requisitos do Telegram.",
                                        reply_markup=keyboard
                                    )
                                return
                            
                            print(f"🔍 DEBUG: {validation_message}")
                            
                            # Para vídeos redondos, usar reply_video_note
                            print(f"🔍 DEBUG: Enviando como reply_video_note")
                            await update.message.reply_video_note(
                                video_note=file_data
                            )
                            
                            # Enviar texto separadamente (video notes não suportam caption)
                            if step.get('content'):
                                await update.message.reply_text(
                                    step.get('content', ''),
                                    reply_markup=keyboard
                                )
                        else:
                            # Verificar se é um arquivo local (mesmo que não comece com 'uploads/')
                            if not step['media_url'].startswith(('http://', 'https://', 'ftp://')):
                                print(f"🔍 DEBUG: Usando arquivo local: {step['media_url']}")
                                try:
                                    # Tentar abrir como arquivo local
                                    with open(step['media_url'], 'rb') as f:
                                        file_data = f.read()
                                    print(f"🔍 DEBUG: Arquivo local lido, tamanho: {len(file_data)} bytes")
                                    
                                    # Validar requisitos antes de enviar
                                    print(f"🔍 DEBUG: Validando requisitos do video note antes do envio...")
                                    is_valid, validation_message = await validate_video_note_requirements(file_data)
                                    
                                    if not is_valid:
                                        print(f"🔍 DEBUG: Video note inválido: {validation_message}")
                                        
                                        # Tentar conversão automática
                                        print(f"🔧 DEBUG: Tentando conversão automática...")
                                        conversion_success, converted_data, conversion_message = await convert_video_to_video_note(file_data)
                                        
                                        if conversion_success:
                                            print(f"🔧 DEBUG: Conversão bem-sucedida: {conversion_message}")
                                            
                                            # Substituir o arquivo original pelo convertido
                                            try:
                                                print(f"🔧 DEBUG: Substituindo arquivo original pelo convertido...")
                                                
                                                # Salvar vídeo convertido no lugar do original
                                                with open(step['media_url'], 'wb') as f:
                                                    f.write(converted_data)
                                                
                                                print(f"🔧 DEBUG: ✅ Arquivo original substituído: {step['media_url']}")
                                                
                                                # Atualizar o banco de dados para marcar como convertido
                                                from flow_manager import update_step_media_url
                                                update_step_media_url(step['id'], step['media_url'])
                                                
                                            except Exception as e:
                                                print(f"🔧 DEBUG: ⚠️ Erro ao substituir arquivo: {e}")
                                            
                                            # Enviar vídeo convertido com retry
                                            max_retries = 3
                                            for attempt in range(max_retries):
                                                try:
                                                    print(f"🔧 DEBUG: Tentativa {attempt + 1}/{max_retries} de envio")
                                                    
                                                    # Enviar vídeo convertido como video_note com timeout
                                                    await asyncio.wait_for(
                                                        update.message.reply_video_note(
                                                            video_note=converted_data
                                                        ),
                                                        timeout=30.0  # 30 segundos de timeout
                                                    )
                                                    
                                                    # Enviar texto separadamente (video notes não suportam caption)
                                                    if step.get('content'):
                                                        await update.message.reply_text(
                                                            step.get('content', ''),
                                                            reply_markup=keyboard
                                                        )
                                                    
                                                    
                                                    print(f"🔧 DEBUG: ✅ Envio bem-sucedido na tentativa {attempt + 1}")
                                                    break
                                                    
                                                except asyncio.TimeoutError:
                                                    print(f"🔧 DEBUG: ⏰ Timeout na tentativa {attempt + 1}")
                                                    if attempt == max_retries - 1:
                                                        await update.message.reply_text(
                                                            f"⚠️ **Timeout no Envio**\n\n"
                                                            "O vídeo foi convertido com sucesso, mas houve timeout no envio.\n"
                                                            "Tente novamente em alguns segundos.",
                                                            reply_markup=keyboard
                                                        )
                                                    else:
                                                        await asyncio.sleep(2)  # Aguardar 2 segundos antes da próxima tentativa
                                                        
                                                except Exception as e:
                                                    print(f"🔧 DEBUG: ❌ Erro na tentativa {attempt + 1}: {e}")
                                                    if attempt == max_retries - 1:
                                                        await update.message.reply_text(
                                                            f"❌ **Erro no Envio**\n\n"
                                                            "O vídeo foi convertido, mas houve erro no envio.\n"
                                                            "Tente novamente.",
                                                            reply_markup=keyboard
                                                        )
                                                    else:
                                                        await asyncio.sleep(2)
                                        else:
                                            print(f"🔧 DEBUG: Conversão falhou: {conversion_message}")
                                            await update.message.reply_text(
                                                f"❌ **Erro ao enviar video note**\n\n{validation_message}\n\n"
                                                "Tentativa de conversão automática falhou.\n"
                                                "O vídeo não atende aos requisitos do Telegram.",
                                                reply_markup=keyboard
                                            )
                                        return
                                    
                                    print(f"🔍 DEBUG: {validation_message}")
                                    
                                    # Para vídeos redondos, usar reply_video_note
                                    print(f"🔍 DEBUG: Enviando como reply_video_note")
                                    await update.message.reply_video_note(
                                        video_note=file_data
                                    )
                                    
                                    # Enviar texto separadamente (video notes não suportam caption)
                                    if step.get('content'):
                                        await update.message.reply_text(
                                            step.get('content', ''),
                                            reply_markup=keyboard
                                        )
                                        
                                except FileNotFoundError:
                                    print(f"🔍 DEBUG: Arquivo local não encontrado: {step['media_url']}")
                                    await handle_video_note_fallback(update, step, keyboard)
                                except Exception as e:
                                    print(f"🔍 DEBUG: Erro ao ler arquivo local: {e}")
                                    await handle_video_note_fallback(update, step, keyboard)
                            else:
                                print(f"🔍 DEBUG: Usando URL remota: {step['media_url']}")
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(step['media_url']) as response:
                                        if response.status == 200:
                                                                                    file_data = await response.read()
                                        print(f"🔍 DEBUG: Arquivo baixado, tamanho: {len(file_data)} bytes")
                                        
                                        # Validar requisitos antes de enviar
                                        print(f"🔍 DEBUG: Validando requisitos do video note antes do envio...")
                                        is_valid, validation_message = await validate_video_note_requirements(file_data)
                                        
                                        if not is_valid:
                                            print(f"🔍 DEBUG: Video note inválido: {validation_message}")
                                            
                                            # Tentar conversão automática
                                            print(f"🔧 DEBUG: Tentando conversão automática (URL)...")
                                            conversion_success, converted_data, conversion_message = await convert_video_to_video_note(file_data)
                                            
                                            if conversion_success:
                                                print(f"🔧 DEBUG: Conversão bem-sucedida (URL): {conversion_message}")
                                                
                                                # Substituir o arquivo original pelo convertido
                                                try:
                                                    print(f"🔧 DEBUG: Substituindo arquivo original pelo convertido (URL)...")
                                                    
                                                    # Para URLs remotas, salvar localmente
                                                    temp_filename = f"converted_{int(asyncio.get_event_loop().time())}.mp4"
                                                    temp_path = UPLOADS_DIR / "video_note" / temp_filename
                                                    temp_path.parent.mkdir(exist_ok=True)
                                                    
                                                    with open(temp_path, 'wb') as f:
                                                        f.write(converted_data)
                                                    
                                                    # Atualizar o banco de dados com o novo caminho
                                                    from flow_manager import update_step_media_url
                                                    update_step_media_url(step['id'], str(temp_path))
                                                    
                                                    print(f"🔧 DEBUG: ✅ Arquivo convertido salvo: {temp_path}")
                                                    
                                                except Exception as e:
                                                    print(f"🔧 DEBUG: ⚠️ Erro ao substituir arquivo (URL): {e}")
                                                
                                                # Enviar vídeo convertido com retry
                                                max_retries = 3
                                                for attempt in range(max_retries):
                                                    try:
                                                        print(f"🔧 DEBUG: Tentativa {attempt + 1}/{max_retries} de envio (URL)")
                                                        
                                                        # Enviar vídeo convertido como video_note com timeout
                                                        await asyncio.wait_for(
                                                            update.message.reply_video_note(
                                                                video_note=converted_data
                                                            ),
                                                            timeout=30.0  # 30 segundos de timeout
                                                        )
                                                        
                                                        # Enviar texto separadamente (video notes não suportam caption)
                                                        if step.get('content'):
                                                            await update.message.reply_text(
                                                                step.get('content', ''),
                                                                reply_markup=keyboard
                                                            )
                                                        
                                                        
                                                        print(f"🔧 DEBUG: ✅ Envio bem-sucedido na tentativa {attempt + 1} (URL)")
                                                        break
                                                        
                                                    except asyncio.TimeoutError:
                                                        print(f"🔧 DEBUG: ⏰ Timeout na tentativa {attempt + 1} (URL)")
                                                        if attempt == max_retries - 1:
                                                            await update.message.reply_text(
                                                                f"⚠️ **Timeout no Envio**\n\n"
                                                                "O vídeo foi convertido com sucesso, mas houve timeout no envio.\n"
                                                                "Tente novamente em alguns segundos.",
                                                                reply_markup=keyboard
                                                            )
                                                        else:
                                                            await asyncio.sleep(2)  # Aguardar 2 segundos antes da próxima tentativa
                                                            
                                                    except Exception as e:
                                                        print(f"🔧 DEBUG: ❌ Erro na tentativa {attempt + 1} (URL): {e}")
                                                        if attempt == max_retries - 1:
                                                            await update.message.reply_text(
                                                                f"❌ **Erro no Envio**\n\n"
                                                                "O vídeo foi convertido, mas houve erro no envio.\n"
                                                                "Tente novamente.",
                                                                reply_markup=keyboard
                                                            )
                                                        else:
                                                            await asyncio.sleep(2)
                                            else:
                                                print(f"🔧 DEBUG: Conversão falhou (URL): {conversion_message}")
                                                await update.message.reply_text(
                                                    f"❌ **Erro ao enviar video note**\n\n{validation_message}\n\n"
                                                    "Tentativa de conversão automática falhou.\n"
                                                    "O vídeo não atende aos requisitos do Telegram.",
                                                    reply_markup=keyboard
                                                )
                                            return
                                        
                                        print(f"🔍 DEBUG: {validation_message}")
                                        
                                        # Para vídeos redondos, usar reply_video_note
                                        print(f"🔍 DEBUG: Enviando como reply_video_note")
                                        await update.message.reply_video_note(
                                            video_note=file_data
                                        )
                                        
                                        # Enviar texto separadamente (video notes não suportam caption)
                                        if step.get('content'):
                                            await update.message.reply_text(
                                                step.get('content', ''),
                                                reply_markup=keyboard
                                            )
#                                     else:
                                        raise Exception(f"HTTP {response.status}")
                    except Exception as e:
                        print(f"🔍 DEBUG: Erro no video_note (media_url): {e}")
                        await handle_video_note_fallback(update, step, keyboard)
                else:
                    await handle_fallback(update, step, keyboard)

            elif step['step_type'] == 'button':
                await update.message.reply_text(
                    step['content'] or "Escolha uma opção:",
                    reply_markup=keyboard
                )

            # Pequena pausa entre as mensagens
            await asyncio.sleep(0.5)
            
        except Exception as e:
            print(f"Erro ao executar etapa {i+1}: {e}")
            continue

async def handle_media_send(update, step, keyboard, media_type, method):
    """Manipula o envio de mídia genérica"""
    print(f"🔍 DEBUG: handle_media_send - Tipo: {media_type}")
    print(f"🔍 DEBUG: Step data: {step}")
    print(f"🔍 DEBUG: Tem file_id: {step.get('file_id')}")
    print(f"🔍 DEBUG: Tem media_url: {step.get('media_url')}")
    print(f"🔍 DEBUG: Tem content: {step.get('content')}")
    
    try:
        if step.get('file_id'):
            print(f"🔍 DEBUG: Enviando via file_id: {step['file_id']}")
            await method(
                **{media_type: step['file_id']},
                caption=step.get('content', ''),
                reply_markup=keyboard
            )
            print(f"🔍 DEBUG: ✅ Envio via file_id bem-sucedido")
        elif step.get('media_url'):
            print(f"🔍 DEBUG: Enviando via media_url: {step['media_url']}")
            
            if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                print(f"🔍 DEBUG: Usando arquivo local: {step['media_url']}")
                try:
                    with open(step['media_url'], 'rb') as f:
                        file_data = f.read()
                    print(f"🔍 DEBUG: Arquivo lido, tamanho: {len(file_data)} bytes")
                    
                    await method(
                        **{media_type: file_data},
                        caption=step.get('content', ''),
                        reply_markup=keyboard
                    )
                    print(f"🔍 DEBUG: ✅ Envio de arquivo local bem-sucedido")
                except FileNotFoundError:
                    print(f"🔍 DEBUG: ❌ Arquivo não encontrado: {step['media_url']}")
                    raise Exception(f"Arquivo não encontrado: {step['media_url']}")
                except Exception as e:
                    print(f"🔍 DEBUG: ❌ Erro ao ler arquivo local: {e}")
                    raise e
            else:
                print(f"🔍 DEBUG: Usando URL remota: {step['media_url']}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(step['media_url']) as response:
                        if response.status == 200:
                            file_data = await response.read()
                            print(f"🔍 DEBUG: Arquivo baixado, tamanho: {len(file_data)} bytes")
                            
                            await method(
                                **{media_type: file_data},
                                caption=step.get('content', ''),
                                reply_markup=keyboard
                            )
                            print(f"🔍 DEBUG: ✅ Envio de URL remota bem-sucedido")
                        else:
                            print(f"🔍 DEBUG: ❌ HTTP {response.status} para URL: {step['media_url']}")
                            raise Exception(f"HTTP {response.status}")
        else:
            print(f"🔍 DEBUG: ❌ Nenhum file_id ou media_url encontrado, usando fallback")
            await handle_fallback(update, step, keyboard)
    except Exception as e:
        print(f"🔍 DEBUG: ❌ Erro ao enviar {media_type}: {e}")
        await handle_fallback(update, step, keyboard)

async def handle_fallback(update, step, keyboard):
    """Fallback genérico quando o envio de mídia falha"""
    await update.message.reply_text(
        f"{step.get('content', 'Conteúdo não disponível')}",
        reply_markup=keyboard
    )

async def handle_video_note_fallback(update, step, keyboard):
    """Fallback específico para video_note"""
    try:
        if step.get('media_url'):
            if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                with open(step['media_url'], 'rb') as f:
                    await update.message.reply_video(
                        video=f,
                        caption=step.get('content', ''),
                        reply_markup=keyboard,
                        width=512,
                        height=512
                    )
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get(step['media_url']) as response:
                        if response.status == 200:
                            await update.message.reply_video(
                                video=await response.read(),
                                caption=step.get('content', ''),
                                reply_markup=keyboard,
                                width=512,
                                height=512
                            )
                        else:
                            await handle_fallback(update, step, keyboard)
        else:
            await handle_fallback(update, step, keyboard)
    except Exception as e:
        print(f"🔍 DEBUG: Fallback para video_note também falhou: {e}")
        await handle_fallback(update, step, keyboard)


async def execute_step(query, step):
    """Executa uma etapa específica"""
    if step['step_type'] == 'text':
        # Verificar se há botões para este step de texto
        buttons = []
        if step.get('buttons'):
            for button in step['buttons']:
                if button['button_type'] == 'url':
                    buttons.append([InlineKeyboardButton(button['button_text'], url=button['button_data'])])
                else:
                    buttons.append([InlineKeyboardButton(button['button_text'], callback_data=button['button_data'])])
        
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await safe_edit_message(step['content'], reply_markup=keyboard)
    elif step['step_type'] == 'image':
        if step['media_url']:
            try:
                # Verificar se é um arquivo local
                if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                    # Arquivo local
                    with open(step['media_url'], 'rb') as f:
                        file_data = f.read()
                    await query.edit_message_media(
                        media=InputMediaPhoto(file_data, caption=step['content'] or "")
                    )
                else:
                    # URL remota
                    await query.edit_message_media(
                        media=InputMediaPhoto(step['media_url'], caption=step['content'] or "")
                    )
            except Exception as e:
                print(f"Erro ao editar imagem: {e}")
    elif step['step_type'] == 'video':
        if step['media_url']:
            try:
                # Verificar se é um arquivo local
                if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                    # Arquivo local
                    with open(step['media_url'], 'rb') as f:
                        file_data = f.read()
                    await query.edit_message_media(
                        media=InputMediaVideo(file_data, caption=step['content'] or "")
                    )
                else:
                    # URL remota
                    await query.edit_message_media(
                        media=InputMediaVideo(step['media_url'], caption=step['content'] or "")
                    )
            except Exception as e:
                print(f"Erro ao editar vídeo: {e}")
    elif step['step_type'] == 'video_note':
        # Para vídeos redondos, sempre usar reply_video com dimensões 512x512
        # O Telegram só aceita vídeos redondos reais no sendVideoNote
        is_converted_video = True
        
        if step['media_url']:
            try:
                # Verificar se é um arquivo local
                if step['media_url'].startswith('uploads/') or step['media_url'].startswith('uploads\\'):
                    # Arquivo local
                    with open(step['media_url'], 'rb') as f:
                        file_data = f.read()
                    
                    # Validar requisitos antes de enviar
                    print(f"🔍 DEBUG: Validando requisitos do video note em execute_step...")
                    is_valid, validation_message = await validate_video_note_requirements(file_data)
                    
                    if not is_valid:
                        print(f"🔍 DEBUG: Video note inválido em execute_step: {validation_message}")
                        
                        # Tentar conversão automática
                        print(f"🔧 DEBUG: Tentando conversão automática em execute_step...")
                        conversion_success, converted_data, conversion_message = await convert_video_to_video_note(file_data)
                        
                        if conversion_success:
                            print(f"🔧 DEBUG: Conversão bem-sucedida em execute_step: {conversion_message}")
                            
                            # Substituir o arquivo original pelo convertido
                            try:
                                print(f"🔧 DEBUG: Substituindo arquivo original pelo convertido em execute_step...")
                                
                                # Salvar vídeo convertido no lugar do original
                                with open(step['media_url'], 'wb') as f:
                                    f.write(converted_data)
                                
                                print(f"🔧 DEBUG: ✅ Arquivo original substituído: {step['media_url']}")
                                
                                # Atualizar o banco de dados para marcar como convertido
                                from flow_manager import update_step_media_url
                                update_step_media_url(step['id'], step['media_url'])
                                
                            except Exception as e:
                                print(f"🔧 DEBUG: ⚠️ Erro ao substituir arquivo em execute_step: {e}")
                            
                            # Enviar vídeo convertido
                            await query.message.reply_video_note(video_note=converted_data)
                            
                            # Enviar texto separadamente (video notes não suportam caption)
                            if step.get('content'):
                                await query.message.reply_text(step['content'])
                            
                        else:
                            print(f"🔧 DEBUG: Conversão falhou em execute_step: {conversion_message}")
                            await query.message.reply_text(
                                f"❌ **Erro ao enviar video note**\n\n{validation_message}\n\n"
                                "Tentativa de conversão automática falhou.\n"
                                "O vídeo não atende aos requisitos do Telegram."
                            )
                        return
                    
                    print(f"🔍 DEBUG: {validation_message}")
                    
                    # Para vídeos redondos, sempre usar reply_video_note
                    await query.message.reply_video_note(video_note=file_data)
                    
                    # Enviar texto separadamente (video notes não suportam caption)
                    if step.get('content'):
                        await query.message.reply_text(step['content'])
                else:
                    # URL remota (fallback)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(step['media_url']) as response:
                            if response.status == 200:
                                file_data = await response.read()
                                
                                # Validar requisitos antes de enviar
                                print(f"🔍 DEBUG: Validando requisitos do video note em execute_step (URL)...")
                                is_valid, validation_message = await validate_video_note_requirements(file_data)
                                
                                if not is_valid:
                                    print(f"🔍 DEBUG: Video note inválido em execute_step (URL): {validation_message}")
                                    await query.message.reply_text(
                                        f"❌ **Erro ao enviar video note**\n\n{validation_message}\n\n"
                                        "O vídeo não atende aos requisitos do Telegram.",
                                    )
                                    return
                                
                                print(f"🔍 DEBUG: {validation_message}")
                                
                                # Para vídeos redondos, sempre usar reply_video_note
                                await query.message.reply_video_note(video_note=file_data)
                                
                                # Enviar texto separadamente (video notes não suportam caption)
                                if step.get('content'):
                                    await query.message.reply_text(step['content'])
                            else:
                                await safe_edit_message("Vídeo redondo não disponível")
            except Exception as e:
                print(f"Erro ao enviar vídeo redondo: {e}")
                await safe_edit_message("Vídeo redondo não disponível")
        else:
            await safe_edit_message(step['content'] or "")
    elif step['step_type'] == 'button':
        # Criar botões inline
        buttons = []
        if step['button_text']:
            buttons.append([InlineKeyboardButton(step['button_text'], callback_data=f"step_{step['id']}")])
        
        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        await safe_edit_message(
            step['content'] or "Escolha uma opção:",
            reply_markup=keyboard
        )

def get_user_data(telegram_id):
    """Obtém dados adicionais do usuário"""
    connection = create_connection()
    if connection is None:
        return {}
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT name, phone, email, additional_data 
        FROM users 
        WHERE telegram_id = %s
        """
        cursor.execute(query, (telegram_id,))
        result = cursor.fetchone()
        
        if result:
            return result
        else:
            return {}
            
    except Error as e:
        print(f"Erro ao obter dados do usuário: {e}")
        return {}
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def update_user_data(telegram_id, data):
    """Atualiza dados adicionais do usuário"""
    connection = create_connection()
    if connection is None:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Construir query dinamicamente baseada nos dados fornecidos
        update_fields = []
        values = []
        
        if 'name' in data:
            update_fields.append("name = %s")
            values.append(data['name'])
        if 'phone' in data:
            update_fields.append("phone = %s")
            values.append(data['phone'])
        if 'email' in data:
            update_fields.append("email = %s")
            values.append(data['email'])
        if 'additional_data' in data:
            update_fields.append("additional_data = %s")
            values.append(data['additional_data'])
        
        if not update_fields:
            return False
        
        values.append(telegram_id)
        query = f"UPDATE users SET {', '.join(update_fields)} WHERE telegram_id = %s"
        
        cursor.execute(query, values)
        connection.commit()
        return True
        
    except Error as e:
        print(f"Erro ao atualizar dados do usuário: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

async def request_missing_data(update, context, missing_data):
    """Solicita dados faltantes do usuário"""
    user = update.effective_user
    
    print(f"🔍 DEBUG: request_missing_data - Usuário {user.id} - Dados faltantes: {missing_data}")

    # Enviar vídeo redondo de boas-vindas antes do cadastro (se configurado)
    from flow_manager import send_welcome_video_note_for_signup
    print(f"🔍 DEBUG: Chamando send_welcome_video_note_for_signup para usuário {user.id}")
    video_sent = await send_welcome_video_note_for_signup(update, context)
    print(f"🔍 DEBUG: Resultado send_welcome_video_note_for_signup: {video_sent}")
    
    # Aguardar um pouco se o vídeo foi enviado
    if video_sent:
        print(f"🔍 DEBUG: Vídeo enviado, aguardando 1 segundo...")
        await asyncio.sleep(1)

    # Definir estado de coleta de dados
    context.user_data['collecting_data'] = True
    context.user_data['missing_data'] = missing_data
    context.user_data['current_data_index'] = 0

    # Verificar dados já coletados para atualizar a lista
    collected_phone = context.user_data.get('collected_phone', None)
    collected_email = context.user_data.get('collected_email', None)
    
    # Filtrar dados que ainda faltam
    remaining_data = []
    for data_type in missing_data:
        if data_type == "telefone" and collected_phone is None:
            remaining_data.append(data_type)
        elif data_type == "email" and collected_email is None:
            remaining_data.append(data_type)
        elif data_type not in ["telefone", "email"]:
            remaining_data.append(data_type)
    
    # Atualizar missing_data com apenas os dados que faltam
    context.user_data['missing_data'] = remaining_data
    
    # Mensagem inicial
    message = "📋 *Cadastro Necessário*\n\n"
    message += "Para continuar, precisamos de algumas informações:\n\n"

    for i, data_type in enumerate(remaining_data, 1):
        message += f"{i}. {data_type.title()}\n"

    message += "\nUse os botões abaixo para compartilhar suas informações:"

    # Criar botões personalizados baseados nos dados que ainda faltam
    buttons = []
    
    # Verificar dados já coletados
    collected_data = context.user_data.get('collected_phone', None)
    has_phone = collected_data is not None
    
    collected_email = context.user_data.get('collected_email', None)
    has_email = collected_email is not None
    


    # Mostrar apenas botões para dados que ainda faltam
    if "telefone" in remaining_data and not has_phone:
        buttons.append([KeyboardButton("�� Compartilhar Telefone", request_contact=True)])
        # Definir estado para esperar contato
        context.user_data['waiting_for_contact'] = True

    if "email" in remaining_data and not has_email:
        buttons.append([KeyboardButton("📧 Enviar Email")])

    buttons.append([KeyboardButton("❌ Cancelar")])
    
    # Verificar se todos os dados foram coletados
    if not remaining_data:
        # Todos os dados foram coletados
        await finish_data_collection(update, context)
        return
    
    # Verificação adicional: se não há botões além do cancelar, finalizar
    if len(buttons) == 1:  # Só tem o botão cancelar
        await finish_data_collection(update, context)
        return
    
    # Verificação extra: se todos os dados necessários foram coletados
    required_data = ["telefone", "email"]
    collected_data = []
    if context.user_data.get('collected_phone'):
        collected_data.append("telefone")
    if context.user_data.get('collected_email'):
        collected_data.append("email")
    
    if len(collected_data) == len(required_data):
        # Todos os dados foram coletados
        await finish_data_collection(update, context)
        return

    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def finish_data_collection(update, context):
    """Finaliza a coleta de dados e executa o fluxo automaticamente"""
    user = update.effective_user
    
    # Salvar dados coletados
    collected_data = {}
    if 'collected_name' in context.user_data:
        collected_data['name'] = context.user_data['collected_name']
    if 'collected_phone' in context.user_data:
        collected_data['phone'] = context.user_data['collected_phone']
    if 'collected_email' in context.user_data:
        collected_data['email'] = context.user_data['collected_email']
    
    if collected_data:
        update_user_data(user.id, collected_data)
        
        # Enviar webhook de cadastro concluído
        user_data = {
            'telegram_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'name': collected_data.get('name'),
            'phone': collected_data.get('phone'),
            'email': collected_data.get('email')
        }
        send_webhook('cadastro_concluido', user_data)

        # Se não há fluxo padrão, mostrar mensagem
    await update.message.reply_text(
        "✅ **Cadastro foi Concluído!.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Limpar dados temporários
    context.user_data.clear()
    
    # Executar fluxo automaticamente
    flow_manager = FlowManager()
    default_flow = flow_manager.get_default_flow()
    
    if default_flow:
        steps = flow_manager.get_flow_steps(default_flow['id'])
        if steps:
            # Executar todas as etapas do fluxo
            await execute_complete_flow(update, steps)
            return
    


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

def main():
    """Função principal do bot"""
    
    # Criar tabelas se não existirem
    if not create_tables():
        print("Erro ao criar tabelas. Verifique a conexão com o banco de dados.")
        return
    
    # Obter token do bot do banco de dados ou variável de ambiente
    bot_token = get_config_value('bot_token') or os.getenv('BOT_TOKEN')
    if not bot_token:
        print("Erro: BOT_TOKEN não encontrado no banco de dados ou nas variáveis de ambiente.")
        print("Execute o script setup_initial_data.py primeiro para configurar o bot.")
        return
    
    # Criar aplicação
    application = Application.builder().token(bot_token).build()
    
    # Adicionar handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Handler para callbacks dos botões inline
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Handler para contatos compartilhados
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact_shared))
    
    # Handler específico para vídeo redondo (teste)
    application.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_media_input))
    
    # Handler para mídias (fotos, vídeos, documentos)
    application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media_input))
    
    # Handler para mensagens de texto (com prioridade para criação de fluxos)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    # Iniciar o bot
    print("Bot iniciado...")
    application.run_polling()

if __name__ == '__main__':
    main() 
