# ADR-013 — Référentiels d’organisation et de classification

- Date : 2026-11-22.
- Statut : accepté pour le registre technique v1; la source de vérité et le mode de constitution initiale sont décidés.

## Contexte

Le module Documents référence un `service_id` et un `category_id`, mais aucun registre Direction/Service/Catégorie n’existait dans le dépôt. Le propriétaire du produit a choisi de créer et maintenir ces référentiels dans l’application.

## Décisions

- Le contexte Administration est propriétaire des tables PostgreSQL des Directions, Services et Catégories.
- L’axe organisationnel est `Direction → Service`; chaque Service a exactement une Direction.
- L’axe de classification est indépendant : `Catégorie → Sous-catégorie`; une catégorie a zéro ou une catégorie parente, et le niveau Sous-catégorie ne peut pas être parent à son tour.
- Les identifiants sont des UUID stables. Documents et comptes valident les références par un port/adaptateur; aucune FK inter-contextes n’est ajoutée.
- Les entrées sont créées et renommées par l’administrateur central, seul rôle d’administration défini en v1. Toutes les opérations sont auditées.
- Le registre applicatif Administration en PostgreSQL est la source de vérité; aucune API ou liste externe n’est requise. L’administrateur central crée les Directions, Services, Catégories et Sous-catégories initiales via l’API d’administration.
- Les noms sont uniques sans distinction de casse à l’intérieur de leur Direction ou de leur parent de catégorie. Les noms initiaux ne sont pas semés automatiquement.
- L’API v1 propose lecture, création et renommage. Suppression, archivage, désactivation et déplacement d’une entrée sont différés afin d’éviter d’invalider des documents et permissions avant la décision de cycle de vie.

## Conséquences

- Les permissions ne peuvent être accordées que pour un Service existant.
- Les créations de document valident Service et Catégorie via le registre Administration.
- Les routes d’administration exigent une session active d’administrateur central et une validation CSRF pour les écritures.
- La migration crée les tables vides; les documents et permissions ne pourront référencer des entrées qu’après leur création par l’administrateur central.

## Questions reportées

- Quelle politique future d’archivage, de désactivation, de déplacement et de renommage historique appliquer ?
- Faut-il permettre à d’autres profils que l’administrateur central de gérer le catalogue ?
