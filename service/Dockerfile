FROM python:3.11.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# CPU-only torch (the default wheel drags in ~2 GB of CUDA libraries)
RUN pip install torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
COPY service/requirements.txt .
RUN pip install -r requirements.txt
COPY service/app.py service/schema.json ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
