FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Comando para iniciar o workflow
CMD ["python", "workflow_agentes.py"]