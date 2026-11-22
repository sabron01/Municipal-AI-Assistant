# Municipal AI Assistant — Tataouine

Monorepo et **monolithe modulaire DDD**, avec PostgreSQL + pgvector, RustFS, Ollama et des outils MCP internes. Le module Documents v1 dispose d'une implémentation backend initiale dans `backend/`; l'interface frontend n'est pas encore développée.

## Statut
- Socle local : démarré et vérifié le 2026-11-22 (PostgreSQL, RustFS, Ollama, API FastAPI).
- Module Documents v1 : backend et contrôle d'accès par service implémentés sur `feat/documents-v1`; le raccordement des référentiels Service/Catégorie reste à faire.
- Authentification : comptes applicatifs et permissions par action implémentés; l'administrateur initial local est activé, avec Mailpit pour les courriels de développement.
- Modèles LLM / embeddings : benchmark à réaliser avant sélection.
- Interface React : emplacement réservé, aucun écran fonctionnel.
- Sauvegardes : non configurées ni testées.

## Structure
- `backend/` : API FastAPI, module Documents v1, migration Alembic et tests unitaires.
- `frontend/` : emplacement prévu pour React + TypeScript.
- `mcp/` : serveurs MCP internes uniquement.
- `infrastructure/` : configuration et scripts d'infrastructure.
- `docs/` : architecture, décisions, sécurité, benchmark et spécification documentaire.
- `.agents/` : profils spécialisés des agents de développement.

## Démarrage de l'infrastructure locale
1. Créer un `.env` local ignoré par Git et renseigner des identifiants locaux forts.
2. Lancer `docker compose config -q` pour valider la configuration.
3. Lancer `docker compose up -d` et vérifier `docker compose ps`. Mailpit capture les e-mails locaux sur `localhost:1025`; consulter l'interface sur `http://localhost:8025`.
4. Installer le backend depuis `backend/`, appliquer `alembic upgrade head`, puis démarrer `uvicorn municipal_assistant.app:app`.

L'API locale et les services Compose sont actuellement lancés sur les ports loopback. Le `.env` utilisé dans cet environnement contient des identifiants locaux générés et n'est pas versionné. Cette configuration n'est pas destinée à la production.

## Gouvernance
Lire `AGENTS.md` avant toute contribution. Toute modification de décision architecturale passe par un ADR et, si elle change le périmètre approuvé, par validation du responsable produit.
