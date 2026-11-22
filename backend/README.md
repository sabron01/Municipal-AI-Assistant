# Backend
API FastAPI et modules DDD du monolithe.

La spécification technique du module Documents v1 est définie dans [`docs/documents/specification-v1.md`](../docs/documents/specification-v1.md). Les modules exécutables Documents et comptes se trouvent sous `src/municipal_assistant/`; les comptes et permissions ont leur migration dans `alembic/versions/`.

## Démarrage local

Depuis ce dossier, installer le projet (`pip install -e '.[dev]'`), définir `DATABASE_URL`, `OBJECT_STORAGE_ENDPOINT`, les identifiants RustFS et le bucket, puis lancer `alembic upgrade head` et `uvicorn municipal_assistant.app:app`. L'URL ObjectStorage est indépendante des ports RustFS et vaut, depuis Compose, typiquement `http://rustfs:9000`.

En local, Mailpit capture les courriels SMTP : son interface est disponible sur `http://localhost:8025` et son serveur SMTP sur `127.0.0.1:1025`. L'autorisation SMTP non chiffrée est limitée explicitement à une destination loopback sans identifiants (`SMTP_ALLOW_INSECURE_LOCAL=true`); ne pas reprendre ce réglage en production. `.env.example` conserve `AUTH_ENABLED=false` par défaut. Après démarrage de PostgreSQL, application des migrations et bootstrap du premier administrateur (`python -m municipal_assistant.accounts.bootstrap_admin`), on peut activer l'authentification locale avec `AUTH_ENABLED=true`; le bootstrap envoie son lien à Mailpit. Retirer `INITIAL_CENTRAL_ADMIN_EMAIL` après le bootstrap. En environnement partagé, remplacer Mailpit par un SMTP réel configuré en TLS. Le registre Administration des Directions, Services et Catégories est disponible via l'API documentée dans `/docs`; ses données initiales restent à fournir. Ses opérations de création/renommage sont réservées à l'administrateur central et auditées. Les routes Documents restent en échec fermé tant que la limite de taille, la liste MIME, RustFS et la configuration d'exposition ne sont pas validés. La politique par défaut `DatabaseDocumentAccessPolicy` exige un grant explicite par action et service.

`DocumentService.reconcile_pending_uploads()` permet de reprendre de manière idempotente des réservations d'upload après vérification du checksum et de la taille côté stockage. Il doit être appelé par un worker interne après mise en place de la supervision; aucune route publique de purge physique n'existe.
