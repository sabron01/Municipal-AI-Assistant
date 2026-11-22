# Municipal AI Assistant — Tataouine

Socle documentaire du Sprint 0. Le projet est conçu comme un **monorepo** et un **monolithe modulaire DDD**, avec PostgreSQL + pgvector, RustFS, Ollama et des outils MCP internes.

## Statut
- Sprint 0 autorisé : oui.
- Développement fonctionnel métier : non démarré.
- Authentification : décision différée.
- Modèles LLM / embeddings : benchmark à réaliser avant sélection.
- Infrastructure : configuration préparatoire fournie ; non exécutée ni validée sur une machine cible.

## Structure
- `backend/` : emplacement prévu pour l'API FastAPI et les modules métier.
- `frontend/` : emplacement prévu pour React + TypeScript.
- `mcp/` : serveurs MCP internes uniquement.
- `infrastructure/` : configuration et scripts d'infrastructure.
- `docs/` : architecture, décisions, sécurité, benchmark et spécification documentaire.
- `.agents/` : profils spécialisés des agents de développement.

## Démarrage de l'infrastructure locale
1. Copier `.env.example` vers `.env`.
2. Modifier impérativement les identifiants RustFS et PostgreSQL.
3. Lancer `docker compose config` pour valider la syntaxe.
4. Lancer `docker compose up -d`.
5. Vérifier les conteneurs avec `docker compose ps`.

> Cette configuration est un socle de développement local. Elle ne constitue pas une configuration de production. Aucun service n'a été démarré depuis cet environnement d'assistance.

## Gouvernance
Lire `AGENTS.md` avant toute contribution. Toute modification de décision architecturale passe par un ADR et, si elle change le périmètre approuvé, par validation du responsable produit.
