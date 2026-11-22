# ADR-003 — Stockage documentaire MinIO

- Statut : accepté.
- Décision : MinIO compatible S3 pour les objets binaires.
- Motif : séparer stockage objet et métadonnées PostgreSQL.
- Conséquences : prévoir politiques d'accès, sauvegardes, chiffrement, versioning et cycle de vie avant production. Les métadonnées restent dans PostgreSQL.
