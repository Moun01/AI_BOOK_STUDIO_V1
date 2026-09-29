# AI BOOK STUDIO

**Transformez vos PDF en livres professionnels avec l’IA.**

Application web fonctionnelle, française, avec serveur FastAPI, base SQLite, projets privés et fichiers réellement créés. Interface responsive sans dépendance frontend distante. Cette livraison est une **version locale testable**, pas une infrastructure SaaS prête à ouvrir au public sans durcissement.

## Tester immédiatement

L’application tourne dans l’aperçu live **AI BOOK STUDIO**, sur le port **8000**.

1. Cliquer sur **Explorer un livre de démonstration**.
2. Créer le livre, puis cliquer sur **ANALYSER MON LIVRE**.
3. Inspecter **Manuscrit**, **Illustrations**, **Mise en page** et **Couverture**.
4. Après modification, cliquer sur **Recomposer le livre**.
5. Consulter **Contrôle qualité**, puis **Aperçu**.
6. Cliquer sur **Exporter** et télécharger les vrais fichiers.

Une session découverte privée est créée au premier import. Pour disposer d’un accès récupérable par mot de passe, **créer un compte avant de créer ses projets**, via le bouton de connexion au bas de la barre latérale. Les sessions découverte ne sont pas transférées automatiquement vers les comptes et expirent après sept jours.

### Exemple déjà exporté

Dans `examples/livre-demonstration/` :

- `original.pdf` : manuscrit fictif de six pages ;
- `complete.pdf` : première de couverture, intérieur et quatrième ;
- `interior.pdf` : intérieur au format A5 ;
- `cover.pdf` : couverture à plat, quatrième + dos + première, avec fond perdu et TrimBox ;
- `book.epub` : texte refluable ;
- `projet.json`, `controle-qualite.json` : structure et rapport ;
- `preview-*.png` : pages rasterisées depuis le PDF exporté.

Le résumé de cet exemple préparé est un texte de présentation rédigé pour la démo. Lors d’un import ordinaire, le résumé gratuit initial est **un extrait du texte original**, étiqueté comme tel, jusqu’à édition ou appel explicite à Text AI.

## Fonctions réellement disponibles

| Domaine | Réalisation |
|---|---|
| Import PDF | PDF textuel validé, maximum 30 Mo et 250 pages ; documents chiffrés refusés |
| Extraction | Texte, pages source, typographie, métadonnées, langue estimée, nombre de tableaux, extraction des images intégrées |
| Structure | Détection heuristique des titres, chapitres, paragraphes et citations ; texte source conservé, sans réécriture |
| Illustrations | Suggestions avec passage exact, section, page source, idée, prompt et style ; import, remplacement, téléchargement, retrait, redimensionnement proportionnel et placement avant/après un bloc |
| IA générative | Connecteurs réels Ollama et AUTOMATIC1111 ; options OpenAI explicites ; aucun faux résultat si le fournisseur est absent |
| Éditeur | Édition des blocs, ajout/suppression/réorganisation des sections, couleur, police, marges, sauvegarde automatique et historique serveur de 30 versions |
| Mise en page | ReportLab : A4, A5, 6 × 9 pouces, dimensions personnalisées, 8 préréglages typographiques, pagination, en-têtes, proportions d’images préservées |
| Couverture | Première, dos et quatrième ; texte ajusté à la zone ; image importée ou reprise des illustrations ; épaisseur du dos calculée |
| Qualité | Bornes du texte intérieur, pages vides/peu remplies, résolution effective des images, pagination, fond perdu et avertissements prépresse |
| Correction | Marges d’au moins 18 mm, fond perdu de 3 mm, réduction des images trop petites et nouveau calcul de mise en page |
| Aperçu | Images des pages du **PDF réel**, zoom, navigation, miniatures, plein écran si autorisé par le navigateur |
| Export | PDF complet, intérieur, couverture à plat et EPUB texte ; téléchargements protégés par session |
| Assistant | Commandes françaises à règles modifiant réellement le projet ; explicitement **pas un LLM** |
| Stockage | SQLite, fichiers privés côté serveur, contrôle de propriétaire à chaque accès |
| Traitement | File en arrière-plan, deux workers, étapes comptées après exécution, erreurs visibles, export en dossier intermédiaire |

## IA : ce qui est gratuit et ce qui doit être connecté

### Sans aucune clé API

Extraction, analyse heuristique, prompts, édition, import d’images, couverture typographique, composition, contrôle limité et exports fonctionnent sans API payante.

**Une vraie illustration IA a été générée avec l’outil d’image Arena pendant la construction de l’application.** Elle représente Amina et des vendeuses sur un marché de Cotonou, devant des casiers réfrigérés solaires, conformément au chapitre 1. Elle est incluse dans `examples/illustration-demo.png` et réutilisée dans les nouveaux livres de démonstration. Son origine est indiquée : **« IA Arena · illustration de démonstration pré-générée »**.

Cette image n’est **pas** une génération exécutée à chaque import. Le serveur web ne peut pas appeler directement les outils de cette conversation Arena ; il ne dispose ni d’un endpoint Arena documenté ni d’un modèle d’image préinstallé. Le bouton Générer ne présente jamais cette image comme un nouveau résultat.

### Text AI local : Ollama

Installer Ollama sur le même serveur, télécharger un modèle, par exemple :

```sh
ollama pull qwen2.5:3b
ollama serve
```

Dans **Paramètres IA → Text AI**, sélectionner Ollama et saisir `qwen2.5:3b`. Le connecteur appelle `http://127.0.0.1:11434/api/generate` côté serveur. L’action **Enrichir avec Text AI** met à jour le résumé, les mots-clés et le public probable, **sans réécrire le manuscrit**. L’extrait transmis est limité à 22 000 caractères ; les livres longs ne sont donc pas analysés intégralement par ce connecteur initial.

### Image AI local : Stable Diffusion

Installer AUTOMATIC1111, un modèle compatible, puis démarrer le service avec `--api` sur le port 7860. Sélectionner **Stable Diffusion — AUTOMATIC1111 local** dans les paramètres. Le serveur utilise `/sdapi/v1/txt2img`, décode la réponse et enregistre l’image réelle.

Le logiciel et les modèles compatibles peuvent être gratuits, mais le calcul exige des ressources matérielles. Un GPU adapté est recommandé. Aucun modèle n’a été installé dans cette livraison. Les licences des modèles doivent être vérifiées selon l’usage.

### APIs externes facultatives

OpenAI Text et Images sont des options qui nécessitent une clé et peuvent être facturées. Le frontend demande confirmation avant les opérations concernées. Les clés sont stockées dans la base privée et ne sont **jamais renvoyées par l’API de paramètres**.

Les connecteurs génératifs externes/locaux sont implémentés, **mais n’ont pas fait l’objet d’un test positif contre un fournisseur actif**, faute de modèle installé et de clé. Le chemin d’erreur « aucun fournisseur disponible » est testé. Les changements futurs des APIs peuvent nécessiter une adaptation.

Vision AI : emplacement pour une clé uniquement ; **ni OCR ni connecteur Vision opérationnel**. L’interface l’indique explicitement.

## Assistant : commandes prises en charge

- `Corrige les problèmes de mise en page` : marges, taille d’images, nouveau rendu et nouveau contrôle.
- `Réorganise cette page` : recomposition générale, pas manipulation arbitraire des éléments d’une page.
- `Crée une nouvelle couverture` : recalcul de la couverture typographique avec les paramètres actuels.
- `Mets les illustrations du chapitre 2 en style 3D` : modification réelle des prompts. Les images déjà présentes ne changent pas sans régénération.
- `Change l’image de la page 3` : recherche d’une suggestion sur la **page du PDF source** et génération via le fournisseur connecté.
- `Ajoute une illustration au chapitre 2` : ajout d’une suggestion ancrée dans un bloc réel.

Les numéros de chapitre correspondent à l’ordre des sections dans le panneau de structure. Une commande non reconnue renvoie une explication, jamais une fausse confirmation.

## Installation et reprise

Python 3.11+ recommandé. Les versions réellement utilisées sont épinglées dans `requirements.txt`.

```sh
cd ai-book-studio
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Le serveur écoute `0.0.0.0:8000`. Le port peut être modifié avec `PORT=8080 ./start.sh`. Les polices DejaVu sont fournies dans `assets/fonts/` avec leur notice.

### Docker

```sh
docker build -t ai-book-studio .
docker run --rm -p 8000:8000 -v studio-data:/studio/data ai-book-studio
```

Avec Docker, les connecteurs en boucle locale ciblent **le conteneur**, pas l’ordinateur hôte. Pour connecter les services IA de l’hôte, adapter le connecteur/réseau (par exemple réseau hôte sur Linux). Le Dockerfile est fourni ; sa construction n’a pas été testée ici.

## Architecture

```text
static/index.html + style.css + app.js
                 │ mêmes origine et session
                 ▼
app/main.py      FastAPI · authentification · contrôle d’accès
                 projets · historique · file de travaux · fichiers
                 │
                 ├── app/engines.py
                 │   extract_pdf       → PDF ENGINE
                 │   analyze_document  → DOCUMENT ANALYZER / BOOK STRUCTURE
                 │   build_prompts     → IMAGE PROMPT ENGINE
                 │   render_interior   → LAYOUT ENGINE
                 │   render_covers     → COVER GENERATOR
                 │   quality_check     → QUALITY CONTROL
                 │   export_book/epub  → EXPORT ENGINE
                 │
                 ├── app/providers.py
                 │   TextProvider      → Ollama / OpenAI
                 │   LocalImageProvider→ AUTOMATIC1111 / OpenAI Images
                 │
                 └── data/
                     studio.sqlite3
                     <project_id>/original.pdf, extracted.json,
                                  images, PDF, EPUB, aperçus
```

Les moteurs sont des fonctions indépendantes regroupées dans `engines.py`. Un moteur peut être remplacé sans réécrire les routes ni le frontend, en conservant son contrat de données. Le livre contient `chapters[].blocks[]` et `suggestions[]`, avec identifiants d’ancrage et page source. Dans cette version, chapitres et sections utilisent le même niveau de structure : pas d’arbre de sous-chapitres imbriqués.

## Sécurité mise en œuvre

- Mots de passe hachés par scrypt, sel aléatoire par compte.
- Sessions aléatoires, empreinte SHA-256 dans la base, cookie HTTP-only, expiration 7 jours ; SameSite=Lax en HTTP local, Secure/SameSite=None/Partitioned en HTTPS pour l’aperçu intégré. Les mutations nécessitent toujours l’en-tête personnalisé et CORS reste fermé.
- Limitation des tentatives d’authentification par adresse IP en mémoire.
- Projets et fichiers accessibles seulement à leur propriétaire.
- Aucun montage public du répertoire `data/` ; liste stricte de noms téléchargeables.
- Mutations nécessitant un en-tête personnalisé ; aucune ouverture CORS.
- Validation de signature PDF puis analyse par le parseur ; bornes de taille et nombre de pages.
- Validation et réencodage des images, limite 15 Mo / 35 mégapixels.
- Échappement HTML de l’interface et du texte utilisé par ReportLab.
- Rejet d’une sauvegarde sur une version périmée ; une tâche active bloque les mutations du projet.
- Dossier privé 0700 et base 0600 ; clés côté serveur, **pas de chiffrement applicatif au repos**.

### Avant exploitation publique

Ajouter HTTPS contrôlé, chiffrement du disque/secrets, sauvegardes, quotas globaux d’upload/CPU/stockage, antivirus, isolation des parseurs dans un processus/conteneur, proxy limitant les corps de requête, journalisation avec filtrage des secrets, nettoyage de sessions, réinitialisation des mots de passe, validation email et supervision. La limite de 30 projets par compte n’est pas un quota global. Il n’y a ni facturation ni gestion d’abonnement.

La file de traitements est locale. Après redémarrage, les travaux interrompus sont marqués en erreur ; ils doivent être relancés. L’export intermédiaire évite de remplacer les fichiers lors d’une erreur de rendu, mais ne constitue pas une transaction multi-fichiers résistante à une panne système au milieu de leur publication.

## Limites éditoriales et prépresse

- Pas d’OCR : fournir un PDF avec du texte extractible.
- La structure heuristique et la langue restent des estimations. Les documents multi-colonnes, en-têtes récurrents et typographies atypiques peuvent nécessiter une correction manuelle.
- Texte original conservé dans le PDF source et l’extraction. Les retours de ligne sont reflués pour la nouvelle mise en page ; le livre n’est pas réécrit.
- Tableaux : détection et texte extrait, pas reconstruction fiable des cellules.
- Pas d’éditeur WYSIWYG à placement libre ni d’ajout/suppression de **pages physiques**. Les opérations s’appliquent aux sections et aux blocs ; les pages sont recalculées.
- Les styles d’illustration pilotent les prompts. Une cohérence parfaite des personnages nécessite des outils supplémentaires (images de référence, modèles dédiés, etc.).
- EPUB texte seulement, sans illustrations ni équivalence de pagination avec le PDF ; pas de validation EPUBCheck exécutée.
- PDF en RVB, polices incorporées, non certifié PDF/X, sans profil ICC d’imprimeur. Pas de garantie automatique « prêt à imprimer » universelle.
- Le contrôle ne certifie pas tous les chevauchements, les glyphes absents, les ruptures sémantiques ou la qualité des tableaux. Inspection visuelle indispensable.
- Couverture : dos = pages ÷ 2 × épaisseur d’une **feuille** ; à confirmer selon papier et reliure. Sous 5 mm, pas de texte sur le dos. Pas de débordement d’image sur l’intérieur ; couverture seule avec fond perdu.

## Tests exécutés

```sh
# Avec le serveur démarré
python tests/test_workflow.py
python tests/export_examples.py

# Facultatif : tests navigateur
npm install --no-save playwright
npx playwright install --with-deps chromium
node tests/browser.cjs
```

**Résultats :** 19 contrôles d’intégration réussis ; parcours navigateur réussi sans erreur JavaScript ; vérification à 390 px sans débordement horizontal. Formats A4, A5, 6 × 9 et personnalisé rendus. Voir `tests/results.json`, `tests/browser-results.json` et `TESTS.md`.

## Licences des dépendances

Les outils sont disponibles sans paiement obligatoire pour tester. **PyMuPDF est distribué sous AGPL ou licence commerciale** : vérifier les obligations applicables, particulièrement avant une exploitation SaaS propriétaire. Gratuit ne signifie pas exempt d’obligations de licence. Les polices DejaVu et les modèles IA ont leurs propres conditions. Aucun modèle IA tiers n’est redistribué ici.
