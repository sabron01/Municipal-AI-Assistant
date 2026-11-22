# ADR-009 — Modèle technique du module Documents v1

- Date : 2026-11-22.
- Statut : accepté pour la spécification; implémentation conditionnée aux décisions ouvertes ci-dessous.
- Contexte : le dépôt ne contenait qu'une spécification v0 avec questions métier non résolues. Les décisions DOC-001 à DOC-004 ont été validées par le propriétaire du produit dans la conversation de conception référencée.

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-001 | Rattachement au service | Un document appartient à un seul service; sa direction est dérivée du référentiel du service. |
| DOC-002 | Classification simple | Une catégorie principale unique par document; sous-catégorie facultative choisissable comme catégorie principale. |
| DOC-003 | Historique préservé | Chaque changement d'octets produit une nouvelle version immuable; une version courante. |
| DOC-004 | Suppression logique | Tombstone du document; versions et objets restent conservés. |

- L'organisation est hybride : Direction → Service et Catégorie → Sous-catégorie sont deux axes distincts.
- PostgreSQL conserve les métadonnées; RustFS conserve les octets via une abstraction applicative indépendante `ObjectStorage`.
- RustFS API/console gardent leurs ports de service déterminés dans ADR-008. Le port HTTP de l'application ObjectStorage est un paramètre indépendant, à choisir dans le manifeste de configuration; il ne doit pas être implicitement lié au port RustFS 9000.
- La cohérence inter-systèmes suit une saga/outbox, objets immuables, versions visibles seulement après vérification du stockage. Pas de transaction distribuée.
- L'authentification applicative et la matrice de permissions sont définies dans [ADR-012](ADR-012-application-managed-accounts.md) et le périmètre de visibilité dans [ADR-011](ADR-011-documents-service-visibility.md). Leur activation opérationnelle reste conditionnée au bootstrap et au SMTP.

## Détails et conséquences

La spécification exécutable est [specification-v1.md](../../documents/specification-v1.md). Elle définit ports Protocol, cas d'utilisation, schémas, routes, tables, cohérence, sécurité et matrice de tests. Le registre Administration retenu ensuite est décrit dans [ADR-013](ADR-013-administration-catalogs.md).

ADR-008 est la décision active d'implémentation RustFS; ADR-003 MinIO est historique et remplacé. Cette décision ne valide ni migration de données MinIO, ni déploiement de production, ni politique de rétention physique.

## Questions à résoudre avant implémentation fonctionnelle exposée

Cycle de vie et données initiales du catalogue; formats et limites upload; champs obligatoires; suppression/purge/rétention; idempotence et comportement des conflits; confidentialité, sauvegardes, antivirus/quarantaine. Les choix de comptes et permissions sont consignés dans ADR-011/012; les points non bloquants y sont reportés après v1.

## Options considérées

- Objet versionné mutable côté stockage : rejeté, car rend l'historique dépendant de la configuration bucket; clés uniques par version rendent l'immuabilité explicite.
- Suppression physique au DELETE HTTP : rejetée, contraire à DOC-004.
- Transaction distribuée PostgreSQL/S3 : non disponible; remplacée par une saga rejouable et une réconciliation sans purge automatique.
