# Backend
API FastAPI et modules DDD du monolithe.

La spécification technique du module Documents v1 est définie dans [`docs/documents/specification-v1.md`](../docs/documents/specification-v1.md). Les modules exécutables Documents et comptes se trouvent sous `src/municipal_assistant/`; les comptes et permissions ont leur migration dans `alembic/versions/`.

## Démarrage local

Depuis ce dossier, installer le projet (`pip install -e '.[dev]'`), définir `DATABASE_URL`, `OBJECT_STORAGE_ENDPOINT`, les identifiants RustFS et le bucket, puis lancer `alembic upgrade head` et `uvicorn municipal_assistant.app:app`. L'URL ObjectStorage est indépendante des ports RustFS et vaut, depuis Compose, typiquement `http://rustfs:9000`.

En local, Mailpit capture les courriels SMTP : son interface est disponible sur `http://localhost:8025` et son serveur SMTP sur `127.0.0.1:1025`. L'autorisation SMTP non chiffrée est limitée explicitement à une destination loopback sans identifiants (`SMTP_ALLOW_INSECURE_LOCAL=true`); ne pas reprendre ce réglage en production. Les routes d'authentification et de comptes restent désactivées avec `AUTH_ENABLED=false` jusqu'au bootstrap du premier administrateur et à la configuration d'un SMTP réel. Le bootstrap se lance avec `python -m municipal_assistant.accounts.bootstrap_admin`; après son succès, retirer `INITIAL_CENTRAL_ADMIN_EMAIL` de l'environnement. Les routes Documents restent également en échec fermé; `configure_documents` exige un service PostgreSQL/RustFS, une liste MIME et une limite de taille validées, les registres Service/Catégorie et un résolveur de session fiable. La politique par défaut `DatabaseDocumentAccessPolicy` exige un grant explicite par action et service. Les registres Service/Catégorie ne sont pas présents dans le dépôt; ils restent des dépendances sans schéma inventé.

`DocumentService.reconcile_pending_uploads()` permet de reprendre de manière idempotente des réservations d'upload après vérification du checksum et de la taille côté stockage. Il doit être appelé par un worker interne après mise en place de la supervision; aucune route publique de purge physique n'existe.
