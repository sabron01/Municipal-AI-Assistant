# Module Documents — spécification technique exécutable v1

- Statut : contrat de référence et implémentation backend Documents, comptes/permissions et registre Administration disponibles sur `feat/documents-v1`; migrations vérifiées sur environnement local isolé, aucun déploiement effectué. La politique d'upload (formats, taille, PDF chiffrés) est validée par [ADR-014](../architecture/adr/ADR-014-documents-upload-policy.md); les autres décisions métier et la configuration d'exposition restent à fournir.
- Date : 2026-11-22.
- Portée : contrat métier/technique et suivi des validations locales; les migrations ont été appliquées à une base locale et à une base temporaire de test, sans déploiement partagé.
- Décisions métier de référence : `DOC-001` à `DOC-004` dans [ADR-009](../architecture/adr/ADR-009-documents-module.md).

## 1. Contraintes validées

- Organisation documentaire hybride : organisation administrative Direction → Service et taxonomie Catégorie → Sous-catégorie, indépendantes.
- Chaque document référence exactement un service responsable et une catégorie principale. La catégorie principale peut être une sous-catégorie.
- Toutes les versions sont préservées et immuables ; une seule version est courante par document.
- La suppression est logique au niveau du document. Elle ne supprime pas les objets ni les versions.
- PostgreSQL contient les métadonnées ; RustFS contient les octets. La couche applicative dépend du port `ObjectStorage`, jamais du SDK S3.
- Authentification par comptes applicatifs, visibilité limitée au service et permissions d'action explicites définies dans [ADR-011](../architecture/adr/ADR-011-documents-service-visibility.md) et [ADR-012](../architecture/adr/ADR-012-application-managed-accounts.md). L'accès est refusé par défaut; les routes restent fermées tant que le bootstrap, SMTP et la configuration d'exposition ne sont pas opérationnels.

## 2. Arborescence mise en œuvre

```text
backend/src/municipal_assistant/documents/
  domain/{entities.py,value_objects.py,ports.py,errors.py}
  application/{dto.py,use_cases.py}
  infrastructure/{sqlalchemy_models.py,postgres_repositories.py,rustfs_storage.py}
  presentation/{schemas.py,router.py}
backend/alembic/versions/<revision>_documents_v1.py
backend/tests/{unit/documents,integration/documents}/
backend/src/municipal_assistant/accounts/{models.py,service.py,router.py,security.py,email.py}
backend/alembic/versions/<revision>_application_accounts.py
backend/src/municipal_assistant/administration/{domain,application,infrastructure,presentation}/
backend/alembic/versions/<revision>_administration_catalogs.py
```

Le domaine importe seulement la bibliothèque standard. L’application importe le domaine et ses ports. Infrastructure et présentation implémentent/adaptent ces contrats. Les dépendances et leurs bornes de compatibilité sont déclarées dans `backend/pyproject.toml`.

## 3. Domaine : Value Objects et entités

Types implémentés : `DocumentId`, `VersionId`, `ServiceId`, `CategoryId` (UUID), `Sha256` (64 caractères hexadécimaux normalisés), `ObjectKey` (clé opaque relative, jamais un chemin local), nom de fichier assaini, MIME détecté, taille strictement positive, référence optionnelle, acteur applicatif et horodatages timezone-aware. Constructions invalides lèvent `ValueError` ou une erreur de domaine dédiée.

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

@dataclass(frozen=True, slots=True)
class DocumentId: value: UUID
@dataclass(frozen=True, slots=True)
class VersionId: value: UUID
@dataclass(frozen=True, slots=True)
class ServiceId: value: UUID
@dataclass(frozen=True, slots=True)
class CategoryId: value: UUID
@dataclass(frozen=True, slots=True)
class Sha256: value: str  # valide hex 64 caractères
@dataclass(frozen=True, slots=True)
class ObjectKey: value: str  # clé opaque générée côté serveur

class DocumentStatus(StrEnum): ACTIVE = "active"; DELETED = "deleted"

@dataclass(frozen=True, slots=True)
class DocumentVersion:
    id: VersionId; document_id: DocumentId; sequence: int
    object_key: ObjectKey; sha256: Sha256; size_bytes: int; detected_mime_type: str
    original_filename: str; created_at: datetime; created_by: UUID | None

@dataclass(slots=True)
class Document:
    id: DocumentId; title: str; service_id: ServiceId; category_id: CategoryId
    current_version_id: VersionId; status: DocumentStatus; created_at: datetime
    created_by: UUID | None; updated_at: datetime; deleted_at: datetime | None = None
    deleted_by: UUID | None = None; description: str | None = None
    reference_number: str | None = None; aggregate_version: int = 1

    def add_version(self, version: DocumentVersion) -> None: ...
    def soft_delete(self, at: datetime, actor_id: UUID | None) -> None: ...
    def update_metadata(self, *, title: str, description: str | None,
                        reference_number: str | None, service_id: ServiceId,
                        category_id: CategoryId, expected_version: int) -> None: ...
```

Les ellipses ci-dessus désignent les obligations de comportement, pas une implémentation dans cet extrait. Invariants : séquence positive et unique par document, version courante appartenant au document, horodatages UTC, agrégat supprimé non téléchargeable et non modifiable, version jamais écrasée, suppression répétée idempotente. Toute modification des octets crée une nouvelle version ; les changements de titre/service/catégorie/description/référence ne créent pas de version de fichier. Service et catégorie sont validés par des ports vers les registres détenus par le contexte Administration; aucune FK inter-contextes n'est ajoutée.

## 4. Ports Python (Protocol)

```python
from typing import BinaryIO, Protocol
from collections.abc import Sequence

class DocumentRepository(Protocol):
    def get(self, document_id: DocumentId, *, include_deleted: bool = False) -> Document | None: ...
    def save(self, document: Document, *, expected_aggregate_version: int | None) -> None: ...
    def list(self, query: "DocumentQuery") -> "Page[DocumentSummary]": ...
    def add_version(self, version: DocumentVersion) -> None: ...
    def versions(self, document_id: DocumentId) -> Sequence[DocumentVersion]: ...

class ObjectStorage(Protocol):
    def put(self, *, key: ObjectKey, body: BinaryIO, content_length: int,
            content_type: str, checksum_sha256: Sha256) -> "StoredObjectReceipt": ...
    def open(self, key: ObjectKey) -> "ReadableObject": ...
    def head(self, key: ObjectKey) -> "StoredObjectMetadata | None": ...
    def delete(self, key: ObjectKey) -> None: ...  # réservé au worker de purge ultérieur

class ServiceDirectory(Protocol):
    def exists(self, service_id: ServiceId) -> bool: ...
class CategoryDirectory(Protocol):
    def exists(self, category_id: CategoryId) -> bool: ...
class UnitOfWork(Protocol):
    documents: DocumentRepository
    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> None: ...
    def commit(self) -> None: ...
class UploadStaging(Protocol):
    def stage(self, body: BinaryIO, *, max_bytes: int) -> "StagedUpload": ...
    # implémentation temporaire locale, bornée, nettoyée même sur exception
```

`ReadableObject` expose un flux contextuel, `StoredObjectReceipt` retourne clé, taille et checksum vérifiés. Le port de stockage ne connaît ni RustFS ni port réseau ; l’adaptateur configure endpoint, credentials, bucket, TLS et région hors du domaine. Bucket privé, clé aléatoire (`documents/{document_uuid}/{version_uuid}`), opérations S3 conditionnelles si disponibles. Ne jamais faire confiance au checksum déclaré par le client.

## 5. Use Cases

Contrats applicatifs (entrée DTO validée, sortie DTO ou erreur typée) :

1. `CreateDocument`: vérifier service/catégorie actifs via répertoires, valider fichier (format autorisé configuré, taille plafonnée, signature réelle), calculer SHA-256, créer document + version 1.
2. `AddDocumentVersion`: document actif, mêmes contrôles, attribuer `max(sequence)+1` sous verrou/version optimiste, stocker nouvel objet et pointer `current_version_id`.
3. `GetDocument` / `ListDocuments`: fournir métadonnées seulement. Les filtres disponibles incluent service, catégorie, état et pagination curseur; autorisation obligatoire en amont et réappliquée avant restitution.
4. `DownloadDocument`: vérifier accès avant `ObjectStorage.open`, sélectionner explicitement version ou version courante, journaliser sans contenu.
5. `UpdateDocumentMetadata`: appliquer règles de concurrence; aucune modification du fichier.
6. `SoftDeleteDocument`: renseigner `deleted_at/by`; préserver toutes les versions et objets.
7. `ListDocumentVersions`: historique immuable, pas de suppression ni restauration de version prévue en v1.

Les use cases acceptent `ActorId` et un `DocumentAccessPolicy` abstrait. Tant que l’identité et la matrice d’accès ne sont pas validées, le point d’entrée HTTP est désactivé ou renvoie 503; un mode permissif n’est pas acceptable. La définition de ce port et de ses décisions est un prérequis métier/sécurité avant implémentation exposée.

## 6. Schémas Pydantic (contrat indicatif)

```python
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=300)
    service_id: UUID
    category_id: UUID
    description: str | None = Field(default=None, max_length=5000)
    reference_number: str | None = Field(default=None, max_length=200)

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; title: str; service_id: UUID; category_id: UUID
    current_version_id: UUID; status: str; created_at: datetime

class VersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID; sequence: int; original_filename: str
    detected_mime_type: str; size_bytes: int; sha256: str; created_at: datetime
```

Les imports de types/alias doivent être distribués proprement lors de l’implémentation ; `Field` expose les plafonds seulement, pas les règles de fichier. Les réponses ne divulguent jamais `object_key`, identifiants d’infrastructure ou credentials. Multipart : fichier unique `file` et champs du DTO ; champs inconnus rejetés. Réponses d’erreur JSON `application/problem+json` avec `type/title/status/detail/instance` et `request_id`, sans trace interne.

## 7. Contrats HTTP v1 (préfixe `/api/v1`)

| Méthode / route | Contrat |
|---|---|
| `POST /documents` | multipart; crée document et version 1; `201`, `Location`, DTO |
| `GET /documents` | curseur opaque, limite bornée, filtres service/catégorie; `200` |
| `GET /documents/{id}` | détail; `200`, `404` |
| `PATCH /documents/{id}` | champs de métadonnées autorisés uniquement, `If-Match` requis; `200`, `412` conflit |
| `POST /documents/{id}/versions` | multipart, `If-Match`; crée version; `201` |
| `GET /documents/{id}/versions` | liste ordonnée; `200` |
| `GET /documents/{id}/content?version_id=` | flux, version courante si paramètre absent; Content-Disposition attachment |
| `DELETE /documents/{id}` | tombstone logique, `204`; jamais d’effacement S3 |

Erreurs : `400` entrée invalide, `404` ressource absente ou non visible (ne pas permettre d’énumération), `409` contrainte métier/conflit séquence, `412` ETag périmé, `413` trop volumineux, `415` format refusé, `422` DTO invalide, `503` stockage/dépendance indisponible. Les autorisations ne sont pas codées comme rôles dans cette spécification : toute route doit être protégée par la politique validée avant activation. Streaming sans mise en mémoire complète, en-têtes `X-Content-Type-Options: nosniff`, `Cache-Control: private, no-store`, nom de téléchargement échappé; ne jamais servir en inline.

## 8. PostgreSQL / SQLAlchemy / Alembic

Tables dédiées `documents.documents`, `documents.document_versions`, `documents.document_outbox` et `documents.document_audit`; UUID PK, `timestamptz`, `text/varchar` bornés, `bigint` taille, checksum `char(64)`, clé objet unique. Les statuts techniques sont `pending|available|failed` pour version, `pending|active|deleted` pour document; seul `active` est visible. L'outbox garde l'état de reprise et la version d'agrégat attendue. L'audit conserve actor, action, document/version et résultat, sans contenu fichier. Index : `(service_id, created_at DESC, id)`, `(category_id, created_at DESC, id)`, `(document_id, sequence DESC)`, index partiel documents actifs, et unicité partielle `(document_id)` quand `state='pending'` pour sérialiser les uploads par document. Contraintes : `size_bytes > 0`, `sequence > 0`, status enum/check, `UNIQUE(document_id, sequence)`, `UNIQUE(object_key)`, FKs versions→documents, FK composite document `(id,current_version_id)` vers versions `(document_id,id)` (contrainte différée ou mise à jour dans transaction). Le rattachement service/catégorie utilise UUID; FKs aux tables de référentiel seulement après décision de propriété/schéma.

`DocumentRow` et `DocumentVersionRow` SQLAlchemy 2.x ne traversent pas vers le domaine. Mapping explicite. Alembic : une migration réversible crée schema/tables/indexes/checks; pas de données initiales de catégories/services ni d’extension non justifiée. Index de recherche texte/RAG hors périmètre. `aggregate_version` est compteur optimiste (`UPDATE ... WHERE aggregate_version=:expected`), le conflit renvoie 412.

## 9. Cohérence PostgreSQL / RustFS

Les transactions distribuées sont impossibles. Sémantique retenue : PostgreSQL est autorité des métadonnées; chaque objet est immuable et adressé par une clé unique.

**Écriture** : prévalider et mettre en staging borné; dans transaction DB réserver document/version en état interne `pending` (non visible) + entrée outbox; publier objet RustFS; vérifier HEAD taille/checksum; transaction DB passer version `available`, document courant, événement outbox complété. Échec après upload : garder la réservation rejouable; compensateur asynchrone peut supprimer uniquement l’objet non référencé après délai de grâce et vérification DB. Échec avant upload : réservation échoue/réessayable. Une seule réservation `pending` est permise par document. Le dépôt PostgreSQL vérifie de nouveau la version d'agrégat sous verrou au moment de réserver; une tentative concurrente est refusée avec un conflit préconditionnel, et un index partiel protège aussi la contrainte en base.

**Lecture** : n’exposer que versions `available`; panne RustFS → 503. **Suppression logique** : tombstone DB seulement, aucune suppression objet. Une éventuelle purge physique nécessite approbation de rétention, job audité, délai de grâce, et décision distincte. Tâche de réconciliation périodique compare objets/références, sans effacer automatiquement en v1. Outbox sert à l’audit et reprises; aucune indexation RAG n’est déclenchée en v1. Backups PostgreSQL et RustFS doivent être cohérents et testés avant usage partagé.

## 10. Sécurité et confidentialité

- Pas d’activation publique avant identité, autorisation par ressource/service, politique d’administration et audit définis.
- Limite d’upload configurable et rejet streaming dès dépassement; liste de formats autorisés à faire valider, détection MIME par signature, extension seulement informative; quarantaine/antivirus requis avant disponibilité si le service de scan est adopté.
- Clés objet générées, bucket privé, droits IAM minimaux, chiffrement/TLS, secrets seulement via environnement/gestionnaire de secrets.
- Protection CSRF si session cookie; CORS limité; rate limit, timeouts, quotas à définir; validation de nom, path traversal neutralisé; téléchargement en attachment avec nom sûr.
- Aucun document, extrait, token, clé, ou URL pré-signée dans logs. Audit structuré actor opaque, action, document/version, date UTC, request ID et résultat; durée d’audit à fixer.
- Menaces à traiter : usurpation ID, fuite inter-service, malware, zip bomb, MIME trompeur, concurrence version, objets orphelins, SSRF via endpoint S3 configurable, rejeu upload.

## 11. Plan de tests

**Unitaires** : invariants entités/VO, transitions version/suppression, permissions refusées par défaut, validation de taille/type/checksum, idempotence, conflit optimiste, mapping d’erreurs.

**Intégration PostgreSQL** : contraintes uniques/FK/check, migrations up/down sur PostgreSQL réel, réservations concurrentes, tombstone invisible et historique préservé. **Contrat ObjectStorage** : même suite pour adaptateur faux/local et RustFS de test : put/head/open/checksum, objet absent, erreur/transitoire, flux, nettoyage d’objet non référencé. **API** : schémas, multipart limites, routes protégées, 404 anti-énumération, `If-Match`, streaming, Problem Details. **Sécurité** : path traversal, MIME spoofing, taille dépassée, nom actif, mauvais service, injection de filtres, credentials absents, logs sans données sensibles. Les tests unitaires couvrent domaine, validation d'upload, accès fail-closed, plafonnement des requêtes, registre Administration et cas d'utilisation dépôt/version. Dernière suite complète sans dépendances de test externes : 25 réussis, 4 tests PostgreSQL/RustFS ignorés faute de variables dédiées; un avertissement de dépréciation Starlette/httpx subsiste. Les 4 tests réels de `tests/integration/documents/test_postgres_rustfs.py` ont été exécutés séparément avec succès sur une base PostgreSQL temporaire migrée et RustFS local : parcours HTTP avec connexion, permissions et CSRF; création, liste, mise à jour des métadonnées, versions, téléchargements et suppression logique; rejet des champs multipart inconnus et de l'accès/création sans grant de service; refus d'If-Match périmé; réservation en attente et deux dépôts concurrents avec un seul gagnant. Un aller-retour Alembic complet (`downgrade base`, `upgrade head`) et `alembic check` ont aussi réussi; la base temporaire, vidée après les tests, a été supprimée. La base locale est à `20261122_05`. Les autres combinaisons d'erreurs HTTP et cas de sécurité listés ci-dessus restent à compléter.

## 12. Hypothèses et décisions métier ouvertes (bloquantes avant code exposé)

1. ~~Cycle de vie des entrées du registre : archivage/désactivation, déplacement et effet historique d'un renommage.~~ Résolu par [ADR-015](../architecture/adr/ADR-015-catalog-lifecycle.md) : renommage rétroactif accepté, aucune désactivation/archivage/suppression en v1, déplacement de document autorisé avec permission sur le Service source et le Service cible, reparentage de catégorie différé. Le registre PostgreSQL de l'application est la source de vérité; l'administrateur central crée les entrées initiales via l'API d'administration.
2. ~~Formats exacts, taille maximale, scan/quarantaine, documents protégés/chiffrés, règle MIME.~~ Résolu par [ADR-014](../architecture/adr/ADR-014-documents-upload-policy.md) : PDF, DOCX, XLSX, PPTX, PNG et JPEG ; 25 Mo ; aucun scan antivirus en v1 ; PDF chiffrés refusés. Les routes restent fermées tant que la configuration correspondante n'est pas complète et que `DOCUMENT_POLICY_APPROVED` n'est pas passé à `true`.
3. Champs métier supplémentaires, unicité/format des références, convention de titre et langues.
4. Suppression réversible ou définitive, rétention légale, purge physique et durée de conservation des sauvegardes/audits.
5. Exigences de confidentialité/données personnelles, localisation, chiffrement et procédures de sauvegarde/restauration.

Les comptes applicatifs, la visibilité par service, les permissions explicites par action, l'administrateur central et la politique d'accès fail-closed sont définis dans ADR-011/012 et implémentés. Délégations et accès temporaires sont différés après v1.

Les valeurs techniques proposées (300 caractères titre, 5 000 description, 200 référence) sont des bornes de schéma initiales à confirmer, et non des règles métier validées. Les endpoints sont présents mais échouent fermés par défaut; l'activation technique est câblée par configuration (`DOCUMENT_MAX_UPLOAD_BYTES`, `DOCUMENT_ALLOWED_MEDIA_TYPES`, `DOCUMENT_POLICY_APPROVED`) et exige toujours des adaptateurs d'identité et de registre validés, une liste MIME et une limite d'upload explicites, puis un gate QA/Security. Aucune valeur métier n'est fournie par défaut.
