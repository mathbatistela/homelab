FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# Task data lives in SQLite here; mount a volume at /data so it survives
# container restarts and redeploys.
RUN mkdir -p /data
VOLUME ["/data"]

ENV PORT=5000
ENV DB_PATH=/data/adhd-board.db

EXPOSE 5000

CMD ["python", "src/main.py"]
