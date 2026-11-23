# ADR-017 — Suppression, restauration et rétention des Documents v1

- Date : 2026-11-24.
- Statut : accepté.
- Contexte : les décisions D4 de la spécification v1 (suppression réversible/définitive, rétention, purge, sauvegardes) n'étaient pas tranchées. L'implémentation initiale ne disposait que d'une suppression logique.

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-019 | Suppression logique (`soft_delete`) reste le comportement par défaut de `DELETE /documents/{id}`. | Le document devient invisible, les objets sont conservés; `404` sur les lectures. |
| DOC-020 | La restauration est possible tant que le document n'est pas purgé, par un acteur disposant de `document.restore`. | `POST /documents/{id}/restore` réactive le document et incrémente l'agrégat; refus `409` si le document n'est pas supprimé. |
| DOC-021 | La purge physique est manuelle et réservée aux acteurs disposant de `document.purge`. | `DELETE /documents/{id}/purge` supprime métadonnées, versions, audit et objets; le document doit être supprimé logiquement d'abord. |
| DOC-022 | La durée de rétention est portée par la catégorie (`retention_years`, en années, nullable). | `NULL` signifie conservation indéfinie; aucune purge automatique n'est mise en œuvre en v1. |
| DOC-023 | Aucune suppression de version individuelle en v1. | L'historique des versions reste immuable; seuls les documents entiers peuvent être purgés. |
| DOC-024 | La sauvegarde et sa rétention relèvent de l'exploitation. | Les scripts `scripts/backup.py` et `scripts/restore.py` restent manuels; aucune planification n'est embarquée. |

## Détails

- La purge supprime d'abord les objets du stockage (meilleur effort), puis les lignes `document_outbox`, `document_versions`, `document_audit` et `documents` dans une transaction.
- Un enregistrement d'audit `document.purged` est conservé avec `document_id = NULL` pour tracer l'opération sans référencer un document disparu.
- La restauration réinitialise `deleted_at` et `deleted_by` et incrémente `aggregate_version`.
- Les permissions `document.restore` et `document.purge` sont accordées par service; elles sont typiquement réservées aux administrateurs centraux.
- La rétention selon la catégorie est informative en v1 (pas de purge automatique); une future évolution pourra déclencher une purge à l'échéance.

## Options rejetées

- **Purge automatique à l'échéance** : reportée; exigerait un worker planifié et une validation métier des durées.
- **Suppression définitive immédiate** : contraire à la réversibilité souhaitée et à l'audit.
- **Rétention globale unique** : la décision valide une durée par catégorie.

## Conséquences

- Migration `20261122_07` : colonne `retention_years` sur `administration.categories`.
- Migration `20261122_08` : permissions `document.restore` et `document.purge` dans la contrainte `ck_permission_grant_permission`.
- Routes `POST /documents/{id}/restore` et `DELETE /documents/{id}/purge`.
- Interface d'administration : saisie et affichage de la rétention sur les catégories.
