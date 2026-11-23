# ADR-015 — Cycle de vie du registre Administration v1

- Date : 2026-11-23.
- Statut : accepté.
- Contexte : les décisions D2 de la spécification v1 (renommage, entrées obsolètes, déplacement d'un document, déplacement d'une catégorie) n'étaient pas tranchées. L'interface du registre livrée permet de créer et renommer les Directions, Services et Catégories, mais pas de les désactiver ni de les déplacer.

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-008 | Le renommage d'une Direction, d'un Service ou d'une Catégorie est rétroactif. Aucun historique du nom n'est conservé en v1. | Les documents référencent des UUID : ils affichent toujours le nom courant. Aucune migration ni table d'historique. |
| DOC-009 | Aucune désactivation, archivage ou suppression d'entrée du registre en v1. | Les entrées obsolètes restent proposées indéfiniment. Limite documentée ; un retrait nécessitera un nouvel ADR. |
| DOC-010 | Le déplacement d'un document vers un autre Service ou une autre Catégorie est autorisé. | `PATCH /documents/{id}` exige `document.metadata_update` sur le Service source **et** le Service cible ; l'action est auditée. |
| DOC-011 | Le déplacement d'une Catégorie sous un autre parent est différé après v1. | Aucune route ni interface de reparentage. |

## Détails et conséquences

- **Renommage** : l'unicité reste garantie par périmètre (nom normalisé unique par Direction pour les Services, par parent pour les Catégories). Un renommage échoue en `409` si le nom existe déjà. L'audit `administration.catalog_audit` conserve l'action et l'entité, pas les anciennes valeurs.
- **Entrées obsolètes** : elles restent visibles et sélectionnables. Les documents existants restent lisibles, téléchargeables et modifiables. Aucun mécanisme ne bloque un nouveau dépôt sur une entrée devenue obsolète.
- **Déplacement de document** : le contrôle d'accès est appliqué deux fois, avant validation des référentiels. Un acteur autorisé sur le service source mais pas sur le service cible reçoit un refus. Le déplacement ne crée pas de version de fichier et ne modifie pas l'historique.
- **Déplacement de catégorie** : les sous-catégories restent limitées à un niveau ; un reparentage changerait l'unicité et l'historique d'affichage, d'où le report.

## Risques acceptés

- Encombrement progressif des listes et risque de sélection d'une entrée obsolète pour un nouveau document.
- Un document peut être reclassé dans un autre service par un acteur disposant des permissions sur les deux services ; l'audit permet de tracer l'opération, sans conservation de l'ancien service dans l'historique des versions.

## Options rejetées

- **Désactivation logique en v1** : aurait exigé migration, état, routes, badges d'interface et règles sur les documents existants ; reportée.
- **Interdire le déplacement de document** : le comportement actuel est conservé, avec double autorisation et audit.
- **Historisation des noms** : coût de modèle et d'interface disproportionné pour v1 ; le renommage rétroactif est accepté.

## Suivi

Toute demande de retrait d'une entrée, d'historique des noms ou de reparentage de catégorie devra faire l'objet d'un nouvel ADR et d'une validation du propriétaire du produit.
