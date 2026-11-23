# Municipal AI Assistant — Tataouine

Monorepo et **monolithe modulaire DDD**, avec PostgreSQL + pgvector, RustFS, Ollama et des outils MCP internes. Le module Documents v1 dispose d'une implémentation backend initiale dans `backend/` et l'interface React d'administration du registre est implémentée dans `frontend/`; l'interface Documents et le dépôt de fichiers ne sont pas encore couverts.

## Statut
- Socle local : démarré et vérifié le 2026-11-22 (PostgreSQL, RustFS, Ollama, API FastAPI).
- Module Documents v1 : backend, contrôle d'accès par service et registre Direction/Service/Catégorie implémentés sur `feat/documents-v1`; l’interface React d’administration du registre est implémentée et couverte par des tests frontend, la revue QA reste à compléter.
- Authentification : comptes applicatifs et permissions par action implémentés; l'administrateur initial local est activé, avec Mailpit pour les courriels de développement.
- Modèles LLM / embeddings : benchmark à réaliser avant sélection.
- Interface React : écran d’administration du registre implémenté; l’interface Documents et le dépôt de fichiers ne sont pas encore couverts.
- Sauvegardes : procédure PostgreSQL + RustFS définie, scriptée et vérifiée localement le 2026-11-23 (voir `docs/deployment/backup-restore.md`); la fréquence et la rétention restent à décider.
- Intégration continue : workflow GitHub Actions backend (tests unitaires + intégration PostgreSQL/RustFS) et frontend (lint, tests, build) défini dans `.github/workflows/ci.yml`; première exécution sur GitHub à venir.

## Structure
- `backend/` : API FastAPI, module Documents v1, migration Alembic et tests unitaires et d'intégration.
- `frontend/` : interface React + TypeScript du registre (Vite, tests Vitest).
- `scripts/` : sauvegarde et restauration PostgreSQL + RustFS.
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
