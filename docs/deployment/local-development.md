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
- PostgreSQL 16 avec pgvector : `127.0.0.1:5432` par défaut.
- RustFS API : `127.0.0.1:RUSTFS_API_PORT` (9000 par défaut) ; console : `127.0.0.1:RUSTFS_CONSOLE_PORT` (9001 par défaut). L'application configure séparément `OBJECT_STORAGE_ENDPOINT` (par exemple `http://rustfs:9000` depuis le réseau Compose); ce n'est pas un port d'écoute RustFS.
- Ollama : `127.0.0.1:11434`.

Les ports sont liés à la boucle locale pour le développement. Ne pas utiliser ces identifiants ni cette topologie en environnement partagé ou en production; revoir réseau, TLS, sauvegardes et secrets avant toute exposition.
