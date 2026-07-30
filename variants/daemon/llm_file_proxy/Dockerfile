FROM python:3.11-slim

RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hf_space.py .

# Persistent storage mount point
RUN mkdir -p /data/indexes

ENV PORT=7860
EXPOSE 7860

CMD ["python", "hf_space.py"]
