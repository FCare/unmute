FROM ollama/ollama:latest

# Accepter le modèle à télécharger comme argument de build
ARG MODEL_NAME=llama3.2:3b

# Démarrer le serveur Ollama en arrière-plan, télécharger le modèle et faire un warm-up
RUN ollama serve & \
    sleep 10 && \
    ollama pull ${MODEL_NAME} && \
    sleep 5 && \
    echo "Warming up model ${MODEL_NAME}..." && \
    ollama run ${MODEL_NAME} "Hello" && \
    pkill ollama