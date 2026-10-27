FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY samples ./samples
EXPOSE 8000
# Optional: --env-file .env with XAI_API_KEY; runs on regex fallback without it
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
