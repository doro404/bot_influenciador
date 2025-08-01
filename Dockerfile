# Usar imagem Python oficial
FROM python:3.10-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copiar código do projeto
COPY . .

# Criar diretório de uploads
RUN mkdir -p uploads/video_note

# Expor porta (se necessário)
EXPOSE 8000

# Comando para executar o bot
CMD ["python", "bot.py"] 