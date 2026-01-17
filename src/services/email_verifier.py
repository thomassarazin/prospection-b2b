import time
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
from src.core.retry import http_request_with_retry

def verify_email_realtime(
    email: str,
    api_key: str,
    timeout: int = 10,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> str:
    """
    Vérifie un email via Million Verifier Real-Time API

    Args:
        email: Email à vérifier
        api_key: Clé API Million Verifier
        timeout: Timeout en secondes (2-60, défaut 10)
        log_fn: Fonction de log optionnelle

    Returns:
        Result code: 'ok', 'catch_all', 'unknown', 'error', 'disposable', 'invalid'
    """
    if not email or not isinstance(email, str):
        if log_fn:
            log_fn(f"⚠️ [MillionVerifier] Email invalide: {email}", "WARNING")
        return "invalid"

    # Endpoint Real-Time API v3
    url = "https://api.millionverifier.com/api/v3/"
    params = {
        "api": api_key,
        "email": email.strip(),
        "timeout": min(max(timeout, 2), 60)  # Clamp entre 2 et 60
    }

    try:
        if log_fn:
            log_fn(f"🔍 [MillionVerifier] Vérification de {email}...", "DEBUG")

        # Pas de rate limiting car 160 req/sec (très permissif)
        resp = http_request_with_retry(
            "GET",
            url,
            params=params,
            timeout=timeout + 5,  # Un peu plus que le timeout API
            max_retries=2
        )

        if resp.status_code != 200:
            if log_fn:
                log_fn(f"❌ [MillionVerifier] Erreur HTTP {resp.status_code} pour {email}", "ERROR")
            return "error"

        data = resp.json()
        result = data.get("result", "error")

        if log_fn:
            log_fn(f"✅ [MillionVerifier] {email} → {result}", "DEBUG")

        return result

    except Exception as exc:
        if log_fn:
            log_fn(f"💥 [MillionVerifier] Exception pour {email}: {exc}", "ERROR")
        return "error"


def million_verifier_validate_batch(
    prospects: List[Dict[str, Any]],
    api_key: str,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Valide les emails d'un batch via Million Verifier Real-Time API
    Garde uniquement 'ok' et 'catch_all'

    Args:
        prospects: Liste de prospects avec emails
        api_key: Clé API Million Verifier
        log_fn: Fonction de log optionnelle

    Returns:
        (prospects_emails_valides, prospects_emails_invalides)
    """
    logger = logging.getLogger("prospection_pipeline")
    prospects_valides = []
    prospects_invalides = []

    if not prospects:
        return [], []

    if log_fn:
        log_fn(f"\n📧 [MillionVerifier] Validation de {len(prospects)} emails...", "INFO")

    validation_stats = {
        "ok": 0,
        "catch_all": 0,
        "invalid": 0,
        "disposable": 0,
        "unknown": 0,
        "error": 0
    }

    for prospect in prospects:
        # Extraire l'email (peut être une liste ou une string)
        email = None
        email_field = prospect.get("email", "")

        if isinstance(email_field, list) and email_field:
            first = email_field[0]
            if isinstance(first, dict):
                email = first.get("email", "")
            else:
                email = str(first)
        elif isinstance(email_field, str):
            email = email_field
        else:
            email = str(email_field) if email_field else ""

        email = email.strip()

        if not email:
            prospect["million_verifier_result"] = "no_email"
            prospect["motif_exclusion"] = "email manquant"
            prospects_invalides.append(prospect)
            if log_fn:
                log_fn(f"   ⚠️ {prospect.get('nom_complet', 'Inconnu')} - Pas d'email", "WARNING")
            continue

        # ⭐ IMPORTANT: Normaliser le champ email pour le CSV (remplacer liste/dict par string simple)
        prospect["email"] = email

        # Vérification via API
        result = verify_email_realtime(email, api_key, timeout=10, log_fn=None)
        prospect["million_verifier_result"] = result

        # Comptabiliser
        validation_stats[result] = validation_stats.get(result, 0) + 1

        # Filtrage : on garde seulement 'ok' et 'catch_all'
        if result in ["ok", "catch_all"]:
            prospects_valides.append(prospect)
            if log_fn:
                emoji = "✅" if result == "ok" else "⚠️"
                log_fn(
                    f"   {emoji} {prospect.get('nom_complet', 'Inconnu')} ({email}) - {result.upper()}",
                    "INFO"
                )
        else:
            prospect["motif_exclusion"] = f"email_{result}"
            prospects_invalides.append(prospect)
            if log_fn:
                log_fn(
                    f"   ❌ {prospect.get('nom_complet', 'Inconnu')} ({email}) - {result.upper()} (rejeté)",
                    "WARNING"
                )

        # Petit délai pour respecter le rate limit (160/sec = ~6ms, on met 10ms par sécurité)
        time.sleep(0.01)

    # Logs de synthèse
    if log_fn:
        log_fn(f"\n📊 [MillionVerifier] Résultats de validation:", "INFO")
        log_fn(f"   ✅ OK: {validation_stats['ok']}", "INFO")
        log_fn(f"   ⚠️ CATCH-ALL: {validation_stats['catch_all']}", "INFO")
        log_fn(f"   ❌ INVALID: {validation_stats['invalid']}", "WARNING")
        log_fn(f"   ❌ DISPOSABLE: {validation_stats['disposable']}", "WARNING")
        log_fn(f"   ⚠️ UNKNOWN: {validation_stats['unknown']}", "WARNING")
        log_fn(f"   ❌ ERROR: {validation_stats['error']}", "ERROR")
        log_fn(f"   📈 TAUX DE VALIDITÉ: {len(prospects_valides)}/{len(prospects)} ({len(prospects_valides)*100//len(prospects) if prospects else 0}%)", "INFO")

    return prospects_valides, prospects_invalides
