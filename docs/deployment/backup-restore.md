# Sauvegarde et restauration

## Périmètre

La sauvegarde couvre les deux sources de données du projet :

- la base PostgreSQL (schémas `documents`, `accounts`, `administration`, table `public.alembic_version`) ;
- le bucket Documents de RustFS (objets binaires et leurs clés).

Le code et la configuration ne sont pas sauvegardés par ces scripts : ils sont versionnés dans Git et dans `.env` local.

## Prérequis

- Pile Docker Compose démarrée (`docker compose ps` : `maa-postgres` et `maa-rustfs` sains).
- Python disposant des dépendances du backend (`pip install -e "./backend[dev]"`), dont `boto3`.
- Fichier `.env` local renseigné (`POSTGRES_*`, `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `RUSTFS_BUCKET_DOCUMENTS`).
- Espace disque suffisant pour le dump et une copie complète des objets.

## Sauvegarde

```bash
python scripts/backup.py
# ou vers un répertoire explicite
python scripts/backup.py --destination backups/2026-11-23
```

Le répertoire produit est autonome :

| Élément | Contenu |
| --- | --- |
| `postgres.dump` | Archive `pg_dump` au format personnalisé (`-Fc`) |
| `objects/` | Copie des objets du bucket, arborescence identique aux clés S3 |
| `manifest.json` | Horodatage, taille et empreinte SHA-256 du dump et de chaque objet |

Aucun identifiant n'est écrit dans le manifeste. Les objets sont lus depuis l'hôte via `BACKUP_S3_ENDPOINT` (par défaut `http://127.0.0.1:9000`) ; `OBJECT_STORAGE_ENDPOINT` sert de repli si le nom d'hôte Compose `rustfs` n'est pas résolvable depuis l'hôte.

## Restauration

```bash
# Vers une base de vérification (sans risque pour l'application)
python scripts/restore.py --source backups/2026-11-23 --database maa_restore_check

# Vers la base applicative (écrasement confirmé)
python scripts/restore.py --source backups/2026-11-23 --yes
```

La restauration vérifie d'abord l'empreinte SHA-256 du dump et de chaque objet ; toute divergence interrompt l'opération. `pg_restore` s'exécute avec `--clean --if-exists --no-owner`, puis les objets sont réécrits dans le bucket du manifeste (le bucket est créé s'il n'existe pas). Sans `--yes`, l'écriture dans la base applicative est refusée.

## Points de vigilance

- Arrêter l'API pendant la sauvegarde : le dump PostgreSQL est cohérent, mais un document déposé entre le dump et la copie des objets produirait un objet sans ligne associée.
- Le script ne planifie rien : la fréquence et la rétention relèvent d'une décision d'exploitation.
- Les archives ne sont pas chiffrées par le script : les stocker sur un support chiffré et restreindre les accès.
- Restaurer sur une pile à l'arrêt, puis vérifier `alembic current` et les comptages avant de redémarrer l'API.

## Journal de validation

Vérification exécutée le 2026-11-23 sur la pile locale :

1. Objet témoin déposé dans le bucket, sauvegarde exécutée (1 objet, dump PostgreSQL).
2. Objet témoin supprimé du bucket, puis restauration vers la base `maa_restore_check`.
3. Résultat : révision Alembic `20261122_05`, tables `documents.documents`, `accounts.user_accounts` et `administration.directions` présentes, objet témoin restauré avec la même empreinte.
4. Nettoyage : base de vérification supprimée, objet témoin supprimé, répertoire de travail effacé.
