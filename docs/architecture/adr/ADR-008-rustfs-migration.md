# ADR-008 — Migration du stockage objet vers RustFS

- Date : 2026-11-22.
- Statut : accepté.
- Décision : RustFS est le stockage objet compatible S3 du socle local ; il remplace MinIO dans Docker Compose. PostgreSQL conserve les métadonnées documentaires.
- Motif : adopter RustFS comme implémentation du stockage objet tout en conservant l'interface S3 attendue par les clients.
- Configuration : image RustFS `rustfs/rustfs-x86-musl:v2.3.1`, API S3 sur le port 9000, console sur le port 9001 et données persistées dans le volume `rustfs_data`. Les clés sont fournies par `RUSTFS_ACCESS_KEY` et `RUSTFS_SECRET_KEY`.
- Le port de service RustFS est distinct du port d'écoute éventuel de l'application ObjectStorage. Le backend reçoit un endpoint configurable (`OBJECT_STORAGE_ENDPOINT`, par exemple `http://rustfs:9000` sur le réseau Compose) et ne doit pas coder le port 9000 dans le domaine ni dans son contrat `ObjectStorage`. Le port hôte RustFS reste piloté par `RUSTFS_API_PORT`; aucun port API applicatif n'est dérivé de lui.
- Compatibilité de configuration : Compose accepte temporairement les variables locales historiques `MINIO_ROOT_USER` et `MINIO_ROOT_PASSWORD` comme valeurs de repli. Les nouveaux fichiers `.env` doivent utiliser les noms `RUSTFS_*`.
- Conséquences : les clients S3 peuvent garder leur modèle d'accès, mais leurs endpoints/configurations devront viser le service `rustfs` depuis le réseau Compose. Le volume `minio_data` n'est pas renommé ni converti ; les objets qu'il contient ne sont pas copiés dans `rustfs_data` par cette modification.
- Limites : la configuration Compose vise le développement local et ne valide ni la migration des données existantes, ni les sauvegardes, ni une configuration de production. Ces points restent à traiter avant tout usage partagé ou production.
- Référence : [Installation RustFS en conteneur](https://docs.rustfs.com/en/installation/container), [variables d'identification](https://docs.rustfs.com/en/operations/credentials).
