# Base da imagem
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia e instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código da aplicação
COPY app/ app/

# Cria pasta de dados (será sobrescrita por volume externo)
RUN mkdir -p dados

# Expõe a porta da API
EXPOSE 8000

# Comando para rodar a aplicação
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
