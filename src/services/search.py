import requests
from typing import Dict, Any, Optional, Callable, List, Tuple
from urllib.parse import urlparse, parse_qs, unquote, urlunparse
from bs4 import BeautifulSoup

WEBSITE_SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

WEBSITE_EXCLUDED_DOMAINS = (
    "linkedin.", "instagram.", "facebook.", "twitter.", "youtube.",
    "tiktok.", "viadeo.", "pinterest.", "medium.com",
)

def normalize_candidate_url(url: str) -> str:
    """Normalise une URL trouvée en ligne."""
    if not url:
        return ""

    if url.startswith("/"):
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            url = unquote(qs["uddg"][0])
        else:
            return ""

    url = unquote(url)
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if not domain or any(excluded in domain for excluded in WEBSITE_EXCLUDED_DOMAINS):
        return ""

    scheme = parsed.scheme if parsed.scheme in ("http", "https") else "https"
    normalized = urlunparse((scheme, domain, parsed.path.rstrip('/'), '', '', ''))
    return normalized

def find_website_online(query: str) -> str:
    """Recherche un site web sur DuckDuckGo."""
    if not query:
        return ""
    try:
        response = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query, "kl": "fr-fr"},
            headers=WEBSITE_SEARCH_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for link in soup.select("a.result__a")[:5]:
            candidate = normalize_candidate_url(link.get("href", ""))
            if candidate:
                return candidate
    except Exception:
        return ""
    return ""

def find_website_from_email_domain(prospect: Dict[str, Any], log_fn: Optional[Callable[[str, str], None]] = None) -> Dict[str, Any]:
    """Si le prospect n'a pas de website, tente de le trouver à partir du domaine de l'email."""
    website = prospect.get("website", "").strip()
    if website:
        return prospect

    email = prospect.get("email", "").strip()
    if not email or "@" not in email:
        return prospect

    domain = email.split("@")[1].lower()
    generic_domains = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "yahoo.fr",
                       "orange.fr", "free.fr", "wanadoo.fr", "laposte.net", "sfr.fr"]
    if domain in generic_domains:
        return prospect

    if log_fn:
        log_fn(f"🔍 {prospect.get('nom_complet', 'Inconnu')} - Recherche website depuis domaine: {domain}", "INFO")

    urls_to_test = [f"https://www.{domain}", f"https://{domain}"]
    for url in urls_to_test:
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if 200 <= response.status_code < 400:
                prospect["website"] = url
                if log_fn: log_fn(f"   ✅ Website trouvé: {url}", "INFO")
                return prospect
        except Exception:
            continue
    
    return prospect

def enrich_missing_websites(
    prospects: List[Dict[str, Any]],
    log_fn: Optional[Callable[[str, str], None]] = None,
) -> None:
    """Restauration fidèle de la logique d'enrichissement massif des sites web."""
    website_cache: Dict[Tuple[str, str], str] = {}
    for prospect in prospects:
        current = prospect.get("website", "").strip()
        if current:
            continue

        key = (
            prospect.get("nom_complet", "").lower(),
            prospect.get("entreprise_nom", "").lower(),
        )

        if key in website_cache:
            cached = website_cache[key]
            if cached: prospect["website"] = cached
            continue

        # 1. Tentative par domaine email d'abord (plus fiable et gratuit)
        find_website_from_email_domain(prospect, log_fn)
        if prospect.get("website"):
            website_cache[key] = prospect["website"]
            continue

        # 2. Tentative par recherche en ligne (DuckDuckGo)
        query_parts = []
        entreprise = prospect.get("entreprise_nom", "").strip()
        nom_complet = prospect.get("nom_complet", "").strip()
        if entreprise: query_parts.append(entreprise)
        if nom_complet and nom_complet.lower() not in entreprise.lower():
            query_parts.append(nom_complet)
        query_parts.append("site officiel")
        
        candidate = find_website_online(" ".join(query_parts))
        website_cache[key] = candidate
        if candidate:
            prospect["website"] = candidate
            if log_fn: log_fn(f"🌐 [Websites] Trouvé en ligne pour {entreprise}: {candidate}", "INFO")
