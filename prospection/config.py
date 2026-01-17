#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuration centralisée pour le pipeline de prospection."""

import os

# =============================================================================
# CONFIGURATION DES TARGETS
# =============================================================================

# Total de prospects souhaités
TARGET_TOTAL = 100

# Répartition par segment (en pourcentages)
REPARTITION = {
    "pme": 0.25,                      # 25% - Prospects PME (25 prospects)
    "freelance_b2b_premium": 0.25,    # 25% - Freelances B2B premium (25 prospects)
    "studios": 0.25,                  # 25% - Studios créatifs via Instagram (25 prospects)
    "locales": 0.25                   # 25% - Petites marques locales via Google Maps (25 prospects)
}

# Calcul automatique des targets par segment
TARGETS_CONFIG = {
    segment: int(TARGET_TOTAL * ratio)
    for segment, ratio in REPARTITION.items()
}

# =============================================================================
# CLÉS API
# =============================================================================

# Apollo (optionnel)
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "***REMOVED***")

# Apify (Instagram/LinkedIn)
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "***REMOVED***")
APIFY_INSTAGRAM_HASHTAG_ACTOR = os.getenv("APIFY_INSTAGRAM_HASHTAG_ACTOR", "apify/instagram-hashtag-scraper")
APIFY_INSTAGRAM_PROFILE_ACTOR = os.getenv("APIFY_INSTAGRAM_PROFILE_ACTOR", "apify/instagram-profile-scraper")
APIFY_LINKEDIN_ACTOR_ID = os.getenv("APIFY_LINKEDIN_ACTOR_ID", "")

# Configuration du cache persistant Apify
APIFY_CACHE_ENABLED = os.getenv("APIFY_CACHE_ENABLED", "true").lower() == "true"
APIFY_CACHE_FILE = os.getenv("APIFY_CACHE_FILE", "cache_usernames_apify.json")
APIFY_CACHE_MAX_AGE_DAYS = int(os.getenv("APIFY_CACHE_MAX_AGE_DAYS", "90"))

# Pappers (données SIRENE)
PAPPERS_API_KEY = os.getenv("PAPPERS_API_KEY", "***REMOVED***")

# Dropcontact (enrichissement email/LinkedIn)
DROPCONTACT_API_KEY = os.getenv("DROPCONTACT_API_KEY", "***REMOVED***")
DROPCONTACT_BATCH_SIZE_DEFAULT = int(os.getenv("DROPCONTACT_BATCH_SIZE", "10"))
DROPCONTACT_BATCH_SIZE_MIN = int(os.getenv("DROPCONTACT_BATCH_SIZE_MIN", "3"))
DROPCONTACT_BATCH_SIZE_MAX = int(os.getenv("DROPCONTACT_BATCH_SIZE_MAX", "100"))

# =============================================================================
# CONFIGURATION PAR SEGMENT
# =============================================================================

PME_TARGET_DEFAULT = int(os.getenv("PME_TARGET_DEFAULT", "40"))
FREELANCE_TARGET_DEFAULT = int(os.getenv("FREELANCE_TARGET_DEFAULT", "30"))

# =============================================================================
# CONFIGURATION ENRICHISSEMENT WEB
# =============================================================================

WEBSITE_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

WEBSITE_EXCLUDED_DOMAINS = (
    "linkedin.",
    "instagram.",
    "facebook.",
    "twitter.",
    "youtube.",
    "tiktok.",
    "viadeo.",
    "pinterest.",
    "medium.com",
)
