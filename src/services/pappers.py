import time
import logging
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from src.core.rate_limiter import RateLimiter
from src.core.retry import http_request_with_retry
from src.config.settings import PAPPERS_API_KEY

# Instance locale du rate limiter
_rate_limiter = RateLimiter()

def collect_dirigeants_for_strategy(
    strategy: Dict[str, Any],
    siren_exclus: Set[str],
    pappers_filters: Dict[str, Any],
    pappers_headers: Dict[str, str],
    log_fn: Optional[Callable[[str, str], None]] = None,
    segment_name: str = "PME",
    page_number: int = 1,
    curseur: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], int, int, Optional[str]]:
    """
    Collecte les dirigeants via l'API Pappers (endpoint /recherche-dirigeants).
    
    Supporte:
    - Pagination classique ou curseurs (>400 résultats)
    - Filtrage par code NAF ou objet social
    - Filtrage des SIREN exclus
    - Extraction des entreprises pertinentes pour le dirigeant

    Returns:
        Tuple[dirigeants, nb_api_calls, nb_avant_filtrage, curseur_suivant]
    """
    logger = logging.getLogger("prospection_pipeline")
    api_calls = 0
    objet_social = strategy.get("objet_social")
    code_naf = strategy.get("code_naf")
    par_page = strategy.get("par_page", 20)
    nom_strategy = strategy.get("nom", "Unknown Strategy")

    # Ensemble des codes NAF recherchés (pour filtrage rapide)
    codes_naf_recherches = set(code_naf.split(",")) if code_naf else None

    # Base params
    base_params = {
        "api_token": PAPPERS_API_KEY,
        "type_dirigeant": "physique",  # Filtre personnes physiques uniquement
        **pappers_filters,
    }

    # Choix pagination vs curseurs
    if curseur is not None:
        # MODE CURSEUR: Pour >400 résultats
        base_params["curseur"] = curseur
        base_params["par_curseur"] = min(par_page, 1000)  # Max 1000 par curseur
        pagination_info = f"curseur {curseur[:20]}..." if curseur != "*" else "curseur initial (*)"
    else:
        # MODE PAGE: Pagination classique (<400 résultats)
        base_params["par_page"] = par_page
        base_params["page"] = page_number
        pagination_info = f"page {page_number}"

    if code_naf:
        params = {**base_params, "code_naf": code_naf}
        logger.info(f"🔍 [Pappers] Recherche CODE NAF '{code_naf}' ({pagination_info})...")
    elif objet_social:
        params = {**base_params, "objet_social": objet_social}
        logger.info(f"🔍 [Pappers] Recherche objet social '{objet_social}' ({pagination_info})...")
    else:
        logger.error("❌ Stratégie invalide: ni 'objet_social' ni 'code_naf' défini")
        return [], 0, 0, None

    try:
        # Log adapté selon le mode
        search_term = code_naf if code_naf else objet_social
        debug_start = time.time()
        api_calls += 1
        logger.debug(f"📞 [DEBUG] APPEL API #{api_calls}: RECHERCHE-DIRIGEANTS '{search_term}'")

        _rate_limiter.wait_if_needed("pappers")
        resp = http_request_with_retry(
            "GET",
            "https://api.pappers.fr/v2/recherche-dirigeants",
            params=params,
            headers=pappers_headers
        )
        debug_end = time.time()
        logger.debug(
            f"📡 [DEBUG] RECHERCHE-DIRIGEANTS API: {resp.status_code} - {debug_end - debug_start:.2f}s"
        )

        if resp.status_code != 200:
            if resp.status_code in [401, 402, 403]:
                error_msg = resp.text[:200] if resp.text else "Pas de détails"
                logger.error(
                    f"🚫 [PAPPERS] QUOTA ÉPUISÉ OU ACCÈS REFUSÉ (code {resp.status_code})\n"
                    f"   Message API: {error_msg}\n"
                    f"   ⚠️ Vérifiez vos crédits Pappers restants"
                )
                raise Exception(f"PAPPERS_QUOTA_EXCEEDED: Code {resp.status_code} - {error_msg}")

            logger.error(f"❌ [{segment_name}] Erreur recherche dirigeants {nom_strategy}: {resp.status_code}")
            return [], api_calls, 0, None

        data = resp.json()
        resultats_dirigeants = data.get("resultats", [])
        curseur_suivant = data.get("curseurSuivant")
        logger.info(f"📊 [Pappers] {len(resultats_dirigeants)} dirigeants trouvés pour '{search_term}'")

    except Exception as exc:
        logger.error(f"💥 [{segment_name}] Exception recherche dirigeants {nom_strategy}: {exc}")
        return [], api_calls, 0, None

    # TRAITEMENT DES RÉSULTATS
    dirigeants: List[Dict[str, Any]] = []
    
    # Debug stats
    debug_stats = {
        "total_entreprises": 0,
        "rejet_siren_deja_traite": 0,
        "rejet_code_naf_non_matchant": 0,
        "collectes": 0,
        "codes_naf_trouves": set()
    }

    for dirigeant_data in resultats_dirigeants:
        # Vérifier que c'est bien une personne physique
        if dirigeant_data.get("personne_morale", False):
            continue

        prenom = dirigeant_data.get("prenom", "")
        nom = dirigeant_data.get("nom", "")
        nom_complet = dirigeant_data.get("nom_complet", f"{prenom} {nom}")
        qualite = dirigeant_data.get("qualite", "")
        qualites = dirigeant_data.get("qualites", [])

        if not prenom or not nom:
            continue

        # Filtrer commissaires aux comptes
        if qualite and "commissaire" in qualite.lower():
            continue
        if any("commissaire" in q.lower() for q in qualites):
            continue

        entreprises = dirigeant_data.get("entreprises", [])
        if not entreprises:
            continue

        for entreprise in entreprises:
            debug_stats["total_entreprises"] += 1
            siren = entreprise.get("siren", "")
            entreprise_nom = entreprise.get("denomination", "") or entreprise.get("nom_entreprise", "N/A")

            # Check SIREN exclus
            if not siren or siren in siren_exclus:
                if siren and siren in siren_exclus:
                    debug_stats["rejet_siren_deja_traite"] += 1
                continue

            # FILTRE CODE NAF
            if codes_naf_recherches:
                entreprise_code_naf = entreprise.get("code_naf", "")
                entreprise_code_naf_normalise = str(entreprise_code_naf or "").replace(".", "")
                debug_stats["codes_naf_trouves"].add(entreprise_code_naf)

                if entreprise_code_naf_normalise not in codes_naf_recherches:
                    debug_stats["rejet_code_naf_non_matchant"] += 1
                    if log_fn:
                        log_fn(f"         ⏭️ Skip {entreprise_nom} - Code NAF {entreprise_code_naf} non matchant (Voulus: {codes_naf_recherches})", "DEBUG")
                    continue

            debug_stats["collectes"] += 1
            siege = entreprise.get("siege", {})

            logger.info(f"         ✅ Dirigeant: {nom_complet} ({qualite}) - {entreprise_nom}")

            dirigeants.append({
                "prenom": prenom,
                "nom": nom,
                "nom_complet": nom_complet,
                "qualite": qualite,
                "entreprise_nom": entreprise_nom,
                "siren": siren,
                "forme_juridique": entreprise.get("forme_juridique", ""),
                "effectif": entreprise.get("effectif", ""),
                "code_naf": entreprise.get("code_naf", ""),
                "secteur_activite": entreprise.get("libelle_code_naf", ""),
                "date_creation": entreprise.get("date_creation", ""),
                "localisation": f"{siege.get('ville', '')}, {siege.get('code_postal', '')}",
            })
            siren_exclus.add(siren)

    logger.info(f"✅ [{segment_name}] {len(dirigeants)} dirigeants collectés avec {api_calls} appel(s) API")

    return dirigeants, api_calls, len(resultats_dirigeants), curseur_suivant
