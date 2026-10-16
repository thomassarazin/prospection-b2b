# prospection-b2b

Pipeline de prospection B2B en ligne de commande. Il recherche des dirigeants
d'entreprises (via Pappers), enrichit leurs coordonnées (Dropcontact), valide
les emails (MillionVerifier), puis réalise un audit technique automatisé du site
web de chaque prospect (sécurité, UX/code, visuel) à l'aide de modèles de
langage (DeepInfra). La sortie est un fichier CSV de prospects qualifiés.

Pour le détail du fonctionnement, voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Prérequis

- Python 3.13+
- Un navigateur Chromium pour Crawl4AI (installé via Playwright)
- Poppler (conversion des captures PDF en image, utilisé par `pdf2image`)
  - macOS : `brew install poppler`
  - Debian/Ubuntu : `apt-get install poppler-utils`
- Clés API : Pappers, Dropcontact, MillionVerifier, DeepInfra
- MongoDB (optionnel ; le pipeline fonctionne sans, la persistance est alors
  désactivée)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # puis renseigner les clés
```

Renseignez au minimum dans `.env` :

```
PAPPERS_API_KEY=
DROPCONTACT_API_KEY=
MILLION_VERIFIER_API_KEY=
DEEPINFRA_API_KEY=
```

La liste complète des variables (dont les paramètres optionnels) est documentée
dans [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#configuration--variables-denvironnement).

## Usage

```bash
python main.py --limit 40 --mode code_naf
```

Arguments de `main.py` :

| Argument | Valeurs | Défaut | Rôle |
| --- | --- | --- | --- |
| `--limit` | entier | `TARGET_TOTAL` (settings) | Nombre de prospects visés |
| `--mode` | `code_naf`, `objet_social` | `code_naf` | Méthode de ciblage Pappers |
| `--debug` | drapeau | désactivé | Active les logs niveau DEBUG |

Le résultat est écrit dans `prospects_final_<timestamp>.csv` dans le répertoire
courant. Les codes NAF et départements ciblés se configurent dans
`src/config/settings.py`.

## Avertissement — usage responsable

Cet outil collecte et traite des données relatives à des personnes (dirigeants
d'entreprises) et effectue des tests techniques sur des sites web tiers. Son
usage engage votre responsabilité.

- **RGPD / prospection B2B** : la collecte et l'enrichissement de données de
  contact (noms, emails professionnels, profils LinkedIn) doivent respecter le
  RGPD et les règles de la CNIL sur la prospection B2B (base légale, information
  des personnes, droit d'opposition, minimisation et durée de conservation des
  données). Vous êtes responsable de traitement pour les données générées.
- **CGU des services tiers** : l'utilisation de Pappers, Dropcontact,
  MillionVerifier, DeepInfra, ainsi que le scraping via Crawl4AI et les requêtes
  vers DuckDuckGo, est soumise aux conditions d'utilisation de chaque service.
  Respectez leurs quotas, leurs limites de débit et leurs règles de scraping.
- **Audit de sécurité — périmètre** : le module `src/services/audit.py`, via
  `src/services/scraping.py` et `src/services/validator.py`, récupère le HTML et
  les scripts d'un site, puis `KeyValidator` détecte d'éventuelles clés API
  exposées et **envoie des requêtes de test vers les APIs tierces
  correspondantes** (Stripe, Google Maps, GitHub, etc.) pour vérifier si ces
  clés sont actives. Il ne s'agit pas d'un scan intrusif du serveur cible, mais
  l'émission de requêtes avec des secrets trouvés constitue un test actif. **Ne
  lancez l'audit que sur des sites que vous possédez ou pour lesquels vous avez
  l'autorisation explicite du propriétaire.** Tester des clés trouvées sur des
  sites tiers sans consentement peut être illégal selon les juridictions.

Cet outil est fourni à titre d'exemple ; utilisez-le de manière éthique et
conforme à la loi.

## Licence

[MIT](LICENSE)
