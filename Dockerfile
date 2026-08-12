# packing-agent gateway + frontend (cloud-ready)
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PACKING_OUTPUT_DIR=/app/output \
    PACKING_TRACE_DIR=/app/output/traces \
    PACKING_SKIP_SKJOLBER=1 \
    PORT=8000

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" python-dotenv openpyxl python-multipart

COPY packing_assistant ./packing_assistant
COPY gateway ./gateway
COPY frontend ./frontend
COPY knowledge ./knowledge
COPY knowledge_base ./knowledge_base
COPY scripts ./scripts
COPY docs ./docs
COPY README.md ./

RUN mkdir -p /app/output/runs /app/output/traces

EXPOSE 8000
# Cloud platforms inject $PORT — bind 0.0.0.0 so public URL works
CMD ["sh", "-c", "python -m uvicorn gateway.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
