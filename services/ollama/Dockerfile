FROM ollama/ollama:latest

# Copier le script d'entrypoint
COPY entrypoint.sh /entrypoint.sh

# Rendre le script exécutable
RUN chmod +x /entrypoint.sh

# Définir l'entrypoint
ENTRYPOINT ["/entrypoint.sh"]