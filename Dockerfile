FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cria usuário não-root para evitar execução privilegiada
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
COPY . .
RUN chown -R appuser:appgroup /app
USER appuser

CMD ["python", "workflow.py"]