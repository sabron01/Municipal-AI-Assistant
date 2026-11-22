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
- RustFS API : port hôte `RUSTFS_API_PORT` (9000 par défaut) ; console : `RUSTFS_CONSOLE_PORT` (9001 par défaut). L'application configure séparément `OBJECT_STORAGE_ENDPOINT` (par exemple `http://rustfs:9000` depuis le réseau Compose); ce n'est pas un port d'écoute RustFS.
- Ollama : port 11434.

Ne pas utiliser les identifiants d'exemple en environnement partagé ou en production. Les ports doivent être restreints au réseau de confiance. La configuration doit être revue avant toute exposition réseau.
