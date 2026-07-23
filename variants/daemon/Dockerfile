FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY rm_revenue_engine/ rm_revenue_engine/
COPY rm_pri/ rm_pri/
COPY content/ content/
COPY daily_promotion.py .
COPY static/ static/
COPY files_index.bin ./files.db

ENV PYTHONUNBUFFERED=1
EXPOSE 7860

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
