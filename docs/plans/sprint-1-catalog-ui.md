# Proposition de Sprint 1 — Interface du registre Administration

- Statut : périmètre recommandé retenu pour la poursuite du projet; implémentation réalisée, couverte par des tests frontend sur l'accès, le chargement filtré par l'API, les catégories racines/sous-catégories et les erreurs de session/conflit; les corrections de la revue QA/Security (contrastes, déconnexion mobile, cache, garde d'accès unique, message d'indisponibilité) sont appliquées; revue indépendante finale à réaliser.
- Dépendances : contrat de l’API `/admin/catalog` existant; source de vérité confirmée dans ADR-013.
- Hors périmètre : aucun changement backend, aucune saisie d’une liste officielle prédéfinie, aucune interface de dépôt de documents.

## Objectif

Permettre à l’administrateur central de constituer et maintenir, depuis le frontend, le registre Direction → Service et Catégorie → Sous-catégorie. Le frontend consomme exclusivement l’API de l’application; il ne communique pas directement avec PostgreSQL ni RustFS.

## Critères d’acceptation proposés

1. L’administrateur central ouvre une session par `POST /api/v1/auth/login` (`email`, `password`) et la vérifie avec `GET /api/v1/auth/me`; les pages du registre ne sont pas accessibles sans session et un compte non administrateur reçoit un état d’accès refusé.
2. La session repose sur les cookies HTTP du backend; le frontend ne copie pas le jeton de session dans `localStorage` ou `sessionStorage`. Les requêtes d’écriture envoient le jeton CSRF du cookie dans `X-CSRF-Token` et transmettent les cookies de session.
3. L’écran Directions liste les Directions avec `GET /api/v1/admin/catalog/directions`, et permet d’en créer avec `POST` et de les renommer avec `PATCH /api/v1/admin/catalog/directions/{direction_id}` (`{ "name": "…" }`).
4. L’écran Services filtre par Direction avec `GET /api/v1/admin/catalog/services?direction_id=…`, affiche la Direction parente, et permet de créer un Service par `POST /api/v1/admin/catalog/services` (`direction_id`, `name`) et de le renommer par `PATCH /api/v1/admin/catalog/services/{service_id}` (`name`).
5. L’écran Catégories présente les racines avec `GET /api/v1/admin/catalog/categories?roots_only=true` et les sous-catégories avec `GET /api/v1/admin/catalog/categories?parent_id=…`. Il permet de créer une racine ou une sous-catégorie d’une racine (`POST /api/v1/admin/catalog/categories`, `parent_id` nul ou UUID et `name`) et de renommer une entrée (`PATCH /api/v1/admin/catalog/categories/{category_id}`, `name`).
6. Les formulaires refusent les noms vides ou de plus de 200 caractères. Les conflits `409`, erreurs de validation `422`, session expirée `401`, accès refusé `403` et dépendance indisponible `503` sont rendus de manière explicite et compréhensible.
7. Les états de chargement, listes vides, succès, échec et annulation sont visibles. Les opérations sont utilisables au clavier et les champs ont des libellés accessibles.
8. Après création ou renommage, les données affichées sont réconciliées avec la réponse API; un rechargement confirme leur persistance.
9. Aucun mécanisme de suppression, archivage, désactivation ou déplacement n’est ajouté : ces actions restent différées par ADR-013.

## Conditions d’exécution / de clôture

- Les migrations du backend sont à jour; l’administrateur central est initialisé et actif; l’authentification est activée pour l’environnement local.
- Les origines frontend/API et l’usage des cookies sont configurés sans affaiblir les attributs de sécurité des cookies.
- La revue QA/Security vérifie le contrôle du rôle, le CSRF, la gestion des sessions expirées, les messages d’erreur sans données sensibles et l’accessibilité des formulaires.
- Cette étape suit l’option recommandée après la demande de poursuivre le projet. Elle n’introduit aucune nouvelle règle métier; toute extension du périmètre demandera une validation dédiée.

## Points qui restent hors de cette proposition

- Les formats autorisés et la taille maximale des fichiers, nécessaires à l’interface de dépôt.
- La politique d’archivage, déplacement et renommage historique du registre.
- Les libellés officiels à saisir : aucun jeu de données métier n’est inventé ni chargé automatiquement.
