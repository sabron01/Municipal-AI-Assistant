"""Sauvegarde de PostgreSQL et du stockage objet RustFS.

Usage :
    python scripts/backup.py [--destination backups/<horodatage>]

La sauvegarde produit un répertoire autonome :
    postgres.dump   archive pg_dump au format personnalisé
    objects/        copie des objets du bucket Documents
    manifest.json   empreintes SHA-256, tailles et métadonnées

Les identifiants ne sont jamais écrits dans le manifeste. Les variables sont
lues dans l'environnement puis, si nécessaire, dans le fichier `.env` local.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Variable d'environnement manquante : {name}")
    return value


def host_endpoint() -> str:
    endpoint = os.environ.get("BACKUP_S3_ENDPOINT") or os.environ.get("OBJECT_STORAGE_ENDPOINT") or "http://127.0.0.1:9000"
    endpoint = endpoint.replace("://rustfs:", "://127.0.0.1:")
    port = os.environ.get("RUSTFS_API_PORT")
    if port and endpoint.rstrip("/").endswith(":9000"):
        endpoint = endpoint.rstrip("/")[: -len(":9000")] + f":{port}"
    return endpoint.rstrip("/")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_object_path(root: Path, key: str) -> Path:
    parts = [part for part in key.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise SystemExit(f"Clé d'objet refusée : {key!r}")
    return root.joinpath(*parts)


def dump_database(destination: Path) -> dict[str, object]:
    container = os.environ.get("BACKUP_POSTGRES_CONTAINER", "maa-postgres")
    database = required("POSTGRES_DB")
    user = required("POSTGRES_USER")
    dump_path = destination / "postgres.dump"
    command = ["docker", "exec", container, "pg_dump", "-U", user, "-d", database, "-Fc"]
    with dump_path.open("wb") as handle:
        result = subprocess.run(command, stdout=handle, stderr=subprocess.PIPE)
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip()
        raise SystemExit(f"Échec de pg_dump : {message}")
    return {
        "database": database,
        "dump_file": dump_path.name,
        "bytes": dump_path.stat().st_size,
        "sha256": sha256_file(dump_path),
    }


def copy_objects(destination: Path) -> dict[str, object]:
    import boto3
    from botocore.config import Config

    endpoint = host_endpoint()
    bucket = os.environ.get("RUSTFS_BUCKET_DOCUMENTS") or os.environ.get("OBJECT_STORAGE_BUCKET") or "documents"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=required("RUSTFS_ACCESS_KEY"),
        aws_secret_access_key=required("RUSTFS_SECRET_KEY"),
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )
    objects_root = destination / "objects"
    objects_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Contents", []):
            key = item["Key"]
            target = safe_object_path(objects_root, key)
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))
            entries.append({
                "key": key,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
            })
    return {"endpoint": endpoint, "bucket": bucket, "objects": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description="Sauvegarde PostgreSQL + RustFS")
    parser.add_argument("--destination", type=Path, help="Répertoire de destination (créé si absent)")
    args = parser.parse_args()

    load_dotenv()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = args.destination or (PROJECT_ROOT / "backups" / stamp)
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit(f"Le répertoire de destination n'est pas vide : {destination}")
    destination.mkdir(parents=True, exist_ok=True)

    print(f"Sauvegarde PostgreSQL vers {destination / 'postgres.dump'}…")
    database = dump_database(destination)
    print(f"Copie des objets RustFS depuis {host_endpoint()}…")
    storage = copy_objects(destination)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "database": database,
        "object_storage": storage,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Sauvegarde terminée : {manifest_path}")
    print(f"Objets sauvegardés : {len(storage['objects'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
