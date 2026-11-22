# Clean Architecture

Chaque module suit idéalement :
- `domain/` : entités, value objects, exceptions et règles métier confirmées.
- `application/` : use cases, DTO et ports.
- `infrastructure/` : adaptateurs PostgreSQL, RustFS via le port applicatif `ObjectStorage`, OCR et IA.
- `presentation/` : routes FastAPI, schémas HTTP et mapping.

Les dépendances source pointent vers l'intérieur. Le domaine ne dépend ni de FastAPI, ni de SQLAlchemy, ni de MinIO, ni d'Ollama.

Les modules communiquent via interfaces publiques explicites ; éviter les accès directs aux tables internes d'un autre module.

Pour le module Documents v1, les contrats sont dans [la spécification](../documents/specification-v1.md). Le domaine n'importe pas SQLAlchemy, FastAPI ou SDK S3; le port de stockage reste indépendant du port réseau ObjectStorage.
