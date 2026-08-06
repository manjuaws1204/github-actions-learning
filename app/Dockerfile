FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8080

# 2 workers is plenty for a demo; gunicorn also gives us multi-process
# metrics behaviour worth knowing about (see README note on multiprocess mode).
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "app:app"]
