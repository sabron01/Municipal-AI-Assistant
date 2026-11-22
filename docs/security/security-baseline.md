# Socle sécurité — à compléter avant production

- Secrets hors du dépôt ; rotation et stockage sécurisé à définir.
- PostgreSQL et MinIO non exposés publiquement.
- TLS sur les accès réseau de production.
- Authentification et autorisations obligatoires avant exposition fonctionnelle.
- Validation du contenu des fichiers, limites de taille et protection contre les fichiers malveillants.
- Journalisation sans contenu documentaire ni secret.
- Sauvegarde/restauration testée de PostgreSQL et MinIO.
- Politique de conservation, classification et traitement des données personnelles à valider.
- MCP : outils explicitement autorisés, moindre privilège, validation et audit.
