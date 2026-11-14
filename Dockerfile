FROM python:3.11-slim

WORKDIR /app
COPY web-requirements.txt .
RUN pip install --no-cache-dir -r web-requirements.txt
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
COPY web_app.py .
COPY assistant_services.py .
COPY action_router.py task_store.py web_access.py app_monitor.py development_status.json ./
COPY templates templates
COPY static static

ENV PORT=8080
ENV PRIYA_AI_ENABLED=0
ENV PRIYA_ENV=production
ENV PRIYA_DATA_DIR=/data
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/healthz', timeout=3)"
EXPOSE 8080
CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 4 --timeout 180 --access-logfile - --error-logfile - --bind 0.0.0.0:${PORT} web_app:app"]
