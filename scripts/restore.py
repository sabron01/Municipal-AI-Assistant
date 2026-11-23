"""Restauration d'une sauvegarde PostgreSQL + RustFS produite par backup.py.

Usage :
    python scripts/restore.py --source backups/<horodatage> [--database <base>] [--yes]

La restauration vérifie d'abord l'empreinte SHA-256 du dump et de chaque objet.
Elle refuse d'écraser la base applicative sans l'option `--yes`. Les objets sont
réécrits à l'identique dans le bucket indiqué par le manifeste.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from backup import host_endpoint, load_dotenv, required, safe_object_path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(manifest: dict, source: Path) -> None:
    dump = source / manifest["database"]["dump_file"]
    if not dump.is_file():
        raise SystemExit(f"Dump introuvable : {dump}")
    if sha256_file(dump) != manifest["database"]["sha256"]:
        raise SystemExit("L'empreinte du dump PostgreSQL ne correspond pas au manifeste.")
    for entry in manifest["object_storage"]["objects"]:
        path = safe_object_path(source / "objects", entry["key"])
        if not path.is_file():
            raise SystemExit(f"Objet manquant : {entry['key']}")
        if sha256_file(path) != entry["sha256"]:
            raise SystemExit(f"L'empreinte de l'objet {entry['key']} est invalide.")


def restore_database(manifest: dict, source: Path, database: str) -> None:
    container = os.environ.get("BACKUP_POSTGRES_CONTAINER", "maa-postgres")
    user = required("POSTGRES_USER")
    dump = source / manifest["database"]["dump_file"]
    command = [
        "docker", "exec", "-i", container, "pg_restore",
        "-U", user, "-d", database, "--clean", "--if-exists", "--no-owner",
    ]
    with dump.open("rb") as handle:
        result = subprocess.run(command, stdin=handle, stderr=subprocess.PIPE)
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise SystemExit(f"Échec de pg_restore : {message}")


def restore_objects(manifest: dict, source: Path) -> int:
    import boto3
    from botocore.config import Config

    storage = manifest["object_storage"]
    bucket = storage["bucket"]
    client = boto3.client(
        "s3",
        endpoint_url=host_endpoint(),
        aws_access_key_id=required("RUSTFS_ACCESS_KEY"),
        aws_secret_access_key=required("RUSTFS_SECRET_KEY"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )
    try:
        client.head_bucket(Bucket=bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=bucket)
    for entry in storage["objects"]:
        path = safe_object_path(source / "objects", entry["key"])
        client.upload_file(str(path), bucket, entry["key"])
    return len(storage["objects"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Restauration PostgreSQL + RustFS")
    parser.add_argument("--source", type=Path, required=True, help="Répertoire de sauvegarde")
    parser.add_argument("--database", help="Base cible (par défaut la base applicative)")
    parser.add_argument("--yes", action="store_true", help="Confirmer l'écrasement de la base applicative")
    args = parser.parse_args()

    load_dotenv()
    manifest_path = args.source / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Manifeste introuvable : {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify(manifest, args.source)

    database = args.database or required("POSTGRES_DB")
    if database == os.environ.get("POSTGRES_DB") and not args.yes:
        raise SystemExit("Restauration refusée : ajoutez --yes pour écraser la base applicative.")

    print(f"Restauration PostgreSQL dans {database}…")
    restore_database(manifest, args.source, database)
    print("Restauration des objets RustFS…")
    count = restore_objects(manifest, args.source)
    print(f"Restauration terminée : {count} objet(s) réécrit(s) dans {manifest['object_storage']['bucket']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
