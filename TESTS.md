# Rapport de vérification — AI BOOK STUDIO

Date : 29 septembre 2026.

## Parcours serveur : 19 contrôles réussis

Exécution réelle de `python tests/test_workflow.py` contre l’application sur le port 8000 :

1. Création d’un compte et session authentifiée.
2. Création/import du PDF de démonstration, six pages source.
3. Extraction, structure et suggestions de visuels.
4. Présence de Cotonou dans les passages utilisés par les prompts.
5. PDF original, intérieur, couverture à plat et complet ouverts par le parseur ; TrimBox de la couverture vérifiée.
6. EPUB créé comme archive ZIP lisible, sans erreur d’intégrité.
7. Aperçu PNG réellement décodable.
8. Rapport de qualité comprenant l’avertissement PDF non certifié pour le prépresse.
9. Import d’une image, édition du texte et recomposition.
10. Présence vérifiée du texte modifié et d’une image intégrée dans le PDF intérieur.
11. Annulation puis rétablissement, persistés côté serveur.
12. Modification réelle des prompts par l’assistant local.
13. Génération demandée sans fournisseur : erreur explicite, aucun faux résultat.
14. Correction automatique puis nouvel export.
15. Clé API de test enregistrée, non renvoyée par GET /settings, puis supprimée.
16. Autre session utilisateur : accès au projet et au fichier refusé.
17. Fichier non PDF rejeté.
18. Sauvegarde sur une révision obsolète refusée.
19. Suppression du projet et vérification de sa disparition.

Résultat lisible par machine : `tests/results.json`.

## Parcours navigateur : réussi

Chromium headless via Playwright, `node tests/browser.cjs` :

- Ouverture du dashboard.
- Création du livre de démonstration.
- Clic sur l’analyse et attente de la fin réelle du travail.
- Consultation du plan d’illustrations.
- Message explicite sur l’absence de générateur connecté.
- Édition du sous-titre et sauvegarde automatique.
- Création effective de la couverture et du PDF.
- Affichage des pages et navigation suivante.
- Téléchargement du PDF complet, enregistré dans `tests/browser-export.pdf`.
- Sauvegarde des paramètres IA.
- Vérification d’un viewport 390 × 844 pixels, sans débordement horizontal.
- Aucune exception JavaScript observée.

Résultat : `tests/browser-results.json`.
Captures : `tests/dashboard-desktop.png`, `tests/dashboard-mobile.png`, `tests/editor-desktop.png`.

Il s’agit d’une émulation de dimensions mobiles dans Chromium, **pas** d’un test sur un appareil Android physique ni d’une certification tous navigateurs.

## Export illustré et formats

`python tests/export_examples.py` a produit le livre présent dans `examples/livre-demonstration/`.

L’illustration fournie a été **réellement générée avec l’outil d’image Arena** pour le passage sur les casiers réfrigérés solaires de Cotonou. Elle a ensuite été intégrée au moteur de composition ; sa présence a été vérifiée visuellement dans `preview-3.png`.

Formats rendus sans alerte de texte intérieur hors marges dans ce document :

- A5 / Premium : 7 pages intérieures dans l’exemple préparé ;
- A4 / Moderne : 6 pages ;
- 6 × 9 pouces / Magazine : 4 pages ;
- Personnalisé 120 × 190 mm / Luxe : 10 pages.

Ces comptes s’appliquent à l’exemple préparé au moment du test, pas à tous les projets ni à toute modification ultérieure.

## Défauts trouvés et corrigés

- **Extraction ligne par ligne** : certains PDF émis par ReportLab étaient divisés en petits blocs, empêchant les suggestions contextuelles. Regroupement géométrique des lignes adjacentes, en conservant le texte et sa provenance.
- **Recomposition des paragraphes** : suppression des retours de ligne physiques dans le rendu, sans modifier les mots du manuscrit, pour permettre une vraie nouvelle pagination.
- **Couvertures longues** : ajustement progressif de la taille du texte dans des zones bornées ; erreur visible si le format est trop petit plutôt qu’un succès fictif.
- **Titre d’en-tête trop large** : réduction du libellé à la largeur disponible.
- **Identité visuelle** : correction de l’alignement du logo dans la barre latérale.
- **Statut de sauvegarde** : affichage d’une sauvegarde en attente tant que la modification n’est pas enregistrée.

## Vérifications non réalisées / garanties non données

- Aucun appel positif aux connecteurs Ollama, AUTOMATIC1111 ou OpenAI : aucun modèle local ou identifiant externe disponible. Les connecteurs et leurs réponses d’échec sont implémentés ; leur fonctionnement avec un fournisseur actif doit être validé dans l’environnement de déploiement.
- Pas de validation EPUBCheck, PDF/X, CMJN/ICC, ni validation par un imprimeur.
- Pas de test de charge, de pénétration ou de crash au milieu d’une publication multi-fichiers.
- Pas de garantie d’extraction fidèle des tableaux et des mises en page multi-colonnes.
- Pas de contrôle exhaustif des glyphes, chevauchements ou incohérences typographiques.
- Dockerfile fourni mais non construit dans cet environnement.

**Conclusion :** le parcours local d’un PDF textuel jusqu’aux fichiers exportés est opérationnel et testé. Les fonctions nécessitant un modèle non disponible, ainsi que les limites d’édition et de prépresse, sont indiquées dans l’interface et dans le README.
