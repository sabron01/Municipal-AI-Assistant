# ADR-011 — Visibilité des documents par service

- Date : 2026-11-22.
- Statut : décision métier acceptée; mise en œuvre différée jusqu'au raccordement du cycle de vie des comptes et des permissions par action.
- Contexte : DOC-001 rattache chaque document à un seul service. La politique d'accès doit préciser le périmètre de visibilité sans inventer les rôles municipaux.

## Décision

La visibilité d'un document est limitée au service auquel il est rattaché (`service_id`). Une visibilité communale globale n'est pas accordée par défaut. Toute consultation de métadonnées ou de contenu doit être conditionnée à une identité authentifiée et à une autorisation portant sur le service responsable.

Cette décision ne donne automatiquement aucun droit d'action aux membres d'un service. En particulier, la lecture exige une permission explicite. Pour le moment, les droits de lecture, dépôt, création de version, modification des métadonnées et suppression logique sont attribués séparément par l'administrateur central, au niveau du service, selon [ADR-012](ADR-012-application-managed-accounts.md). L'administration des comptes ou des permissions n'accorde pas en soi le droit de consulter ou modifier les documents.

## Conséquences

- L'adaptateur `DocumentAccessPolicy` doit vérifier le droit d'action pour l'utilisateur et le `service_id` du document.
- La création doit vérifier le droit de dépôt pour le `service_id` demandé; les autres actions exigent leur propre permission explicite.
- Les routes restent non exposées tant que l'authentification des comptes et les permissions d'action ne sont pas branchées et validées.
- Les délégations, accès temporaires, détails d'audit et permissions de restauration restent hors décision.

## Questions ouvertes

- Un compte désactivé peut-il être rétabli ?
- Les délégations ou accès temporaires sont-ils nécessaires ?
- Quels événements d'accès sont journalisés et combien de temps ?

La politique et les garde-fous de conception associés sont suivis dans [documents-access-policy-proposal.md](../../security/documents-access-policy-proposal.md).
