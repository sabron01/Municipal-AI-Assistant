# Politique d'accès — module Documents

- Statut : décisions partiellement approuvées le 2026-11-22; règles encore ouvertes précisées ci-dessous.
- Périmètre : accès aux métadonnées et contenus des documents; aucun rôle ni workflow municipal n'est créé.

## Décision validée

Utiliser `service_id` comme périmètre de visibilité : un document n'est visible qu'aux identités autorisées du service responsable. La visibilité à l'échelle de toute la commune et les accès transversaux ne sont pas accordés par défaut. Cette décision ne confère à elle seule aucun droit de lecture ou d'écriture : les permissions d'action doivent venir d'une source d'autorité validée.

Les comptes sont gérés par l'application. L'administrateur central crée, désactive et peut réactiver un compte existant; le premier administrateur central est désigné au bootstrap par `INITIAL_CENTRAL_ADMIN_EMAIL`, paramètre retiré après initialisation. Un compte désactivé ne peut ni se connecter ni agir; ses permissions restent enregistrées et distinctes de son état. Les comptes suivants sont activés par un lien à usage unique envoyé à l'adresse professionnelle et valide pendant 7 jours. Cette adresse est aussi l'identifiant de connexion. La réinitialisation du mot de passe est déclenchée par l'administrateur central; le lien est envoyé à l'adresse professionnelle et valide pendant 7 jours. La MFA n'est pas obligatoire en v1. Pour le moment, l'administrateur central est l'unique autorité qui attribue, modifie et retire séparément les droits de lecture, dépôt d'un nouveau document, ajout de version, modification des métadonnées et suppression logique pour chaque service. Un compte peut recevoir des permissions dans plusieurs services, uniquement par attribution explicite de l'administrateur central pour chaque service. Administrer les comptes ou permissions ne donne pas implicitement accès aux documents.

## Garde-fous proposés

1. Rejeter toute requête sans identité authentifiée et toute décision d'autorisation absente/indisponible; aucun compte ne reçoit de privilège par défaut.
2. Appliquer le contrôle pour chaque document, y compris avant le téléchargement; ne jamais exposer de clé objet RustFS.
3. Répondre de façon indistinguable pour une ressource inexistante ou non visible afin de limiter l'énumération.
4. Ne pas permettre lecture, téléchargement ou mutation d'un document `pending` ou supprimé logiquement par les routes ordinaires.
5. Journaliser les actions autorisées et refusées sans contenu, secret ni URL pré-signée.
6. Garder les routes désactivées tant que l'authentification, le cycle de vie complet des comptes et l'autorité qui désigne les administrateurs centraux ne sont pas en place.

## Prérequis avant activation

- Choisir et configurer un fournisseur d'envoi de courriels professionnels.
- Implémenter le bootstrap du premier administrateur à partir de `INITIAL_CENTRAL_ADMIN_EMAIL`, puis retirer ce paramètre.
- Définir les protections techniques de mots de passe, sessions et limitation des tentatives avant activation.

## Questions reportées après v1

- Quel processus de désignation des responsables de service appliquer en pratique ?
- Quels attributs d'audit conserver et pendant combien de temps ?
- La restauration de document, les délégations et les accès temporaires restent hors périmètre v1; ils sont désactivés par défaut.

## Conséquence immédiate

Ces décisions ne changent pas encore `DocumentAccessPolicy`, ne créent pas le module de comptes et n'activent aucune route. Les choix reportés n'empêchent pas la conception v1. L'authentification reste fermée jusqu'à mise en place des prérequis techniques ci-dessus.
