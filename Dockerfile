# packing-agent gateway + frontend
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PACKING_OUTPUT_DIR=/app/output \
    PACKING_TRACE_DIR=/app/output/traces

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" python-dotenv openpyxl

COPY packing_assistant ./packing_assistant
COPY gateway ./gateway
COPY frontend ./frontend
COPY knowledge ./knowledge
COPY scripts ./scripts
COPY test ./test
COPY docs ./docs
COPY README.md ./

RUN mkdir -p /app/output/runs /app/output/traces

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
