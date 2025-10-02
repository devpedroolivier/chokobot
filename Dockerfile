FROM python:3.11-slim

WORKDIR /app

# instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia código e recursos
COPY app/ app/
COPY static/ static/
COPY templates/ templates/
COPY scripts/ scripts/

# cria pasta de dados
RUN mkdir -p dados

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
