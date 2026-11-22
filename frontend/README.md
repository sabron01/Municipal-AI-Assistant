# Interface d’administration

Application React + TypeScript de gestion du registre Direction → Service et Catégorie → Sous-catégorie.

## Développement local

1. Démarrer le backend FastAPI sur `http://127.0.0.1:8000` et vérifier que ses migrations sont appliquées.
2. Copier `.env.example` vers `.env.local` si le backend écoute à une autre adresse; `VITE_API_PROXY_TARGET` configure la cible du proxy de développement.
3. Installer les dépendances avec `npm install`.
4. Démarrer l’interface avec `npm run dev` et ouvrir l’URL affichée (par défaut `http://127.0.0.1:5173`).

Les appels `/api/v1/*` sont relayés par Vite vers le backend. Cela garde les appels et les cookies de session sur la même origine dans le navigateur et évite une configuration CORS de développement. L’interface n’accède pas directement à PostgreSQL ou RustFS. Les secrets restent dans l’environnement du backend et ne doivent jamais être ajoutés aux variables `VITE_*`.

Les pages du registre sont réservées à l’administrateur central. Les modifications utilisent le cookie de session et transmettent le cookie CSRF dans `X-CSRF-Token`. Les opérations de suppression, archivage et déplacement ainsi que l’upload de documents ne font pas partie de cette interface.
