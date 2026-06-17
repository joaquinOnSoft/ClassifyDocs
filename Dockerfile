# Usa la imagen oficial de Ollama como base
FROM ollama/ollama:latest

# Instala Python y otras dependencias
RUN apt-get update && apt-get install -y \
    python3-pip \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY .env ./

EXPOSE 11434 9191
ENTRYPOINT ["./scripts/entrypoint.sh"]