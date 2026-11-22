# Clean Architecture

Chaque module suit idéalement :
- `domain/` : entités, value objects, exceptions et règles métier confirmées.
- `application/` : use cases, DTO et ports.
- `infrastructure/` : adaptateurs PostgreSQL, MinIO, OCR et IA.
- `presentation/` : routes FastAPI, schémas HTTP et mapping.

Les dépendances source pointent vers l'intérieur. Le domaine ne dépend ni de FastAPI, ni de SQLAlchemy, ni de MinIO, ni d'Ollama.

Les modules communiquent via interfaces publiques explicites ; éviter les accès directs aux tables internes d'un autre module.
