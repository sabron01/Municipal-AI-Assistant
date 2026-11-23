# ADR-018 — Confidentialité et données personnelles Documents v1

- Date : 2026-11-24.
- Statut : accepté.
- Contexte : les décisions D5 de la spécification v1 (confidentialité, données personnelles, localisation, chiffrement, sauvegarde) n'étaient pas tranchées. Le module dispose déjà d'un champ `confidentiality_level` stocké comme texte libre (ADR-016) et d'une rétention par catégorie (ADR-017).

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-025 | Taxonomie de confidentialité en quatre niveaux : `public`, `interne`, `confidentiel`, `secret`. | Le champ `confidentiality_level` reste libre en v1 (pas de contrainte CHECK) mais les valeurs attendues sont ces quatre niveaux; une contrainte pourra être ajoutée sans migration de données incompatibles. |
| DOC-026 | Les données résident sur des serveurs locaux à Tataouine. | PostgreSQL et RustFS sont hébergés sur place; aucune sortie vers un cloud externe n'est autorisée sans nouvel ADR. |
| DOC-027 | Chiffrement au repos pour la base et les objets. | Volumes chiffrés pour PostgreSQL et RustFS; le chiffrement des flux (TLS) est obligatoire entre composants et vers les clients. |
| DOC-028 | Les demandes de données personnelles sont traitées manuellement par l'administration. | Aucun endpoint automatisé d'accès/rectification/effacement en v1; les demandes sont gérées hors application, avec audit manuel. |
| DOC-029 | La durée de conservation des sauvegardes et des audits est alignée sur la catégorie. | Les sauvegardes et les traces d'audit suivent la rétention du document; en cas de purge, les sauvegardes antérieures à la purge peuvent encore contenir le document jusqu'à leur propre expiration. |
| DOC-030 | Le niveau de confidentialité est informatif en v1. | Aucun contrôle d'accès différencié par niveau n'est mis en œuvre; les permissions restent par service et par action. |

## Détails

- Les quatre niveaux : `public` (diffusable), `interne` (usage administratif), `confidentiel` (accès restreint), `secret` (données personnelles sensibles ou actes réservés).
- La localisation impose que les sauvegardes soient stockées sur un support local ou national agréé, chiffré, et ne transitent pas par un prestataire étranger.
- Le chiffrement au repos est une exigence d'infrastructure; l'application ne gère pas de clés cryptographiques.
- Les demandes manuelles sont tracées dans le registre d'audit administratif, hors du module Documents.
- Les sauvegardes ne sont pas purgées automatiquement; leur rétention relève de l'exploitation (voir `docs/deployment/backup-restore.md`).

## Options rejetées

- **Taxonomie à trois niveaux** : le niveau `secret` est conservé pour les données personnelles sensibles.
- **Endpoints automatisés de droits** : reportés; la charge et la validation métier dépassent le périmètre v1.
- **Contrôle d'accès par niveau de confidentialité** : reporté; les permissions par service restent la seule règle.

## Conséquences

- Aucune migration ni évolution de code; le champ `confidentiality_level` reste libre.
- La documentation de déploiement doit mentionner le chiffrement au repos et la localisation.
- Toute évolution (endpoint de droits, contrôle par niveau, taxonomie contraignante) nécessite un nouvel ADR.
