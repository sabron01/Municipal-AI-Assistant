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

## Module Documents (fermé par défaut)

Les routes `/api/v1/documents` répondent `503` tant que la politique métier n'est pas décidée. L'activation technique se fait uniquement par configuration :

- `DOCUMENT_MAX_UPLOAD_BYTES` : taille maximale en octets, strictement positive.
- `DOCUMENT_ALLOWED_MEDIA_TYPES` : liste MIME séparée par des virgules ; seuls les types détectés par signature sont acceptés.
- `DOCUMENT_POLICY_APPROVED` : `true` seulement après validation des décisions métier et revue QA/Security.
- `OBJECT_STORAGE_ENDPOINT`, `OBJECT_STORAGE_BUCKET`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY` : accès RustFS ; `OBJECT_STORAGE_VERIFY_TLS` vaut `true` par défaut.

Si une valeur manque alors que `DOCUMENT_POLICY_APPROVED=true`, l'application refuse de démarrer avec un message explicite. Si `DOCUMENT_POLICY_APPROVED=false`, les routes restent fermées même lorsque les autres valeurs sont renseignées.
