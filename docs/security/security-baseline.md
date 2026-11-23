# Socle sécurité — à compléter avant production

- Secrets hors du dépôt ; rotation et stockage sécurisé à définir.
- PostgreSQL et RustFS non exposés publiquement.
- TLS sur les accès réseau de production.
- Authentification et autorisations obligatoires avant exposition fonctionnelle.
- Validation du contenu des fichiers, limites de taille et protection contre les fichiers malveillants.
- Journalisation sans contenu documentaire ni secret.
- Sauvegarde/restauration testée de PostgreSQL et RustFS.
- Politique de conservation, classification et traitement des données personnelles à valider.
- MCP : outils explicitement autorisés, moindre privilège, validation et audit.
- Les routes Documents restent désactivées/non exposées jusqu'à validation de l'identité, de l'autorisation ressource/service et de l'audit; voir [spécification v1](../documents/specification-v1.md).
- Les comptes applicatifs et l'attribution centralisée des permissions sont consignés dans [ADR-012](../architecture/adr/ADR-012-application-managed-accounts.md); les routes restent désactivées jusqu'à mise en place de l'authentification et du cycle de vie complet des comptes dans [la politique d'accès](documents-access-policy-proposal.md).

## Limitation des tentatives de connexion et reverse proxy

La limitation s'appuie sur `request.client.host` et sur l'adresse électronique normalisée : 10 échecs par adresse électronique et 100 échecs par adresse IP sur 15 minutes. L'en-tête `X-Forwarded-For` n'est volontairement pas pris en compte, car il est falsifiable sans proxy de confiance.

Conséquences à traiter au déploiement :

- Derrière un reverse proxy, toutes les requêtes portent l'adresse du proxy : le quota de 100 échecs devient partagé par l'ensemble des utilisateurs et peut bloquer des connexions légitimes. Soit l'API est exposée directement, soit le proxy est configuré pour remplacer l'adresse source et l'extraction côté API est adaptée en conséquence.
- Le quota par adresse électronique reste efficace quel que soit le proxy.

## Cookies et transport

- `AUTH_COOKIE_SECURE=true` est obligatoire hors développement local : les cookies prennent alors le préfixe `__Host-` et ne sont émis qu'en HTTPS.
- Le nom des cookies dépend de ce réglage : le modifier invalide les sessions existantes, à planifier hors plage d'utilisation.
