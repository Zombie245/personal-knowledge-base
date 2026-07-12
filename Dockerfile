FROM python:3.11-slim
WORKDIR /app

# Створення не-root користувача для більшої безпеки
RUN useradd -u 1000 -m appuser

COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
