FROM python:3.11.11-slim
WORKDIR /app
COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY worker/ /app/worker/
COPY prompts/ /app/prompts/
WORKDIR /app/worker
CMD ["python", "worker.py"]
