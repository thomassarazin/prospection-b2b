"""Utilitaires de traitement de texte et quality gates."""
import re
from typing import Tuple

SPECIAL_ERROR_PATTERNS = (
    "domain is not connected",
    "domain not connected",
    "connect your domain",
    "domaine n'est pas connecté",
    "ce domaine n'est pas connecté",
    "aucun site n'est encore associé",
    "enable javascript",
    "javascript doit être activé",
    "please turn on javascript",
    "account suspended",
    "site unavailable",
    "site indisponible",
    "site not found",
)

ICEBREAKER_SUSPICIOUS_KEYWORDS = (
    "cookie",
    "cookies",
    "subscription",
    "javascript",
    "connexion",
    "login",
    "rgpd",
    "privacy",
)

def clean_text(text: str) -> str:
    """Nettoie une chaîne de caractères basique."""
    if not text:
        return ""
    return text.strip()

def clean_scraped_markdown(raw_markdown: str) -> str:
    """Nettoie le Markdown (URLs, titres vides) pour conserver un texte exploitable."""
    if not raw_markdown:
        return raw_markdown

    text = raw_markdown
    # Supprimer les URLs
    text = re.sub(r"https?://\S+", " ", text)
    # Supprimer les ancres/balises Markdown (#, ##, etc.) redondantes
    text = re.sub(r"#+\s*", " ", text)
    # Supprimer les répétitions de points ou symboles
    text = re.sub(r"[•·▪►]+", " ", text)
    # Réduire espaces multiples
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def evaluate_content_quality(text: str, min_chars: int = 0) -> Tuple[bool, str]:
    """
    Détecte le contenu bruité (cookies, erreurs Wix, etc.).

    Args:
        text: Contenu à évaluer
        min_chars: Longueur minimale pour considérer le contenu comme fiable

    Returns:
        Tuple (is_valid, reason)
    """
    if not text or not text.strip():
        return False, "contenu vide"

    normalized = text.strip().lower()
    if any(pattern in normalized for pattern in SPECIAL_ERROR_PATTERNS):
        return False, "message d'erreur détecté (Wix / JS / domaine)"

    cookie_mentions = normalized.count("cookie")
    privacy_mentions = normalized.count("privacy") + normalized.count("rgpd")
    if cookie_mentions >= 8 or (cookie_mentions >= 4 and privacy_mentions >= 2):
        return False, "page cookies/consentement détectée"

    if min_chars > 0 and len(text) < min_chars:
        return False, f"contenu trop court ({len(text)} < {min_chars})"

    return True, ""

def contains_suspicious_keyword(value: str) -> bool:
    """Détecte si la variable (A/B/C) contient un mot-clé technique aberrant."""
    if not value:
        return False
    value_lower = value.lower()
    return any(keyword in value_lower for keyword in ICEBREAKER_SUSPICIOUS_KEYWORDS)
