# Modèle de domaine — état v1 du module Documents

Le modèle métier du module Documents est détaillé dans [sa spécification technique v1](../documents/specification-v1.md) et [ADR-009](adr/ADR-009-documents-module.md).

## Concepts

- `Direction` → plusieurs `Service`; le document référence un service unique, jamais la direction directement.
- Taxonomie indépendante `Category` → `Subcategory`; le document référence une catégorie principale unique, qui peut être une sous-catégorie.
- `Document` est l'identité logique, les métadonnées, le service, la catégorie et l'état actif/supprimé logiquement.
- `DocumentVersion` est un instantané immuable des octets, une clé d'objet, un checksum et des métadonnées de dépôt. Une version courante est désignée.
- `ObjectStorage` est un port applicatif indépendant de RustFS/S3. PostgreSQL persiste les métadonnées et RustFS les octets.

## Invariants confirmés

1. Exactement un service et une catégorie principale par document.
2. Toutes les versions sont conservées; changement d'octets = nouvelle version.
3. Suppression logique du document; aucune suppression implicite d'objet.
4. Le changement de service/catégorie/titre ne modifie pas le fichier ni son historique.

Les droits d'accès, la rétention, les référentiels, les formats acceptés et les champs métier restent à valider; voir les questions ouvertes dans la spécification.
