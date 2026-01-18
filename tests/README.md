# 🧪 Scripts de Test

Ce dossier contient tous les scripts de test et de vérification pour le pipeline de prospection.

## 📋 Script Principal

### `check_credits.py` ⭐
**Script de vérification des crédits avant lancement**
- Vérifie les crédits Dropcontact restants
- Teste la connexion à Pappers
- Demande confirmation avant de lancer le pipeline
- **Utilisation recommandée** : `python3 tests/check_credits.py`

---

## 🔍 Tests API

### `test_deepinfra.py`
Test de base de l'API DeepInfra avec le modèle Qwen3-235B

### `test_deepinfra_pipeline.py`
Test complet du pipeline DeepInfra (3 prompts : résumé, extraction A/B/C, automatisations)

### `test_deepinfra_timeout.py`
Mesure du temps de génération DeepInfra pour ajuster les timeouts

### `test_dropcontact.py`
Test de l'API Dropcontact et vérification des crédits

### `test_dropcontact_batch.py`
Test d'enrichissement par batch Dropcontact

### `test_dropcontact_simple.py`
Test simple d'un enrichissement Dropcontact

### `test_pappers_api.py`
Test de l'API Pappers (recherche entreprises, dirigeants)

### `test_pappers_code_naf.py`
Test de recherche Pappers par code NAF

### `test_pappers_total.py`
Test du nombre total d'entreprises disponibles sur Pappers

### `test_pappers_structure_dirigeant.py`
Test de la structure des données dirigeants retournées par Pappers

---

## 🌐 Tests Scraping

### `test_crawl4ai_groq.py`
Test de scraping avec Crawl4AI + extraction LLM Groq

### `test_deep_crawl.py`
Test de scraping approfondi

### `test_apify_bio.py`
Test d'extraction de bio Instagram via Apify

---

## 📊 Tests Techniques

### `test_curseurs_pappers.py`
Test du système de curseurs de pagination Pappers

### `test_pagination_code_naf.py`
Test de la pagination multi-NAF

### `test_groq_extraction.py`
Test d'extraction de variables avec Groq

---

## 💡 Utilisation

Pour vérifier l'état avant de lancer une campagne :
```bash
python3 tests/check_credits.py
```

Pour tester un composant spécifique :
```bash
python3 tests/test_deepinfra_pipeline.py
python3 tests/test_dropcontact.py
```
