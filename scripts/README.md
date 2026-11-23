# Scripts

Répertoire réservé aux scripts reproductibles du projet.

- `backup.py` : sauvegarde PostgreSQL (`pg_dump`) et des objets RustFS, avec manifeste SHA-256. Voir `docs/deployment/backup-restore.md`.
- `restore.py` : restauration vérifiée d'une sauvegarde, vers une base de vérification ou la base applicative (`--yes`).
