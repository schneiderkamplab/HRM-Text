# Draft ANSSI clarification request — not sent

Recipient: controle@ssi.gouv.fr

Subject: DFM Mimir (iOS/macOS) — demande de clarification sur les formalités de cryptologie

Madame, Monsieur,

Syddansk Universitet (University of Southern Denmark), université danoise située
Campusvej 55, DK-5230 Odense M, CVR 29283958, prépare la distribution en France
sur l'App Store de DFM Mimir 0.1.5 (12), pour iOS et macOS.

Il s'agit d'un assistant d'intelligence artificielle exécuté localement. Les
fonctions réseau optionnelles (recherche web, retour utilisateur confirmé et
téléchargement de modèles) utilisent HTTPS via Dart/Flutter et sa bibliothèque
BoringSSL intégrée. L'application utilise aussi le trousseau Apple pour conserver
une clé d'accès, et SHA-256 pour vérifier les modèles. Elle ne propose ni VPN,
ni messagerie chiffrée entre personnes, ni algorithme cryptographique propriétaire.

Apple demande une déclaration française pour cette catégorie d'application.
Pourriez-vous nous confirmer :

1. Si une dispense s'applique à cette configuration ;
2. Si une déclaration existante de Flutter/BoringSSL pourrait couvrir cette
   intégration et quels justificatifs seraient nécessaires ;
3. À défaut, les opérations à déclarer et l'entité responsable dans le cas d'une
   université danoise distribuant par l'intermédiaire d'Apple en France ;
4. Le justificatif institutionnel attendu d'une université publique étrangère
   en remplacement d'un extrait Kbis, et les pièces techniques nécessaires ?

Une description technique du produit est jointe. Nous ne disposons pas à ce
stade d'une attestation dont la couverture de cette application soit établie.

Cordialement,

[Nom, fonction et coordonnées du représentant autorisé de SDU — à compléter]

Contact technique proposé : Peter Schneider-Kamp, petersk@imada.sdu.dk

---

Before sending: obtain SDU's authorized sender, check internal existing coverage,
and attach ENCRYPTION-TECHNICAL.md in the recipient's accepted document format.
This inquiry is not the signed formal declaration. No message has been sent.
