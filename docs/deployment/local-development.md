# Déploiement local

## Prérequis
Docker Engine/Desktop et Docker Compose v2.

## Étapes
```bash
cp .env.example .env
# Remplacer les mots de passe de développement
docker compose config
docker compose up -d
docker compose ps
```

## Services
- PostgreSQL 16 avec pgvector : port 5432 par défaut.
- MinIO API : port 9000 ; console : port 9001.
- Ollama : port 11434.

Ne pas utiliser les identifiants d'exemple en environnement partagé ou en production. Les ports doivent être restreints au réseau de confiance. La configuration doit être revue avant toute exposition réseau.
