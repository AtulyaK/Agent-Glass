FROM python:3.11-slim
WORKDIR /app
COPY services/evaluator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/evaluator/app ./app
COPY pkg ./pkg
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
