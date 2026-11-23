# ADR-016 — Métadonnées et références du module Documents v1

- Date : 2026-11-24.
- Statut : accepté.
- Contexte : les décisions D3 de la spécification v1 (champs obligatoires, numéro de référence, champs supplémentaires, titre/langues) n'étaient pas tranchées. Le contrat initial ne comportait que le titre et une référence optionnelle sans unicité.

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-012 | Champs obligatoires à la création et à la mise à jour : titre, numéro de référence et date du document. | `POST` et `PATCH /documents` exigent `reference_number` et `document_date`; les documents existants sans ces valeurs bloquent la migration. |
| DOC-013 | Le numéro de référence est saisi manuellement, sans motif imposé en v1. | Aucune validation de format; un motif pourra être ajouté ultérieurement sans casser les données. |
| DOC-014 | Le numéro de référence est unique globalement. | Colonne `reference_normalized` (NFKC, espaces réduits, casefold) avec index unique; conflit renvoyé en `409`. |
| DOC-015 | Champs supplémentaires inclus en v1 : date du document, émetteur, mots-clés, niveau de confidentialité, code de conservation. | Cinq colonnes ajoutées; l'émetteur, les mots-clés, le niveau de confidentialité et le code de conservation sont optionnels. |
| DOC-016 | Niveau de confidentialité et code de conservation sont stockés comme texte libre borné en v1. | Aucune taxonomie ni liste de valeurs n'est imposée; les échelles seront définies par D4 et D5 sans migration de données. |
| DOC-017 | Convention de titre « type + objet + année » documentée seulement. | Aucun contrôle automatique en v1; la convention est une consigne d'usage à vérifier par revue. |
| DOC-018 | La date du document peut être postérieure à aujourd'hui. | Aucune restriction de date. |

## Détails

- La date du document est distincte de la date de dépôt (`created_at`). Elle représente la date de l'acte ou du document.
- Les mots-clés sont limités à 20 par document et 100 caractères par mot-clé (bornes techniques).
- L'émetteur est limité à 200 caractères; le niveau de confidentialité et le code de conservation à 100 caractères.
- La normalisation du titre (NFC) n'est pas imposée; le titre est conservé tel que saisi après suppression des espaces aux extrémités.
- La convention de titre recommandée pour les actes communaux est : `[Type] – [Objet] – [Année]`, par exemple `Arrêté – Attribution de subvention – 2026`. Elle n'est pas contrôlée par l'application en v1.

## Options rejetées

- **Motif de référence imposé en v1** : reporté; aucun motif métier n'a été validé.
- **Unicité par Service** : la règle métier exige une unicité globale (référence de l'acte).
- **Taxonomies pour la confidentialité et la conservation** : reportées à D4/D5 pour éviter d'inventer des échelles.
- **Contrôle automatique de la convention de titre** : reporté; aucune structure exacte n'a été fournie.

## Conséquences

- Migration `20261122_06` : colonnes `reference_normalized` (unique), `document_date` (non nulle), `issuer`, `keywords`, `confidentiality_level`, `retention_code`; `reference_number` devient non nul.
- Les documents existants sans référence ni date bloquent la migration; aucun numéro n'est inventé.
- `PATCH /documents/{id}` exige désormais `document_date` et `reference_number`.
- Toute modification de ces règles (motif, taxonomie, convention) nécessite un nouvel ADR.
