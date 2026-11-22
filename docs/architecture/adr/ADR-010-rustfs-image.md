# ADR-010 — Image RustFS officielle et épinglée

- Date : 2026-11-22.
- Statut : accepté pour le socle de développement local.
- Contexte : le démarrage de Compose a échoué, car `rustfs/rustfs-x86-musl:v2.3.1` n'est pas récupérable depuis le registre configuré.
- Décision : utiliser l'image officielle `rustfs/rustfs` épinglée par digest, version embarquée 1.0.6 (`sha256:ee717072290bec9b11abfc0365f8310b00df1cd9b3639943edae47bdef05044a`). `RUSTFS_IMAGE` permet de la remplacer explicitement.
- Configuration : lancer le binaire avec `/data`, conserver volume nommé, ports API/console et variables `RUSTFS_*`.
- Justification : l'image locale en cache porte ces labels de version et digest; la documentation officielle RustFS donne `rustfs/rustfs:latest` et l'argument `/data` pour le démarrage Docker. Le digest fixe le contenu réellement validé et évite la dérive du tag mutable.
- Portée : environnement local seulement. La compatibilité S3 utilisée par l'adaptateur (`PutObject`/`HeadObject` avec SHA-256) doit encore être vérifiée contre ce runtime avant validation d'intégration.
- Références : [démarrage Docker officiel RustFS](https://docs.rustfs.com/en/installation/container/docker), [image Docker officielle](https://hub.docker.com/r/rustfs/rustfs).
