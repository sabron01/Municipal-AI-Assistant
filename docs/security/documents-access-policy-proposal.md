# Proposition — contrôle d'accès du module Documents

- Statut : proposition de conception, non approuvée.
- Périmètre : accès aux métadonnées et contenus des documents; aucun rôle ni workflow municipal n'est créé.

## Recommandation

Utiliser `service_id` comme périmètre de visibilité initial : un document n'est visible qu'aux identités auxquelles le fournisseur d'identité/autorisation associe le service responsable. Aucun accès transversal ou administrateur n'est accordé par défaut. Lecture, téléversement, ajout de version, modification et suppression restent des décisions distinctes fournies par une source d'autorité; l'appartenance au service seule ne doit pas être interprétée comme permission d'écriture.

## Garde-fous proposés

1. Rejeter toute requête sans identité authentifiée et toute décision d'autorisation absente/indisponible.
2. Appliquer le contrôle pour chaque document, y compris avant le téléchargement; ne jamais exposer de clé objet RustFS.
3. Répondre de façon indistinguable pour une ressource inexistante ou non visible afin de limiter l'énumération.
4. Ne pas permettre lecture, téléchargement ou mutation d'un document `pending` ou supprimé logiquement par les routes ordinaires.
5. Journaliser les actions autorisées et refusées sans contenu, secret ni URL pré-signée.
6. Garder les routes désactivées tant que le fournisseur d'identité, l'appartenance au service, les permissions distinctes et les accès transversaux éventuels ne sont pas approuvés.

## Choix produit à valider

- La visibilité limitée au service responsable est-elle la règle retenue, ou certains documents doivent-ils être accessibles à toute la commune ?
- Quelle source établit l'identité et l'appartenance d'une personne à un service ?
- Quelles personnes peuvent déposer, créer une version, modifier les métadonnées, supprimer logiquement, restaurer ou administrer ? La restauration et l'administration ne sont pas incluses dans le contrat v1 actuel.
- Les accès transversaux, délégations et accès temporaires sont-ils permis ?
- Quels attributs doivent apparaître dans l'audit, et quelle est sa durée de conservation ?

## Conséquence immédiate

Cette proposition ne change pas `DocumentAccessPolicy`, ne configure aucun résolveur d'identité et n'active aucune route. Après validation des choix ci-dessus, l'adaptateur d'autorisation pourra être branché sans modifier le domaine Documents.
