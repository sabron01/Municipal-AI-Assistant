# ADR-003 — Stockage documentaire MinIO

- Statut : remplacé par ADR-008.
- Décision : MinIO compatible S3 pour les objets binaires (décision historique).
- Motif : séparer stockage objet et métadonnées PostgreSQL.
- Conséquences : prévoir politiques d'accès, sauvegardes, chiffrement, versioning et cycle de vie avant production. Les métadonnées restent dans PostgreSQL.
