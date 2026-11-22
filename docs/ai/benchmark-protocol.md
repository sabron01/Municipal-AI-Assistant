# Protocole de benchmark OCR, embeddings et LLM

## Corpus de test
Constituer un corpus autorisé et anonymisé, représentatif des documents municipaux :
- PDF natifs et PDF scannés ;
- DOCX, XLSX, PPTX selon les formats effectivement utilisés ;
- images photographiées et numérisées ;
- français, arabe, documents mixtes ;
- tableaux, en-têtes, tampons, formulaires et qualité de scan variable.

## OCR / extraction
Comparer au minimum la fidélité du texte, la conservation de l'ordre de lecture, la gestion de l'arabe RTL, l'extraction des tableaux, le temps par page et les ressources consommées.

Pistes à évaluer : Tesseract, PaddleOCR, PyMuPDF et bibliothèques dédiées aux formats Office. La liste n'est pas une sélection définitive.

## Embeddings / recherche
Évaluer les modèles sur un jeu de questions et passages de référence bilingue : Recall@k, MRR ou nDCG, robustesse aux variantes linguistiques et coût mémoire.

## LLM
Évaluer exactitude, citations/provenance, refus en cas d'information absente, qualité bilingue, latence et consommation matérielle.

## Gouvernance
- jeu de données contrôlé et anonymisé ;
- critères et seuils définis avant le test ;
- résultats reproductibles ;
- aucune donnée sensible envoyée à un service externe sans autorisation.
