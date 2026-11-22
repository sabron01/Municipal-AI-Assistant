# ADR-005 — Authentification différée

- Statut : partiellement décidé.
- Décision : les comptes sont gérés par l'application et, pour le moment, les permissions sur les documents sont attribuées par l'administrateur central, conformément à [ADR-012](ADR-012-application-managed-accounts.md). La visibilité par service est définie par [ADR-011](ADR-011-documents-service-visibility.md).
- Condition : les prérequis techniques de sécurité doivent être définis et validés avant toute exposition; les choix non bloquants peuvent être reportés après v1 selon [ADR-012](ADR-012-application-managed-accounts.md).
- Garde-fou : aucune fonctionnalité documentaire ne doit être exposée en production sans contrôle d'accès validé.
