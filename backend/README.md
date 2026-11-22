# Backend
API FastAPI et modules DDD du monolithe.

La spécification technique du module Documents v1 est définie dans [`docs/documents/specification-v1.md`](../docs/documents/specification-v1.md). Le module exécutable se trouve sous `src/municipal_assistant/documents/` : domaine, use cases, adaptateurs PostgreSQL/RustFS, schémas et routes FastAPI. La migration initiale est sous `alembic/versions/`.

## Démarrage local

Depuis ce dossier, installer le projet (`pip install -e '.[dev]'`), définir `DATABASE_URL`, `OBJECT_STORAGE_ENDPOINT`, les identifiants RustFS et le bucket, puis lancer `alembic upgrade head` et `uvicorn municipal_assistant.app:app`. L'URL ObjectStorage est indépendante des ports RustFS et vaut, depuis Compose, typiquement `http://rustfs:9000`.

Les routes Documents restent en échec fermé par défaut. Elles ne peuvent être activées qu'en appelant `configure_documents` avec `business_policy_approved=True`, un service monté sur PostgreSQL/RustFS, une liste MIME et une limite de taille validées, des adaptateurs de référence Service/Catégorie et un résolveur d'identité de confiance relié à une politique d'accès. Cette valeur est un garde de configuration explicite, pas une décision prise par le code. Aucune identité transmise dans un en-tête HTTP n'est considérée fiable. Les registres Service/Catégorie et le fournisseur d'identité ne sont pas présents dans le dépôt; l'implémentation les exige comme dépendances, sans inventer leur schéma ni leurs droits.

`DocumentService.reconcile_pending_uploads()` permet de reprendre de manière idempotente des réservations d'upload après vérification du checksum et de la taille côté stockage. Il doit être appelé par un worker interne après mise en place de la supervision; aucune route publique de purge physique n'existe.
