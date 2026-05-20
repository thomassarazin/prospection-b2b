# 🎯 Advanced B2B Audit & Prospecting Platform

> **L'ultime plateforme multi-agents** pour la prospection B2B de précision et l'audit technique automatisé (Sécurité, UX, Vision).

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![DeepInfra](https://img.shields.io/badge/AI-DeepInfra-purple.svg)](https://deepinfra.com/)
[![Crawl4AI](https://img.shields.io/badge/Scraping-Crawl4AI--v2-green.svg)](https://crawl4ai.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🔥 Le Concept : L'Audit comme cheval de Troie

Ce pipeline ne se contente pas de trouver des entreprises. Il effectue un **audit technique complet** pour transformer chaque prise de contact en une démonstration d'expertise. Plus besoin de "icebreakers" génériques : vous contactez le prospect avec des failles réelles et des preuves visuelles.

### 1. 🏢 Pipeline de Prospection PME
- 📊 **Segmentation Précise** : Ciblage par code NAF et localisation via Pappers.
- 📧 **Enrichissement Cascade** : Détection d'emails pro (Dropcontact) et découverte de sites web.
- 📑 **Rapports Humains** : Conversion automatique des analyses IA complexes en blocs de texte lisibles pour vos commerciaux (CSV direct).

### 2. 🔍 Audit IA Multi-Experts
- 🛡️ **Expert Sécurité** : Scan approfondi du code HTML et des scripts pour détecter les fuites de versions, les clés API exposées et les failles de headers.
- 🎨 **Expert UX/Code** : Analyse critique de l'accessibilité, de l'hygiène du code et du responsive design.
- 👁️ **Expert Vision (Full-Page)** : Analyse esthétique basée sur une capture complète de la page (du header au footer), évaluant la hiérarchie visuelle et l'impact des CTAs.
- 🧠 **La Synthèse (Mentor)** : Rassemble les points critiques, définit un score de priorité client et génère un **script d'appel téléphonique** ultra-personnalisé.

---

## 🚀 Technologie utilisée

### 🕵️‍♂️ Smart Discovery & Multi-Pages
Le système ne s'arrête pas à la page d'accueil. Il explore intelligemment les pages `/contact` ou `/login` pour agréger un maximum de scripts JavaScript, augmentant ainsi drastiquement la portée de l'audit de sécurité.

### 🔑 KeyValidator Hybride
Un moteur de détection unique qui combine :
- **Scan de scripts externes** (JS Hunter).
- **Scan d'attributs HTML** et de variables inline.
- **Validation Active** : Chaque clé trouvée est testée en temps réel sur les APIs de 45+ services (Stripe, AWS, Google Maps...) pour confirmer si elle est "exploitable" ou non.

### 📸 Vision Vision 1920px
Capture HD via moteur Chromium convertie en JPEG optimisé. L'IA Vision (Qwen-VL) dispose d'une vue d'acteur de l'ensemble du site web, permettant un diagnostic visuel sans angle mort.

---

## 🛠️ Installation

### Prérequis
- **Poppler** (indispensable pour la conversion des captures full-page) :
  ```bash
  brew install poppler  # macOS
  ```

### Setup
```bash
git clone https://github.com/toot7b/Projet-Freelance.git
cd Projet-Freelance
pip install -r requirements.txt
playwright install
cp .env.example .env # Remplir vos clés API
```

---

## 💻 Usage

### � Lancer la prospection massive
```bash
python main.py --limit 40 --mode code_naf
```

### 🔍 Lancer un audit unitaire (Démo)
```bash
python tests/test_full_audit.py www.example.com
```

---

**Propulsion commerciale par l'intelligence technique. 🚀**
