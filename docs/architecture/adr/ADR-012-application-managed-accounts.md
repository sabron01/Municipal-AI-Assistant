# ADR-012 — Comptes applicatifs et permissions de service

- Date : 2026-11-22.
- Statut : décisions v1 acceptées; les choix secondaires ci-dessous sont reportés après v1.
- Contexte : les documents sont visibles dans le périmètre du service responsable (ADR-011). Aucun fournisseur externe d'identité n'est retenu.

## Décisions

- Les comptes utilisateurs sont gérés par l'application.
- Un administrateur central crée et désactive les comptes, et désigne ou révoque les responsables de service.
- Un administrateur central peut réactiver un compte existant.
- Un administrateur central existant peut désigner ou révoquer d'autres administrateurs centraux.
- Le premier administrateur central est désigné au bootstrap par `INITIAL_CENTRAL_ADMIN_EMAIL`, fourni dans l'environnement local; ce paramètre doit être retiré après l'initialisation.
- L'utilisateur active son compte au moyen d'un lien à usage unique envoyé à son adresse professionnelle après création du compte par l'administrateur central; le lien expire après 7 jours.
- L'adresse professionnelle est l'identifiant de connexion du compte.
- La réinitialisation du mot de passe est déclenchée par l'administrateur central; le lien de réinitialisation est envoyé à l'adresse professionnelle de l'utilisateur et expire après 7 jours.
- L'authentification multifacteur n'est pas obligatoire dans la première version.
- Pour le moment, l'administrateur central est l'unique autorité qui attribue, modifie et retire les permissions des utilisateurs, pour chaque service et chaque action.
- Un même compte peut recevoir des permissions dans plusieurs services, si l'administrateur central les attribue explicitement dans chacun.
- La lecture des documents exige une permission de lecture attribuée explicitement; l'appartenance au service seule ne donne pas accès aux documents.
- Le dépôt d'un nouveau document nécessite une permission attribuée dans le service cible.
- La permission de dépôt couvre uniquement la création d'un nouveau document; l'ajout d'une version à un document existant exige une permission distincte.
- La modification des métadonnées et la suppression logique sont deux permissions distinctes, attribuées séparément.
- L'accès est refusé par défaut si le compte, l'affectation au service ou la permission d'action n'est pas établi.

## Conséquences techniques

- L'identité authentifiée doit être résolue depuis un mécanisme applicatif de session ou jeton vérifié; les identifiants transmis librement par le client ne sont jamais fiables.
- Les mots de passe v1 ont une longueur de 15 à 128 caractères, sans règles de composition, et sont hachés avec Argon2id (`m=19456 KiB`, `t=2`, `p=1`), conformément aux recommandations [NIST SP 800-63B](https://pages.nist.gov/800-63-4/sp800-63b.html) et [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- Les sessions utilisent un jeton opaque conservé uniquement sous forme de hash en base, expirent après 8 heures par défaut et utilisent des cookies `HttpOnly`, `SameSite=Strict`, `Secure` hors développement local, avec contrôle CSRF.
- Les tentatives de connexion échouées sont limitées par courriel et adresse source; les événements techniques de limitation sont conservés 24 heures.
- Les autorisations sont évaluées pour chaque requête et chaque action avec `actor_id`, `service_id` et l'action demandée.
- Les permissions sont limitées à un service et administrées par l'autorité désignée pour ce service; aucune permission globale n'est implicite.
- Le module Documents ne doit pas être activé avant la mise en place des comptes, de l'administration des permissions et des contrôles fail-closed.

## Prérequis avant activation

- Implémenter et configurer l'envoi de courriels professionnels pour les liens d'activation et de réinitialisation.
- Créer réellement le premier administrateur à partir de `INITIAL_CENTRAL_ADMIN_EMAIL`, puis retirer ce paramètre du déploiement.
- Fixer et appliquer des protections techniques pour les mots de passe, les sessions et les tentatives de connexion avant toute exposition.

## Questions reportées après v1

- Quel processus de désignation des responsables de service appliquer en pratique ?
- Quelles traces d'administration et d'accès conserver, et pendant combien de temps ?
- Les délégations et accès temporaires restent désactivés par défaut; toute activation future exigera une décision dédiée.

Voir la [politique d'accès Documents](../../security/documents-access-policy-proposal.md) pour les garde-fous et décisions restantes.
