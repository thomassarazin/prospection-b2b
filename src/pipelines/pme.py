import os
import json
import time
import random
import logging
import pandas as pd
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import asdict

from src.models.prospect import UnifiedProspect
from src.config.settings import (
    PAPPERS_API_KEY, DROPCONTACT_API_KEY, MILLION_VERIFIER_API_KEY, DEEPINFRA_API_KEY,
    MODE_PROSPECTION, CAMPAGNE_CODES_NAF, TARGETS_CONFIG,
    RESERVOIR_PME_CSV, RESERVOIR_FILTRE_CACHE, STRATEGIES_CACHE_FILE,
    PAGINATION_NAF_FILE, PAPPERS_MAX_PAGES, LIMIT_MEMORY_MB, PME_SEARCH_DEPARTMENTS
)
from src.core.checkpoint import CheckpointManager
from src.services.pappers import collect_dirigeants_for_strategy
from src.services.dropcontact import dropcontact_enrich_loop
from src.services.search import find_website_from_email_domain, enrich_missing_websites
from src.services.email_verifier import million_verifier_validate_batch
from src.services.scraping import scrape_website_with_crawl4ai
from src.services.deepinfra import (
    extract_detailed_summary_with_deepinfra,
    extract_abc_from_summary_with_deepinfra,
    generate_automation_list_with_deepinfra,
    try_metadata_fallback
)

# Instance locale du checkpoint manager (sera initialisée via settings dans une vraie app, ici on peut la recréer)
_checkpoint_manager = CheckpointManager()

# ---------------------------------------------------------------------------
# Configuration & Constantes
# ---------------------------------------------------------------------------

PME_TARGET_DEFAULT = int(os.getenv("PME_TARGET_DEFAULT", "40"))

PME_FILTERS = {
    "categorie_juridique": "5499,5720,5498,1000,5710",  # SARL, SASU, EURL, EI, SAS
    "tranche_effectif_min": "02",  # 3-5 salariés minimum
    "tranche_effectif_max": "12",  # 20-49 salariés maximum
    "date_creation_min": f"01-01-{datetime.now().year - 7}",  # 7 ans max
    "date_creation_max": f"31-12-{datetime.now().year - 2}",  # 2 ans min
    "departement": "75",  # Par défaut Paris (sera surchargé en segmentation)
    "entreprise_cessee": "false",
}

# Mapping NAF -> Secteur (pour CSV simplifié)
NAF_TO_SECTOR = {
    # Communication & Marketing
    "7021Z": "Conseil en relations publiques et communication",
    "7311Z": "Activités des agences de publicité",
    "7312Z": "Régie publicitaire de médias",
    "7320Z": "Études de marché et sondages",
    "7410Z": "Activités spécialisées de design",
    "7420Z": "Activités photographiques",
    "9001Z": "Arts du spectacle vivant",
    "9003A": "Création artistique relevant des arts plastiques",
    "7430Z": "Traduction et interprétation",
    "6391Z": "Activités des agences de presse",
    "5819Z": "Autres activités d'édition",

    # Conseil B2B
    "7022Z": "Conseil pour les affaires et autres conseils de gestion",
    "7010Z": "Activités des sièges sociaux",
    "7020Z": "Activités des sociétés holding",
    "6920Z": "Activités comptables",
    "6619B": "Autres activités auxiliaires de services financiers",
    "6622Z": "Activités des agents et courtiers d'assurances",
    "6630Z": "Gestion de fonds",
    "7490A": "Activité des économistes de la construction",
    "7490B": "Activités spécialisées, scientifiques et techniques diverses",
    "7120B": "Analyses, essais et inspections techniques",
    "6202A": "Conseil en systèmes et logiciels informatiques",
    "6311Z": "Traitement de données, hébergement et activités connexes",

    # Formation & Coaching
    "8559A": "Formation continue d'adultes",
    "8559B": "Autres enseignements",
    "8560Z": "Activités de soutien à l'enseignement",
    "8551Z": "Enseignement de disciplines sportives et d'activités de loisirs",
    "8532Z": "Enseignement secondaire technique ou professionnel",
    "8542Z": "Enseignement supérieur",
    "9604Z": "Entretien corporel",

    # Événementiel
    "8230Z": "Organisation de foires, salons professionnels et congrès",
    "9329Z": "Autres activités récréatives et de loisirs",
    "9002Z": "Activités de soutien au spectacle vivant",
    "9003B": "Autre création artistique",
    "5610A": "Restauration traditionnelle",
    "5621Z": "Services des traiteurs",
    "7739Z": "Location et location-bail d'autres machines",
    "7729Z": "Location et location-bail d'autres biens personnels et domestiques",

    # Commerce & E-commerce
    "4791A": "Vente à distance sur catalogue général",
    "4791B": "Vente à distance sur catalogue spécialisé",
    "4719B": "Autres commerces de détail en magasin non spécialisé",
    "4771Z": "Commerce de détail d'habillement en magasin spécialisé",
    "4772A": "Commerce de détail de la chaussure",
    "4773Z": "Commerce de détail de produits pharmaceutiques en magasin spécialisé",
    "4775Z": "Commerce de détail de parfumerie et de produits de beauté",
    "4776Z": "Commerce de détail de fleurs, plantes, graines",
    "4778C": "Autres commerces de détail spécialisés divers",
    "4779Z": "Commerce de détail de biens d'occasion en magasin",
    "4781Z": "Commerce de détail alimentaire sur éventaires et marchés",
    "4782Z": "Commerce de détail de textiles, d'habillement et de chaussures",
    "4789Z": "Autres commerces de détail sur éventaires et marchés",
    "4799A": "Vente à domicile",
    "4799B": "Vente par automates et autres commerces de détail hors magasin",
    "4759A": "Commerce de détail de meubles",
    "4759B": "Commerce de détail d'autres équipements du foyer",
    "4751Z": "Commerce de détail de textiles en magasin spécialisé",
    "4752A": "Commerce de détail de quincaillerie, peintures et verres",
    "4752B": "Commerce de détail de bricolage",
    "4753Z": "Commerce de détail de tapis, moquettes et revêtements de murs",
    "4754Z": "Commerce de détail d'appareils électroménagers",

    # Immobilier
    "6831Z": "Agences immobilières",
    "6832A": "Administration d'immeubles et autres biens immobiliers",
    "6832B": "Supports juridiques de gestion de patrimoine immobilier",
    "6810Z": "Activités des marchands de biens immobiliers",
    "6820A": "Location de logements",
    "6820B": "Location de terrains et d'autres biens immobiliers",
    "4110A": "Promotion immobilière de logements",
    "4110B": "Promotion immobilière de bureaux",
    "4110C": "Promotion immobilière d'autres bâtiments",
    "4110D": "Supports juridiques de programmes",

    # RH & Recrutement
    "7810Z": "Activités des agences de placement de main-d'œuvre",
    "7820Z": "Activités des agences de travail temporaire",
    "7830Z": "Autre mise à disposition de ressources humaines",
}

# ---------------------------------------------------------------------------
# Helpers du Réservoir Intelligent
# ---------------------------------------------------------------------------

def calculer_params_reservoir(target_count: int) -> Dict[str, int]:
    """Calcule les paramètres du réservoir selon l'objectif"""
    if target_count <= 10:
        return {"MAX_PAGES_RESERVOIR": 1, "SEUIL_RECHARGE": 5, "BATCH_SIZE": 10}
    elif target_count <= 30:
        return {"MAX_PAGES_RESERVOIR": 2, "SEUIL_RECHARGE": 10, "BATCH_SIZE": 20}
    else:
        return {"MAX_PAGES_RESERVOIR": 3, "SEUIL_RECHARGE": 15, "BATCH_SIZE": 30}

def calculer_cap_reservoir(target_count: int) -> int:
    """Calcule le cap mémoire du réservoir selon l'objectif."""
    if target_count <= 5:
        return max(15, target_count * 3)  # Très petit volume : 3x l'objectif (min 15)
    elif target_count <= 10:
        return 30     # Petit volume
    elif target_count <= 50:
        return 100    # Volume moyen
    else:
        return 300    # Gros volume

def charger_reservoir_pme_csv() -> List[Dict[str, Any]]:
    """Charge l'historique de tous les prospects PME bruts collectés (persistent storage)"""
    if os.path.exists(RESERVOIR_PME_CSV):
        try:
            df = pd.read_csv(RESERVOIR_PME_CSV)
            return df.to_dict('records')
        except Exception as e:
            logging.getLogger("prospection_pipeline").warning(f"⚠️ Erreur lecture CSV réservoir persistant: {e}")
            return []
    return []

def sauvegarder_reservoir_pme_csv(prospects: List[Dict[str, Any]]) -> None:
    """Sauvegarde les prospects bruts (non filtrés) pour historique"""
    try:
        df = pd.DataFrame(prospects)
        df.to_csv(RESERVOIR_PME_CSV, index=False, encoding='utf-8')
    except Exception as e:
        logging.getLogger("prospection_pipeline").error(f"❌ Erreur sauvegarde CSV réservoir persistant: {e}")

def charger_reservoir_filtre_cache(code_naf: str = None) -> List[Dict[str, Any]]:
    """Charge le cache temporaire des prospects VALIDES mais non utilisés dans le run précédent"""
    cache_file = f"reservoir_filtre_{code_naf}.json" if code_naf else "reservoir_filtre_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def sauvegarder_reservoir_filtre_cache(prospects: List[Dict[str, Any]], code_naf: str = None) -> None:
    """Sauvegarde le cache temporaire pour le prochain run"""
    cache_file = f"reservoir_filtre_{code_naf}.json" if code_naf else "reservoir_filtre_cache.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(prospects, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.getLogger("prospection_pipeline").error(f"❌ Erreur sauvegarde cache réservoir: {e}")

def charger_pagination_naf() -> Dict[str, int]:
    """Charge le tracker de pagination pour le mode NAF"""
    if os.path.exists("pagination_naf.json"):
        try:
            with open("pagination_naf.json", 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def sauvegarder_pagination_naf(pagination: Dict[str, int]):
    with open("pagination_naf.json", 'w') as f:
        json.dump(pagination, f, indent=2)

def charger_cache_icebreaker() -> Dict[str, Dict]:
    """Charge le cache des sites déjà scrapés"""
    if os.path.exists("cache_icebreaker.json"):
        try:
            with open("cache_icebreaker.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def sauvegarder_cache_icebreaker(cache: Dict[str, Dict]) -> None:
    with open("cache_icebreaker.json", 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

def equilibrer_reservoir_par_strategie(
    reservoir_dirigeants: List[Dict[str, Any]],
    batch_size: int,
    strategies: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Pioche dans le réservoir en essayant de maintenir l'équilibre entre stratégies."""
    if not reservoir_dirigeants:
        return []

    # ✅ Simplification : Si une seule stratégie, inutile de complexifier
    if len(strategies) <= 1:
        random.shuffle(reservoir_dirigeants)
        return reservoir_dirigeants[:batch_size]

    # ✅ Mode équilibré par stratégie
    selection = []
    # Grouper par stratégie
    groupes = {}
    for p in reservoir_dirigeants:
        strat_name = p.get("_strategy_name", "default")
        if strat_name not in groupes:
            groupes[strat_name] = []
        groupes[strat_name].append(p)

    # Mélanger chaque groupe
    for s in groupes:
        random.shuffle(groupes[s])

    # Piocher circulairement
    strat_names = list(groupes.keys())
    random.shuffle(strat_names)

    idx = 0
    while len(selection) < batch_size and any(groupes[s] for s in strat_names):
        s = strat_names[idx % len(strat_names)]
        if groupes[s]:
            selection.append(groupes[s].pop(0))
        idx += 1

    return selection

def prospect_valide(prospect: Dict[str, Any]) -> bool:
    """Validation minimale - conforme à la logique originale avec logging."""
    logger = logging.getLogger("prospection_pipeline")
    entreprise = prospect.get("entreprise_nom", "")
    nom_complet = f"{prospect.get('prenom', '')} {prospect.get('nom', '')}"

    if not (prospect.get("prenom") and prospect.get("nom")):
        logger.debug(f"   ❌ {entreprise} - REJETÉ: Nom/prénom manquant")
        return False
    
    effectif = prospect.get("effectif", "N/A")
    logger.info(f"   ✅ {nom_complet} ({entreprise}) - VALIDE (Effectif: {effectif})")
    return True

def filtrer_prospects(all_dirigeants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    logger = logging.getLogger("prospection_pipeline")
    logger.info("🔍 [Filtrage] Application des critères de sélection...")
    valides = [p for p in all_dirigeants if prospect_valide(p)]
    logger.info(f"📊 Prospects filtrés: {len(valides)}/{len(all_dirigeants)} conservés")
    return valides

# ---------------------------------------------------------------------------
# Logique d'Enrichissement (Web & Icebreaker)
# ---------------------------------------------------------------------------

def enrich_prospect_with_icebreaker(
    prospect: Dict[str, Any],
    deepinfra_api_key: str,
    log_fn: Optional[Any] = None,
    cache: Optional[Dict[str, Dict]] = None
) -> Dict[str, Any]:
    """Scrape le site et génère les variables A/B/C/D + Automatisations"""
    website = prospect.get("website", "").strip()
    
    # 1. Check cache
    if cache and website and website in cache:
        cached_data = cache[website]
        prospect["icebreaker_a"] = cached_data.get("A", "")
        prospect["icebreaker_b"] = cached_data.get("B", "")
        prospect["icebreaker_c"] = cached_data.get("C", "")
        prospect["icebreaker_d"] = cached_data.get("D", "")
        prospect["icebreaker_origin"] = "cache"
        if log_fn: log_fn(f"📦 [Cache] Icebreakers récupérés pour {website}", "DEBUG")
        return prospect

    # 2. Scraping
    if not website:
        # Fallback metadata NAF
        try_metadata_fallback(prospect, deepinfra_api_key, log_fn)
        return prospect

    # S'assurer que l'URL a un protocole
    if not website.startswith(("http://", "https://")):
        website = f"https://{website}"

    try:
        content = scrape_website_with_crawl4ai(
            website, 
            log_fn=log_fn, 
            allow_noisy_content=False
        )
        
        if not content:
            try_metadata_fallback(prospect, deepinfra_api_key, log_fn)
            return prospect

        # 3. Résumé IA
        summary = extract_detailed_summary_with_deepinfra(content, deepinfra_api_key, log_fn)
        if not summary:
            try_metadata_fallback(prospect, deepinfra_api_key, log_fn)
            return prospect
            
        prospect["icebreaker_d"] = summary

        # 4. Extraction A/B/C
        abc_vars = extract_abc_from_summary_with_deepinfra(summary, deepinfra_api_key, log_fn)
        if abc_vars:
            prospect["icebreaker_a"] = abc_vars.get("activite_principale", "")
            prospect["icebreaker_b"] = abc_vars.get("operations_concretes", "")
            prospect["icebreaker_c"] = abc_vars.get("valeur_humaine", "")
            prospect["icebreaker_origin"] = "deepinfra_custom"
        else:
            try_metadata_fallback(prospect, deepinfra_api_key, log_fn)

        # 5. Automatisations
        code_naf = prospect.get("code_naf", "")
        auto_list = generate_automation_list_with_deepinfra(summary, code_naf, deepinfra_api_key, log_fn)
        if auto_list:
            prospect["automation_list"] = auto_list
            prospect["automation_origin"] = "deepinfra_custom"
        
        return prospect

    except Exception as e:
        if log_fn: log_fn(f"💥 Erreur enrichissement icebreaker {website}: {e}", "ERROR")
        try_metadata_fallback(prospect, deepinfra_api_key, log_fn)
        return prospect

# ---------------------------------------------------------------------------
# Core Pipeline Logic
# ---------------------------------------------------------------------------

def recharger_reservoir_intelligent(
    reservoir_dirigeants: List[Dict[str, Any]],
    pages_chargees: int,
    params: Dict[str, int],
    strategies: List[Dict[str, Any]],
    siren_exclus: Set[str],
    filters: Dict[str, Any],
    headers: Dict[str, str],
    segment_name: str,
    target_count: int,
    debug_api_calls_ref: List[int]
) -> Tuple[List[Dict[str, Any]], int]:
    logger = logging.getLogger("prospection_pipeline")
    MAX_PAGES = params.get("MAX_PAGES_RESERVOIR", 2)
    CAP_MAX = calculer_cap_reservoir(target_count)

    nouvelles_pages = []
    pages_avec_resultats = 0
    pages_vides_consecutives = 0
    MAX_PAGES_VIDES = 10
    
    # En mode objet_social, page est globale. En mode NAF (stratégies), page est par stratégie.
    # Ici on simplifie : on boucle tant qu'on n'a pas assez de résultats.
    
    while pages_avec_resultats < MAX_PAGES and pages_vides_consecutives < MAX_PAGES_VIDES:
        page_dirigeants = []
        nb_total_avant_filtrage = 0
        
        for strategy in strategies:
            # Gestion pagination par stratégie
            strategy_page = strategy.get("_page_actuelle", strategy.get("_page_initiale", 0)) + 1
            
            # Filtres spécifiques (ex: département pour NAF)
            filters_strat = filters.copy()
            if strategy.get("departement"):
                filters_strat["departement"] = strategy["departement"]

            dirigeants, api_calls, nb_avant, _ = collect_dirigeants_for_strategy(
                strategy, 
                siren_exclus, 
                filters_strat, 
                headers, 
                logger.debug, 
                segment_name, 
                page_number=strategy_page
            )
            
            debug_api_calls_ref[0] += api_calls
            strategy["_page_actuelle"] = strategy_page
            
            page_dirigeants.extend(dirigeants)
            nb_total_avant_filtrage += nb_avant
        
        if nb_total_avant_filtrage == 0:
            logger.warning(f"   📄 [{segment_name}] Plus de résultats Pappers disponibles.")
            break
        elif page_dirigeants:
            nouvelles_pages.extend(page_dirigeants)
            pages_avec_resultats += 1
            pages_vides_consecutives = 0
            logger.debug(f"   📄 Collecté {len(page_dirigeants)} dirigeants sur ce tour.")
        else:
            pages_vides_consecutives += 1
            logger.info(f"   📄 Tour vide (filtré).")
            if pages_vides_consecutives >= MAX_PAGES_VIDES:
                break
    
    # Ajout au réservoir avec limite cap
    if nouvelles_pages:
        random.shuffle(nouvelles_pages)
        espace_libre = CAP_MAX - len(reservoir_dirigeants)
        if espace_libre > 0:
            reservoir_dirigeants.extend(nouvelles_pages[:espace_libre])
    
    return reservoir_dirigeants, pages_chargees + pages_avec_resultats


def collect_pme_prospects(target_count: Optional[int] = None) -> List[UnifiedProspect]:
    logger = logging.getLogger("prospection_pipeline")
    pappers_headers = {"User-Agent": "ProspectionBot/1.0"}
    
    if target_count is None:
        target_count = TARGETS_CONFIG.get("pme", PME_TARGET_DEFAULT)

    logger.info(f"🏢 [PME] Collecte de {target_count} prospects...")

    # 1. ID Campagne & Checkpoint
    if MODE_PROSPECTION == "code_naf" and CAMPAGNE_CODES_NAF.get("actif"):
        codes = sorted(CAMPAGNE_CODES_NAF.get("codes", []))
        campaign_id = f"naf_{'_'.join(codes)}"
        # Définition stratégies NAF (découpage département)
        DEPARTEMENTS = PME_SEARCH_DEPARTMENTS
        codes_str = ",".join(codes)
        pagination = charger_pagination_naf()
        
        PME_STRATEGY = []
        for dept in DEPARTEMENTS:
            key = f"{codes_str}_dept{dept}"
            PME_STRATEGY.append({
                "nom": f"NAF {codes_str} - {dept}",
                "code_naf": codes_str,
                "departement": dept,
                "par_page": 20,
                "_strategy_key": key,
                "_page_initiale": pagination.get(key, 0)
            })
        pages_chargees = 0
    else:
        # Mode Objet Social complet avec poids et cache
        from hashlib import md5
        PME_CATEGORIES = {
            # COMMUNICATION & MARKETING (Poids 3 - Prioritaire)
            "communication_marketing": [
                {"objet_social": "agence de communication", "nom": "Agence communication", "par_page": 20},
                {"objet_social": "agence conseil en communication", "nom": "Agence conseil comm", "par_page": 20},
                {"objet_social": "conseil en communication", "nom": "Conseil communication", "par_page": 20},
                {"objet_social": "communication digitale", "nom": "Communication digitale", "par_page": 20},
                {"objet_social": "communication visuelle", "nom": "Communication visuelle", "par_page": 20},
                {"objet_social": "marketing", "nom": "Marketing", "par_page": 20},
                {"objet_social": "marketing digital", "nom": "Marketing digital", "par_page": 20},
                {"objet_social": "conseil en marketing", "nom": "Conseil marketing", "par_page": 20},
                {"objet_social": "stratégie de marque", "nom": "Stratégie de marque", "par_page": 20},
                {"objet_social": "branding", "nom": "Branding", "par_page": 20},
                {"objet_social": "relations publiques", "nom": "Relations publiques", "par_page": 20},
                {"objet_social": "publicité", "nom": "Publicité", "par_page": 20},
                {"objet_social": "production publicitaire", "nom": "Production publicitaire", "par_page": 20},
                {"objet_social": "social media", "nom": "Social media", "par_page": 20},
                {"objet_social": "gestion des réseaux sociaux", "nom": "Gestion réseaux sociaux", "par_page": 20},
                {"objet_social": "content marketing", "nom": "Content marketing", "par_page": 20},
                {"objet_social": "création de contenu", "nom": "Création contenu", "par_page": 20},
                {"objet_social": "rédaction", "nom": "Rédaction", "par_page": 20},
                {"objet_social": "copywriting", "nom": "Copywriting", "par_page": 20},
            ],
            # CONSEIL B2B (Poids 3 - Prioritaire)
            "conseil_b2b": [
                {"objet_social": "cabinet de conseil", "nom": "Cabinet conseil", "par_page": 20},
                {"objet_social": "conseil en gestion", "nom": "Conseil gestion", "par_page": 20},
                {"objet_social": "conseil en management", "nom": "Conseil management", "par_page": 20},
                {"objet_social": "conseil en stratégie", "nom": "Conseil stratégie", "par_page": 20},
                {"objet_social": "conseil en organisation", "nom": "Conseil organisation", "par_page": 20},
                {"objet_social": "conseil en innovation", "nom": "Conseil innovation", "par_page": 20},
                {"objet_social": "conseil commercial", "nom": "Conseil commercial", "par_page": 20},
                {"objet_social": "conseil en développement d'entreprise", "nom": "Conseil développement", "par_page": 20},
                {"objet_social": "audit organisationnel", "nom": "Audit organisationnel", "par_page": 20},
                {"objet_social": "audit marketing", "nom": "Audit marketing", "par_page": 20},
                {"objet_social": "accompagnement d'entreprises", "nom": "Accompagnement entreprises", "par_page": 20},
            ],
            # FORMATION / COACHING (Poids 2)
            "formation_coaching": [
                {"objet_social": "organisme de formation", "nom": "Organisme formation", "par_page": 20},
                {"objet_social": "formation professionnelle", "nom": "Formation professionnelle", "par_page": 20},
                {"objet_social": "formation continue", "nom": "Formation continue", "par_page": 20},
                {"objet_social": "formation en ligne", "nom": "Formation en ligne", "par_page": 20},
                {"objet_social": "e-learning", "nom": "E-learning", "par_page": 20},
                {"objet_social": "coaching professionnel", "nom": "Coaching professionnel", "par_page": 20},
                {"objet_social": "coaching en entreprise", "nom": "Coaching entreprise", "par_page": 20},
            ],
            # ÉVÉNEMENTIEL (Poids 2)
            "evenementiel": [
                {"objet_social": "agence événementielle", "nom": "Agence événementielle", "par_page": 20},
                {"objet_social": "organisation d'événements", "nom": "Organisation événements", "par_page": 20},
                {"objet_social": "organisation de séminaires", "nom": "Organisation séminaires", "par_page": 20},
                {"objet_social": "organisation de conférences", "nom": "Organisation conférences", "par_page": 20},
                {"objet_social": "production événementielle", "nom": "Production événementielle", "par_page": 20},
            ],
            # COMMERCE / E-COMMERCE (Poids 2)
            "commerce_ecommerce": [
                {"objet_social": "commerce de détail", "nom": "Commerce détail", "par_page": 20},
                {"objet_social": "commerce de détail sur internet", "nom": "Commerce détail internet", "par_page": 20},
                {"objet_social": "vente en ligne", "nom": "Vente en ligne", "par_page": 20},
                {"objet_social": "boutique en ligne", "nom": "Boutique en ligne", "par_page": 20},
                {"objet_social": "exploitation de site e-commerce", "nom": "Site e-commerce", "par_page": 20},
                {"objet_social": "marketplace", "nom": "Marketplace", "par_page": 20},
            ],
            # IMMOBILIER (Poids 1)
            "immobilier": [
                {"objet_social": "agence immobilière", "nom": "Agence immobilière", "par_page": 20},
                {"objet_social": "transaction immobilière", "nom": "Transaction immobilière", "par_page": 20},
                {"objet_social": "gestion locative", "nom": "Gestion locative", "par_page": 20},
                {"objet_social": "administration de biens", "nom": "Administration biens", "par_page": 20},
                {"objet_social": "syndic de copropriété", "nom": "Syndic", "par_page": 20},
            ],
            # RH / RECRUTEMENT (Poids 1)
            "rh_recrutement": [
                {"objet_social": "cabinet de recrutement", "nom": "Cabinet recrutement", "par_page": 20},
                {"objet_social": "recrutement", "nom": "Recrutement", "par_page": 20},
                {"objet_social": "conseil en ressources humaines", "nom": "Conseil RH", "par_page": 20},
                {"objet_social": "bilan de compétences", "nom": "Bilan compétences", "par_page": 20},
                {"objet_social": "outplacement", "nom": "Outplacement", "par_page": 20},
            ],
            # ARCHI / BUREAUX D'ÉTUDES (Poids 1)
            "architecture_etudes": [
                {"objet_social": "architecture", "nom": "Architecture", "par_page": 20},
                {"objet_social": "maîtrise d'œuvre", "nom": "Maîtrise d'œuvre", "par_page": 20},
                {"objet_social": "bureau d'études techniques", "nom": "Bureau études", "par_page": 20},
                {"objet_social": "design d'intérieur", "nom": "Design intérieur", "par_page": 20},
                {"objet_social": "décoration intérieure", "nom": "Décoration", "par_page": 20},
            ],
            # SANTÉ / BIEN-ÊTRE (Poids 1)
            "sante_bienetre": [
                {"objet_social": "soins esthétiques", "nom": "Soins esthétiques", "par_page": 20},
                {"objet_social": "institut de beauté", "nom": "Institut beauté", "par_page": 20},
                {"objet_social": "bien-être", "nom": "Bien-être", "par_page": 20},
                {"objet_social": "spa", "nom": "Spa", "par_page": 20},
                {"objet_social": "centre esthétique", "nom": "Centre esthétique", "par_page": 20},
            ]
        }

        category_weights = {
            "communication_marketing": 3,
            "conseil_b2b": 3,
            "formation_coaching": 2,
            "evenementiel": 2,
            "commerce_ecommerce": 2,
            "immobilier": 1,
            "rh_recrutement": 1,
            "architecture_etudes": 1,
            "sante_bienetre": 1,
        }

        # Cache persistant des mots-clés testés
        keywords_testees = []
        if os.path.exists(STRATEGIES_CACHE_FILE):
            try:
                with open(STRATEGIES_CACHE_FILE, "r") as f:
                    cache_data = json.load(f)
                    now = time.time()
                    # Garder uniquement les plus récents (30 jours)
                    keywords_testees = [k for k, t in cache_data.items() if (now - t) < 30 * 86400]
            except: pass

        all_strategies = []
        all_weights = []
        for category, strategies in PME_CATEGORIES.items():
            weight = category_weights.get(category, 1)
            for s in strategies:
                if s["objet_social"] not in keywords_testees:
                    all_strategies.append(s)
                    all_weights.append(weight)

        if not all_strategies: # Reset si tout a été testé
            for category, strategies in PME_CATEGORIES.items():
                weight = category_weights.get(category, 1)
                for s in strategies:
                    all_strategies.append(s)
                    all_weights.append(weight)

        # SÉLECTION ADAPTATIVE : économie pour tests, diversité pour usage réel
        if target_count <= 5:
            max_strategies_total = 2  # Mode test économique
        elif target_count <= 15:
            max_strategies_total = 6  # Usage modéré
        else:
            max_strategies_total = 15  # Usage normal avec diversité complète

        logger.info(f"🎯 [Adaptatif] Max {max_strategies_total} stratégies pour {target_count} prospects")

        # Sélection pondérée aléatoire
        PME_STRATEGY = random.choices(
            all_strategies,
            weights=all_weights,
            k=min(max_strategies_total, len(all_strategies))
        )

        # Éviter les doublons possibles
        seen = set()
        PME_STRATEGY = [s for s in PME_STRATEGY if not (s["objet_social"] in seen or seen.add(s["objet_social"]))]

        # Mélange final
        random.shuffle(PME_STRATEGY)
        
        # Enregistrer dans le cache
        try:
            cache_data = {}
            if os.path.exists(STRATEGIES_CACHE_FILE):
                with open(STRATEGIES_CACHE_FILE, "r") as f: cache_data = json.load(f)
            for s in PME_STRATEGY:
                cache_data[s["objet_social"]] = time.time()
            with open(STRATEGIES_CACHE_FILE, "w") as f: json.dump(cache_data, f)
        except: pass

        campaign_id = f"objet_{md5(str(sorted([s['nom'] for s in PME_STRATEGY])).encode()).hexdigest()[:8]}"
        pages_chargees = 0

    # Reprise checkpoint
    checkpoint_data = None
    if _checkpoint_manager.has_checkpoint(campaign_id):
        checkpoint_data = _checkpoint_manager.load_last_checkpoint(campaign_id)
        if checkpoint_data:
            phase = checkpoint_data.get("progress_info", {}).get("phase", "")
            qualified_count = checkpoint_data.get("progress_info", {}).get("qualified_count", 0)
            logger.info(f"🔄 Reprise depuis checkpoint {campaign_id} (Phase: {phase}, Prospects: {qualified_count})")
            
            # Restaurer les prospects qualifiés
            if checkpoint_data.get("prospects"):
                prospects_qualifies_finaux = checkpoint_data.get("prospects", [])
                logger.info(f"✅ {len(prospects_qualifies_finaux)} prospects restaurés dans la file d'attente.")
            
            # Gestion des phases avancées (skip steps)
            if phase == "post_icebreaker_enrichment":
                logger.info("✅ Campagne déjà terminée à 100%. Retour direct.")
                # Conversion et retour
                unified_prospects = []
                for p in prospects_qualifies_finaux:
                    email = p.get("email")
                    if isinstance(email, list) and email: email = email[0].get("email", str(email[0]))
                    unified_prospects.append(UnifiedProspect(
                        segment="pme",
                        prospect_name=p.get("nom_complet", ""),
                        company_name=p.get("entreprise_nom", ""),
                        email=str(email) if email else "",
                        website=p.get("website", ""),
                        linkedin=p.get("linkedin", ""),
                        instagram="",
                        location=p.get("localisation", ""),
                        source="pappers+dropcontact",
                        notes=f"SIREN: {p.get('siren','')}"
                    ))
                return unified_prospects

            # Si on a déjà fini la boucle principale, on peut passer direct à l'enrichissement
            if phase in ["pme_main_loop_done", "post_website_enrichment"] and len(prospects_qualifies_finaux) >= target_count:
                logger.info("⏩ Boucle principale déjà terminée, passage à l'enrichissement.")
                # On ne rentre pas dans le while
                target_count = 0 


    # 2. Préparation Réservoir
    params = calculer_params_reservoir(target_count)
    reservoir_pme_persistant = charger_reservoir_pme_csv()
    siren_deja_testes = {str(p.get("siren", "")) for p in reservoir_pme_persistant if p.get("siren")}
    
    # Chargement cache filtré
    code_naf_cache = ",".join(CAMPAGNE_CODES_NAF["codes"]) if MODE_PROSPECTION == "code_naf" else None
    reservoir_dirigeants = charger_reservoir_filtre_cache(code_naf=code_naf_cache)
    
    if 'prospects_qualifies_finaux' not in locals():
        prospects_qualifies_finaux = []

    prospects_pourris = []
    debug_api_calls = [0]
    iteration_count = 0
    max_tentatives_sans_progres = 10
    tentatives_sans_progres = 0
    dernier_count = 0
    
    # 3. Boucle Principale
    while len(prospects_qualifies_finaux) < target_count and pages_chargees < PAPPERS_MAX_PAGES:
        try:
            iteration_count += 1
            manquants = target_count - len(prospects_qualifies_finaux)
            progression_pct = (len(prospects_qualifies_finaux) / target_count * 100) if target_count > 0 else 0
            
            logger.info("")
            logger.info("="*80)
            logger.info(f"🔄 [ITÉRATION {iteration_count}] Progression: {len(prospects_qualifies_finaux)}/{target_count} ({progression_pct:.1f}%)")
            logger.info(f"🎯 [OBJECTIF] {manquants} prospects manquants pour atteindre les {target_count}")
            logger.info("="*80)
            
            # Recharge si nécessaire
            if len(reservoir_dirigeants) < params['SEUIL_RECHARGE']:
                reservoir_bruts_new, pages_chargees = recharger_reservoir_intelligent(
                    [], # temp list
                    pages_chargees, params, PME_STRATEGY, siren_deja_testes, PME_FILTERS, pappers_headers, "PME", target_count, debug_api_calls
                )
                # Sauvegarder bruts
                for p in reservoir_bruts_new:
                    p["date_ajout"] = datetime.now().strftime("%Y-%m-%d")
                reservoir_pme_persistant.extend(reservoir_bruts_new)
                
                # Filtrer et ajouter au réservoir actif
                valides = filtrer_prospects(reservoir_bruts_new)
                reservoir_dirigeants.extend(valides)
                
                if not reservoir_dirigeants:
                    logger.warning("⚠️ Réservoir vide (aucun prospect valide sur ces pages), arrêt.")
                    break

            # Pioche
            batch_size = min(params['BATCH_SIZE'], len(reservoir_dirigeants))
            prospects_valides = equilibrer_reservoir_par_strategie(reservoir_dirigeants, batch_size, PME_STRATEGY)
            
            # Retirer du réservoir
            for p in prospects_valides:
                if p in reservoir_dirigeants: reservoir_dirigeants.remove(p)

            if not prospects_valides: break

            # Enrichissement Dropcontact
            def log_dc(msg, lvl): getattr(logger, lvl.lower())(msg)
            
            qualifies, rejetes = dropcontact_enrich_loop(
                prospects_valides, target_count, 
                {"Content-Type": "application/json", "X-Access-Token": DROPCONTACT_API_KEY}, 
                log_dc, "pme"
            )
            
            # Validation Emails
            ok, pas_ok = million_verifier_validate_batch(qualifies, MILLION_VERIFIER_API_KEY, log_dc)
            
            prospects_qualifies_finaux.extend(ok)
            prospects_pourris.extend(rejetes + pas_ok)
            
            # Update exclusions SIREN
            for p in ok + rejetes + pas_ok:
                if p.get("siren"): siren_deja_testes.add(p["siren"])

            # SÉCURITÉ ANTI-BLOCAGE
            if len(prospects_qualifies_finaux) == dernier_count:
                tentatives_sans_progres += 1
                logger.warning(f"⚠️ [SÉCURITÉ] Aucun nouveau prospect ({tentatives_sans_progres}/{max_tentatives_sans_progres})")
                if tentatives_sans_progres >= max_tentatives_sans_progres:
                    logger.error(f"🛑 [ARRÊT] Aucun progrès après {max_tentatives_sans_progres} tentatives.")
                    break
            else:
                tentatives_sans_progres = 0
                dernier_count = len(prospects_qualifies_finaux)
                
            # Checkpoint boucle principale
            _checkpoint_manager.save_checkpoint(
                prospects=prospects_qualifies_finaux,
                segment_name="pme_main_loop",
                progress_info={"phase": "pme_main_loop", "count": len(prospects_qualifies_finaux)},
                campaign_id=campaign_id
            )

        except Exception as e:
            error_str = str(e)
            if "QUOTA_EXCEEDED" in error_str:
                logger.error(f"🚫 [ARRÊT FORCÉ] QUOTA API ÉPUISÉ: {error_str}")
                break
            
            # Si c'est une erreur de code (NameError, TypeError, AttributeError), on arrête les frais
            if isinstance(e, (NameError, TypeError, AttributeError, ImportError)):
                logger.error(f"🛑 [ARRÊT CRITIQUE] Erreur logicielle détectée : {e}", exc_info=True)
                break
                
            logger.error(f"💥 Erreur itération {iteration_count}: {e}", exc_info=True)
            # Pour les autres types d'erreurs (réseau, etc.), on peut tenter la suivante

    # Checkpoint fin de boucle
    if len(prospects_qualifies_finaux) > 0:
        _checkpoint_manager.save_checkpoint(
            prospects=prospects_qualifies_finaux,
            segment_name="pme_main_loop_done",
            progress_info={"phase": "pme_main_loop_done", "count": len(prospects_qualifies_finaux)},
            campaign_id=campaign_id
        )

    # 4. Enrichissement Manquant (Websites + Icebreakers)
    logger.info("🌐 [Enrichissement Final] Websites & IA...")
    enrich_missing_websites(prospects_qualifies_finaux, logger.info)

    # Checkpoint après websites
    _checkpoint_manager.save_checkpoint(
        prospects=prospects_qualifies_finaux,
        segment_name="post_website_enrichment",
        progress_info={"phase": "post_website_enrichment", "count": len(prospects_qualifies_finaux)},
        campaign_id=campaign_id
    )

        
    cache_ib = charger_cache_icebreaker()
    final_enriched = []
    
    for p in prospects_qualifies_finaux:
        log_wrapper = lambda msg, lvl="INFO": getattr(logger, lvl.lower(), logger.info)(msg)
        enriched = enrich_prospect_with_icebreaker(p, DEEPINFRA_API_KEY, log_wrapper, cache_ib)
        final_enriched.append(enriched)
        
        web = enriched.get("website")
        if web and enriched.get("icebreaker_a"):
             cache_ib[web] = {
                 "A": enriched["icebreaker_a"], "B": enriched["icebreaker_b"], 
                 "C": enriched["icebreaker_c"], "D": enriched.get("icebreaker_d", "")
             }
    
    sauvegarder_cache_icebreaker(cache_ib)
    
    # Checkpoint FINAL
    _checkpoint_manager.save_checkpoint(
        prospects=final_enriched,
        segment_name="post_icebreaker_enrichment",
        progress_info={"phase": "post_icebreaker_enrichment", "count": len(final_enriched)},
        campaign_id=campaign_id
    )
    
    # 5. Sauvegarde Finale & Exports
    sauvegarder_reservoir_pme_csv(reservoir_pme_persistant)
    sauvegarder_reservoir_filtre_cache(reservoir_dirigeants, code_naf=code_naf_cache)
    if MODE_PROSPECTION == "code_naf":
        # Sauvegarder pagination (update sans écraser l'existant)
        pagination_a_sauvegarder = charger_pagination_naf()
        for s in PME_STRATEGY:
            if "_strategy_key" in s:
                pagination_a_sauvegarder[s["_strategy_key"]] = s.get("_page_actuelle", 0)
        sauvegarder_pagination_naf(pagination_a_sauvegarder)
    
    # Logs finaux de synthèse
    logger.info("")
    logger.info("="*80)
    logger.info("✅ [PME] COLLECTE TERMINÉE")
    logger.info("="*80)
    logger.info(f"📊 [RÉSULTAT] {len(final_enriched)} prospects finaux créés")
    logger.info(f"🎯 [OBJECTIF] {len(final_enriched)}/{target_count} - {'✅ ATTEINT' if len(final_enriched) >= target_count else '⚠️ PARTIEL'}")
    logger.info(f"🔄 [ITERATIONS] {iteration_count} itérations effectuées")
    logger.info(f"🔢 [API PAPPERS] {debug_api_calls[0]} appels effectués")
    logger.info(f"📂 [RÉSERVOIR] {len(siren_deja_testes)} SIRENs testés au total")
    logger.info("="*80)

    # Export CSVs (Qualifiés vs À Nettoyer)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    df_final = pd.DataFrame(final_enriched)
    
    # ... Logique export CSV simplifiée ... (à adapter selon besoin exact)
    # Pour l'instant on retourne les UnifiedProspects

    unified_prospects = []
    for p in final_enriched:
        email = p.get("email")
        if isinstance(email, list) and email: email = email[0].get("email", str(email[0]))
        
        unified_prospects.append(UnifiedProspect(
            segment="pme",
            prospect_name=p.get("nom_complet", ""),
            company_name=p.get("entreprise_nom", ""),
            email=str(email) if email else "",
            website=p.get("website", ""),
            linkedin=p.get("linkedin", ""),
            instagram="",
            location=p.get("localisation", ""),
            source="pappers+dropcontact",
            notes=f"SIREN: {p.get('siren','')}",
            icebreaker_a=p.get("icebreaker_a", ""),
            icebreaker_b=p.get("icebreaker_b", ""),
            icebreaker_c=p.get("icebreaker_c", ""),
            icebreaker_d=p.get("automation_list", p.get("icebreaker_d", ""))
        ))


    return unified_prospects

