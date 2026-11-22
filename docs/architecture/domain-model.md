# Modèle de domaine — état initial

Aucun modèle métier définitif n'est approuvé à ce stade.

## Candidats techniques pour le module Documents
- Document : identité logique et métadonnées.
- StoredObject : référence au contenu stocké dans MinIO.
- DocumentVersion : à confirmer selon le besoin de versionnement.
- IngestionJob : à confirmer si le traitement est asynchrone.

## Questions ouvertes
- Qui peut déposer, consulter, modifier et supprimer un document ?
- Quelles catégories et métadonnées sont obligatoires ?
- Un document peut-il avoir plusieurs versions ?
- Quelle durée de conservation et quelle politique d'archivage ?
- Quelles règles de confidentialité et de classification ?
- Quelles limites de taille et quels formats Office exacts ?
