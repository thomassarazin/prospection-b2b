"""Utilitaires pour le web (URLs, Domaines)."""
from urllib.parse import urlparse

def extract_domain(url: str) -> str:
    """Extrait le domaine d'une URL."""
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path
