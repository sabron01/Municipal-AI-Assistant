# Stockage objet documentaire
Le service local actif est RustFS, configuré dans `docker-compose.yml` (ADR-008). Ce dossier historique ne constitue pas une configuration MinIO active.

Le backend doit consommer un endpoint ObjectStorage configurable et indépendant du port API RustFS 9000; les ports API RustFS et console 9001 sont ceux du service, pas les ports d'écoute applicatifs. Bucket privé et politiques minimales sont à définir avant exécution. Aucune donnée historique MinIO n'est migrée automatiquement.
