#!/bin/bash
set -e

# Lire le modèle depuis la variable d'environnement
MODEL=${KYUTAI_LLM_MODEL:-llama3.2:3b}

echo "Starting Ollama with model: $MODEL"

# Démarrer Ollama en arrière-plan
ollama serve &
OLLAMA_PID=$!

# Attendre que le serveur soit prêt
sleep 10

# Vérifier si le modèle est déjà téléchargé
if ! ollama list | grep -q "$MODEL"; then
    echo "Model $MODEL not found. Downloading..."
    ollama pull "$MODEL"
else
    echo "Model $MODEL already available"
fi

# Warm-up du modèle
echo "Warming up model $MODEL..."
ollama run "$MODEL" "Hello" > /dev/null 2>&1 || echo "Warm-up completed"

echo "Ollama ready with model $MODEL"

# Garder le processus principal en vie
wait $OLLAMA_PID