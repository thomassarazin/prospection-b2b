import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# API KEYS & EXTERNAL SERVICES Configuration
# =============================================================================
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

# Services IA & Scraping
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
DEEPINFRA_MODEL = os.getenv("DEEPINFRA_MODEL", "Qwen/Qwen3-235B-A22B-Instruct-2507")
DEEPINFRA_URL = os.getenv("DEEPINFRA_URL", "https://api.deepinfra.com/v1/openai/chat/completions")

# Services Enrichissement
PAPPERS_API_KEY = os.getenv("PAPPERS_API_KEY")
DROPCONTACT_API_KEY = os.getenv("DROPCONTACT_API_KEY")
MILLION_VERIFIER_API_KEY = os.getenv("MILLION_VERIFIER_API_KEY")

# Configuration Crawl4AI
CRAWL_ALLOW_NOISY = os.getenv("CRAWL_ALLOW_NOISY", "true").lower() == "true"
DEFAULT_CRAWL4AI_BASE = os.path.join(os.getcwd(), ".crawl4ai_cache")
os.makedirs(DEFAULT_CRAWL4AI_BASE, exist_ok=True)
os.environ.setdefault("CRAWL4_AI_BASE_DIRECTORY", DEFAULT_CRAWL4AI_BASE)

# =============================================================================
# PROSPECTION CONFIGURATION (PME FOCUSED)
# =============================================================================

# Total de prospects souhaités par défaut
TARGET_TOTAL = 50

# Mode de prospection : "code_naf" (ciblé) ou "objet_social" (large)
MODE_PROSPECTION = os.getenv("MODE_PROSPECTION", "code_naf")

# Configuration campagne Code NAF
CAMPAGNE_CODES_NAF = {
    "actif": MODE_PROSPECTION == "code_naf",
    "codes": [
        "7022Z",  # Conseil pour les affaires et autres conseils de gestion
    ]
}

# Départements ciblés pour la segmentation (Mode NAF)
# Permet de contourner la limite de 400 résultats par appel Pappers
PME_SEARCH_DEPARTMENTS = ["75", "77", "78", "91", "92", "93", "94", "95", "69"]

# Répartition par segment (en pourcentages)
REPARTITION = {
    "pme": 1.0,         # 100% PME
    "studios": 0.0,     # 0% Studios (désactivé)
    "locales": 0.0      # 0% Locales (désactivé)
}

# Calcul automatique des targets par segment
TARGETS_CONFIG = {
    segment: int(TARGET_TOTAL * ratio)
    for segment, ratio in REPARTITION.items()
}

# Limites Système
LIMIT_MEMORY_MB = int(os.getenv("LIMIT_MEMORY_MB", "512"))

# Fichiers de données et Caches
RESERVOIR_PME_CSV = os.getenv("RESERVOIR_PME_CSV", "reservoir_pme.csv")
RESERVOIR_FILTRE_CACHE = os.getenv("RESERVOIR_FILTRE_CACHE", "reservoir_filtre_pme.json")
STRATEGIES_CACHE_FILE = os.getenv("STRATEGIES_CACHE_FILE", "strategies_testees_cache.json")
PAGINATION_NAF_FILE = os.getenv("PAGINATION_NAF_FILE", "pagination_codes_naf.json")
CHECKPOINT_DIR = "checkpoints"

# Limites API & Services
PAPPERS_MAX_PAGES = int(os.getenv("PAPPERS_MAX_PAGES", "4"))
PAPPERS_MAX_RESULTS = int(os.getenv("PAPPERS_MAX_RESULTS", "400"))
DROPCONTACT_BATCH_SIZE_MAX = int(os.getenv("DROPCONTACT_BATCH_SIZE_MAX", "100"))
DROPCONTACT_OVERSAMPLE = int(os.getenv("DROPCONTACT_OVERSAMPLE", "1"))

# Headers pour requêtes web (simples)
WEBSITE_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}
