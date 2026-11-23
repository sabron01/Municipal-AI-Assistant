# ADR-014 — Politique d'upload du module Documents v1

- Date : 2026-11-23.
- Statut : accepté.
- Contexte : les décisions D1 de la spécification v1 (formats, taille, analyse antivirus, PDF protégés) n'étaient pas tranchées ; les routes `/documents` restaient fermées par défaut. Le propriétaire du produit a validé la politique ci-dessous, confirmée par la configuration locale.

## Décisions

| ID | Décision validée | Conséquence |
|---|---|---|
| DOC-005 | Formats autorisés : PDF, DOCX, XLSX, PPTX, PNG, JPEG. Taille maximale : 25 Mo, soit 26 214 400 octets. | Liste MIME configurable ; détection par signature ; extension seulement informative. |
| DOC-006 | Aucun analyse antivirus en v1. | Risque accepté pour un usage interne ; aucune quarantaine ni état de scan. À réévaluer avant toute exposition élargie. |
| DOC-007 | Les PDF chiffrés ou protégés par mot de passe sont refusés. | Refus `415` dès la validation, avant stockage ; un PDF chiffré resterait illisible pour l'OCR et le téléchargement contrôlé. |

## Détails

- Les types MIME autorisés sont : `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.openxmlformats-officedocument.presentationml.presentation`, `image/png`, `image/jpeg`.
- Le type réel est détecté par signature ; une extension trompeuse ne change pas la décision.
- La limite de 25 Mo s'applique au flux complet, avec rejet en streaming (`413`) sans conservation partielle.
- La détection des PDF chiffrés recherche le marqueur `/Encrypt` dans le dictionnaire trailer, borné aux derniers 1 Mio. C'est une heuristique : elle privilégie le refus en cas de doute et ne remplace pas un parseur PDF complet.
- L'activation reste conditionnée à `DOCUMENT_POLICY_APPROVED=true`, à une liste MIME et à une taille explicites, ainsi qu'à l'authentification applicative et à la revue QA/Security.

## Options rejetées

- **Archives ZIP** : surface d'attaque et inspection d'archives imbriquées hors périmètre v1.
- **Accepter les PDF chiffrés** : contenu non vérifiable, non indexable et potentiellement non téléchargeable selon le mot de passe.
- **Scan antivirus obligatoire en v1** : aucun service de scan retenu ; l'ajouter exigerait un port, un état intermédiaire et un worker dédiés.

## Conséquences

- Variables d'environnement : `DOCUMENT_MAX_UPLOAD_BYTES=26214400`, `DOCUMENT_ALLOWED_MEDIA_TYPES`, `DOCUMENT_POLICY_APPROVED`.
- Les décisions D2 à D5 (cycle de vie du registre, champs métier, rétention, confidentialité) restent ouvertes et bloquent un usage partagé, pas l'activation technique.
- Toute modification de cette politique (formats, taille, scan) nécessite un nouvel ADR et une revue QA/Security.
