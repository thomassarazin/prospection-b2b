# 🚀 Smart Prospecting Pipeline & Expert Audit Engine

Un moteur de prospection B2B modulaire conçu pour passer de la prospection de masse à une approche haute-fidélité.

## ✨ Fonctionnalités clés

- 🔍 **Multi-Source Discovery** : Intégration avancée avec Pappers API pour un ciblage précis par code NAF et localisation.
- 📧 **Smart Enrichment** : Batch processing via Dropcontact pour l'extraction des contacts directs des décideurs.
- 🌐 **Deep Web Scraping** : Analyse haute performance via Crawl4AI (Cleaned HTML & Screenshots).
- 🤖 **AI-Driven Personalization** : Génération d'icebreakers et d'automatisations sur-mesure via DeepInfra (Qwen/Llama).
- 🛡️ **Expert Audit (Beta)** : Diagnostic automatique des failles UI et Sécurité pour des arguments de vente à forte valeur ajoutée.

## 🛠️ Stack Technique

- **Langage** : Python 3.12+
- **Scraping** : Crawl4AI
- **IA** : DeepInfra (Llama 3 / Qwen)
- **APIs** : Pappers, Dropcontact, Million Verifier

## 🚀 Installation & Usage

1. **Cloner le projet**
   ```bash
   git clone https://github.com/toot7b/prospection-v1.git
   cd prospection-v1
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

3. **Configuration**
   Copiez le fichier `.env.example` en `.env` et remplissez vos clés API.

4. **Lancer la prospection**
   ```bash
   python main.py --limit 10 --debug
   ```

---
*Projet développé pour optimiser la qualité et la pertinence de la prospection B2B.*
