# Sprint 0 — critères de sortie

- [x] Plan Sprint 0 v1.0 approuvé par l'utilisateur.
- [x] Arborescence et gouvernance proposées dans le socle documentaire.
- [x] Six profils d'agents documentés.
- [x] ADR des décisions validées et des sujets différés.
- [x] Architecture DDD/Clean Architecture documentée.
- [x] Spécification initiale du module Documents.
- [x] Protocole de benchmark OCR / embeddings / LLM.
- [x] Configuration Docker Compose préparée.
- [x] Validation syntaxique Docker Compose sur l'environnement local (2026-11-22).
- [x] Démarrage et healthchecks PostgreSQL, RustFS; Ollama répond à son endpoint local (2026-11-22).
- [x] Persistance du volume PostgreSQL (révision Alembic) et du bucket RustFS vérifiée après recréation des conteneurs.
- [ ] Procédure de sauvegarde/restauration PostgreSQL et RustFS définie et testée.
- [ ] Validation des formats, limites et règles métier du module Documents.

## Vérifications ajoutées après Sprint 0

- [x] Migration `20261122_01` appliquée sur PostgreSQL local et révision courante vérifiée.
- [x] Bucket RustFS privé créé; smoke test S3 `put/head(SHA-256)/get` réussi et objet de test supprimé.
- [x] Tests backend : 25 réussis et 4 ignorés le 2026-11-22 (les 4 tests d'intégration PostgreSQL/RustFS nécessitent une configuration dédiée).
- [ ] Intégration automatisée complète sur PostgreSQL/RustFS et revue QA/Security indépendante.

Les règles métier relatives aux formats, tailles, identité, autorisations et conservation ne sont pas validées; les routes Documents restent donc fermées par défaut. Toute case non cochée reste inachevée.
