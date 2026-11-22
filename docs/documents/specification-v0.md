# Module Documents — Spécification initiale v0

> Historique : cette version est remplacée pour la conception par [la spécification technique v1](specification-v1.md) et [ADR-009](../architecture/adr/ADR-009-documents-module.md). Les règles métier confirmées sont détaillées dans ces documents; les questions encore ouvertes restent bloquantes avant exposition fonctionnelle.

## Objectif
Définir le premier module du produit sans présumer des règles administratives non communiquées.

## Capacités candidates
1. Déposer un fichier.
2. Consulter une liste et les métadonnées.
3. Consulter les détails d'un document.
4. Télécharger le contenu.
5. Supprimer ou archiver uniquement après définition de la politique applicable.
6. Préparer l'extraction de contenu pour une future indexation RAG, sans construire le RAG complet dans ce sprint.

## Métadonnées techniques candidates
- identifiant interne ;
- nom original et nom de stockage ;
- type MIME détecté ;
- taille ;
- empreinte SHA-256 ;
- clé objet MinIO ;
- date de dépôt ;
- état technique du traitement.

## Sécurité et robustesse à spécifier
- validation réelle du type de fichier, pas seulement de l'extension ;
- limites de taille ;
- noms de stockage non prédictibles ;
- analyse antivirus/quarantaine à évaluer ;
- contrôle d'accès avant téléchargement ;
- journalisation des opérations ;
- sauvegarde PostgreSQL et MinIO ;
- protection contre path traversal et fichiers actifs ;
- conservation de la provenance et de l'intégrité.

## Questions métier bloquantes
- catégories et nomenclature ;
- métadonnées obligatoires ;
- utilisateurs et droits ;
- visibilité par service ;
- versionnement ;
- suppression, archivage et durée de conservation ;
- règles de confidentialité ;
- formats Office exacts et limites de taille.

## Hors périmètre du Sprint 0
- workflow de validation métier ;
- authentification définitive ;
- indexation RAG complète ;
- chatbot documentaire ;
- suppression réelle de documents.
