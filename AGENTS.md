# Instructions globales aux agents

## Mission
Construire progressivement l'Assistant IA Municipal de Tataouine. Le projet suit un monorepo, un monolithe modulaire DDD et les principes Clean Architecture.

## Règles non négociables
1. Ne jamais inventer une règle métier, un rôle, un circuit de validation ou une obligation réglementaire.
2. Identifier clairement les hypothèses et les questions ouvertes.
3. Ne pas développer une fonctionnalité hors du sprint autorisé.
4. Respecter les responsabilités des profils dans `.agents/`.
5. Documenter toute décision d'architecture dans `docs/architecture/adr/`.
6. Ne jamais déclarer un test, une compilation, une migration ou un déploiement réussi sans l'avoir réellement exécuté.
7. Ajouter des tests pertinents avec chaque changement de code.
8. Ne pas placer de secrets dans Git. Utiliser `.env` local et des variables d'environnement.
9. Ne pas introduire de microservices sans décision explicite.
10. Les outils MCP sont internes ; aucun outil ne doit exposer une action externe sans validation.

## Architecture
- Domaine : entités, objets-valeurs, invariants métier explicitement validés.
- Application : cas d'utilisation et ports.
- Infrastructure : adaptateurs DB, stockage, OCR et fournisseurs IA.
- Présentation : API HTTP FastAPI.
- Les dépendances pointent vers le domaine et les ports, jamais l'inverse.

## Collaboration
- L'Architecte coordonne les contrats et les ADR.
- Un seul agent est propriétaire d'un fichier pendant une modification.
- Les changements transverses sont annoncés et coordonnés.
- QA/Security examine les changements sensibles avant clôture.
- Les profils spécialisés complètent ces règles, ils ne les remplacent pas.

## Gate de validation
Avant chaque sprint : confirmer le périmètre et les critères d'acceptation.
Avant fusion : tests exécutés, résultats consignés, revue QA/Security.
Pour toute décision métier non spécifiée : suspendre l'implémentation et demander clarification.
