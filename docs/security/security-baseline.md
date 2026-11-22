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
