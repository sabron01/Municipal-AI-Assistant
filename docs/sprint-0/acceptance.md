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
- [x] Procédure de sauvegarde/restauration PostgreSQL et RustFS définie et testée le 2026-11-23 (voir `docs/deployment/backup-restore.md`).
- [ ] Validation des formats, limites et règles métier du module Documents.

## Vérifications ajoutées après Sprint 0

- [x] Migration `20261122_01` appliquée sur PostgreSQL local et révision courante vérifiée.
- [x] Bucket RustFS privé créé; smoke test S3 `put/head(SHA-256)/get` réussi et objet de test supprimé.
- [x] Tests backend : 77 réussis et 4 ignorés le 2026-11-23, dont 52 tests comptes/authentification (les 4 tests d'intégration PostgreSQL/RustFS nécessitent une configuration dédiée).
- [x] Intégration automatisée PostgreSQL/RustFS exécutée le 2026-11-23 sur une base dédiée migrée : 81 réussis, 0 ignoré; workflow CI backend correspondant défini dans `.github/workflows/ci.yml`.
- [x] Tests frontend du registre : 23 réussis le 2026-11-23 (Vitest + Testing Library), build et lint conformes.
- [ ] Revue QA/Security indépendante et première exécution de la CI sur GitHub.
- [x] Corrections issues de la revue QA/Security du Sprint 1 (contrastes WCAG AA, déconnexion mobile, `Cache-Control: no-store`, garde d'accès unique, message d'indisponibilité au démarrage) : 82 tests backend (4 ignorés) et 26 tests frontend réussis le 2026-11-23.

Les règles métier relatives aux formats, tailles, identité, autorisations et conservation ne sont pas validées; les routes Documents restent donc fermées par défaut. Toute case non cochée reste inachevée.
