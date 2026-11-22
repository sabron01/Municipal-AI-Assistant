# Vue d'ensemble

## Décisions retenues
- Monorepo.
- Monolithe modulaire selon DDD.
- Clean Architecture à l'intérieur des modules.
- PostgreSQL avec extension pgvector.
- MinIO pour le stockage objet des fichiers.
- Ollama comme runtime local envisagé ; modèles à sélectionner après benchmark.
- MCP limité à des outils internes.

## Modules candidats
Documents, Identité & Accès, Connaissances/RAG, Assistant IA, Administration. Cette liste est une hypothèse d'organisation technique, pas une validation des processus métier.

## Principes
- Commencer par le module Documents.
- Séparer métadonnées relationnelles et contenu binaire objet.
- Conserver les identifiants et la provenance des documents.
- Introduire les traitements asynchrones seulement lorsque les besoins et volumes sont établis.
