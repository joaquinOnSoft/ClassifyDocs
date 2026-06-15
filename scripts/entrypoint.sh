#!/bin/bash
set -e

# Start Ollama in the background
ollama serve &
OLLAMA_PID=$!

# Wait until Ollama is ready
echo "Esperando a que Ollama inicie..."
until ollama list > /dev/null 2>&1; do
    sleep 1
done
echo "Ollama listo."

# Download the model if it does not exist
MODEL="mistral:7b-instruct-q4_K_M"
if ! ollama list | grep -q "$MODEL"; then
    echo "Downloading model $MODEL ..."
    ollama pull $MODEL
    echo "Model downloaded."
else
    echo "A model already exists."
fi

# Launch the FastAPI API
cd /app
uvicorn app.main:app --host 0.0.0.0 --port 8000

# If Uvicorn ends, kill Ollama
kill $OLLAMA_PID