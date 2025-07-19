FROM ollama/ollama:latest

# Accepter le modèle à télécharger comme argument de build
ARG MODEL_NAME=llama3.2:3b

# Démarrer le serveur Ollama en arrière-plan et télécharger le modèle
RUN ollama serve & \
    sleep 10 && \
    ollama pull ${MODEL_NAME} && \
    pkill ollama