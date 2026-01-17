import asyncio
from typing import Optional, Callable

def scrape_website_with_crawl4ai(
    url: str,
    log_fn: Optional[Callable[[str, str], None]] = None,
    allow_noisy_content: bool = False,
    min_chars: int = 600
) -> Optional[str]:
    """
    Scrape un site web avec Crawl4AI (deep crawl) et retourne le contenu en Markdown

    Utilise un deep crawl APPROFONDI pour récupérer homepage + 5-6 pages importantes
    (about, services, équipe, etc.) pour avoir un maximum d'informations.

    Args:
        url: URL du site à scraper
        log_fn: Fonction de log optionnelle

    Returns:
        Contenu Markdown combiné (limité à 20000 chars pour Groq) ou None si erreur
    """
    # Import local pour éviter les problèmes d'initialisation au chargement du module
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
        # Les filtres sont des imports spécifiques à Crawl4AI
        try:
            from crawl4ai.deep_crawling.filters import URLFilter, FilterChain
        except ImportError:
            # Fallback si version ancienne
            URLFilter = object
            FilterChain = None
        try:
            from crawl4ai.content_filter_strategy import PruningContentFilter
            from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
        except ImportError:
            PruningContentFilter = None
            DefaultMarkdownGenerator = None
    except ImportError:
        if log_fn:
            log_fn("❌ Crawl4AI non installé. Impossible de scraper.", "ERROR")
        return None

    async def crawl():
        # Import local pour CAMPAGNE_CODES_NAF (utilisé pour détecter mode e-commerce)
        from src.config.settings import CAMPAGNE_CODES_NAF
        from src.utils.text import clean_scraped_markdown, evaluate_content_quality
        try:

            # Liste universelle : Nettoie le bruit sans casser les sites vitrines
            EXCLUDED_PATH_KEYWORDS = [
                # 1. Le "bruit" technique (Sûr pour tout le monde)
                "login", "connexion", "signin", "signup", "register",
                "auth", "password", "mdp", "reset",
                "cart", "panier", "basket", "bag",
                "checkout", "commande", "order", "purchase",
                "account", "compte", "profile", "profil",
                "search", "recherche", "query",

                # 2. Le "bruit" E-commerce pur (Sûr pour 99% des agences)
                "wishlist", "favoris", "compare",
                "category", "catégorie",  # Souvent des listes sans fin
                "filter", "filtre", "sort",  # Pages de tri
                "reduction", "remise", "promo", "solde", "discount",  # Promos
                "livraison", "shipping", "delivery", "expedition",  # Livraison

                # 3. Événements commerciaux FR/US (pages promotionnelles)
                "black-friday", "blackfriday", "cyber-monday", "cybermonday",
                "noel", "christmas", "xmas",
                "saint-valentin", "valentine",
                "paques", "easter",
                "fete-des-meres", "fete-des-peres", "mothers-day", "fathers-day",
                "halloween", "thanksgiving",
                "soldes", "sales", "clearance",
                "prime-day", "singles-day",
            ]

            # Codes NAF e-commerce (nécessitent une whitelist stricte pour éviter pages produits infinies)
            CODES_NAF_ECOMMERCE = ["4791A", "4791B"]

            # Détecter si on est en mode e-commerce
            is_ecommerce_mode = False
            if CAMPAGNE_CODES_NAF.get("actif"):
                codes_campagne = CAMPAGNE_CODES_NAF.get("codes", [])
                is_ecommerce_mode = any(code in CODES_NAF_ECOMMERCE for code in codes_campagne)

            # Pages à INCLURE pour l'e-commerce uniquement (whitelist stricte - pertinentes e-commerce)
            INCLUDED_PATH_KEYWORDS = [
                # À propos / Histoire / Qui sommes-nous
                "about", "aboutus", "about-us", "a-propos", "apropos",
                "qui-sommes-nous", "quisommesnous", "qui-nous-sommes", "quinoussommes",
                "histoire", "notre-histoire", "notrehistoire", "history", "our-history", "ourhistory",
                "story", "our-story", "ourstory", "origin", "origine", "origins", "origines",

                # Mission / Valeurs / Engagement
                "mission", "missions", "notre-mission", "notremission", "our-mission", "ourmission",
                "valeurs", "values", "nos-valeurs", "nosvaleurs", "our-values", "ourvalues",
                "vision", "visions", "notre-vision", "notrevision", "our-vision", "ourvision",
                "engagement", "engagements", "nos-engagements", "nosengagements",
                "commitment", "commitments", "our-commitment", "ourcommitment",
                "manifeste", "manifesto", "philosophie", "philosophy",

                # Marque / Boutique
                "marque", "brand", "notre-marque", "notremarque", "our-brand", "ourbrand",
                "boutique", "shop", "store", "notre-boutique", "notreboutique",
                "our-shop", "ourshop", "magasin",

                # Équipe / Fondateurs
                "equipe", "team", "notre-equipe", "notreequipe", "our-team", "ourteam",
                "fondateur", "fondateurs", "founder", "founders", "fondatrice", "fondatrices",
                "createur", "créateur", "createurs", "créateurs", "creator", "creators",

                # Témoignages / Avis clients
                "temoignages", "témoignages", "temoignage", "témoignage",
                "testimonials", "testimonial", "testimony",
                "avis", "reviews", "review", "opinion", "opinions",
                "clients", "customers", "nos-clients", "nosclients", "client",

                # Blog / Actualités
                "blog", "blogs", "actualites", "actualités", "actu", "actus",
                "news", "nouvelles", "nouvelle", "article", "articles",
                "magazine", "journal",

                # FAQ / Aide
                "faq", "faqs", "questions", "question", "aide", "help",
                "support", "assistance", "sav", "service-client",
                "guide", "guides", "comment", "how-to", "howto",

                # Responsabilité / Éthique / Durable
                "responsabilite", "responsabilité", "responsibility", "rse", "csr",
                "ethique", "ethics", "ethical",
                "durable", "durabilite", "durabilité", "sustainable", "sustainability",
                "eco", "ecologique", "écologique", "green", "bio", "organic",

                # Presse
                "presse", "press", "media", "medias", "médias",
                "publication", "publications",

                # Vocabulaire Luxe / Marque / Héritage
                "maison", "la-maison", "notre-maison",
                "univers", "l-univers", "world",
                "heritage", "héritage", "legacy",
                "savoir-faire", "craftsmanship", "artisanat",
                "tradition",
                "groupe", "group", "corporate", "societe", "company",
                "concept",
            ]

            # Créer un filtre personnalisé pour le deep crawl
            class AdaptiveURLFilter(URLFilter):
                """Filtre adaptatif pour e-commerce vs autres secteurs"""

                def apply(self, url: str) -> bool:
                    """Retourne True si l'URL doit être crawlée"""
                    url_lower = url.lower()

                    # 1. Toujours exclure le bruit e-commerce/promo (tous secteurs)
                    for keyword in EXCLUDED_PATH_KEYWORDS:
                        if keyword in url_lower:
                            return False

                    # 2. MODE E-COMMERCE (4791A/4791B) : Whitelist stricte
                    if is_ecommerce_mode:
                        from urllib.parse import urlparse
                        parsed = urlparse(url)

                        # Homepage toujours acceptée (avec variants linguistiques)
                        if parsed.path in ['', '/', '/fr', '/fr/', '/en', '/en/', '/FR', '/FR/', '/EN', '/EN/']:
                            return True

                        # Seulement les pages business listées
                        for keyword in INCLUDED_PATH_KEYWORDS:
                            if keyword in url_lower:
                                return True

                        # Refuser le reste (évite pages produits infinies)
                        return False

                    # 3. AUTRES SECTEURS : Accepter tout sauf blacklist (limité par max_pages=15)
                    return True

            # Créer le FilterChain avec notre filtre personnalisé
            filter_chain = FilterChain([AdaptiveURLFilter()])

            # Stratégie deep crawl avec le filtre
            strategy = BFSDeepCrawlStrategy(
                max_depth=1,
                max_pages=15,
                include_external=True,  # On laisse le filtre gérer l'inclusion/exclusion
                filter_chain=filter_chain
            )

            browser_config = BrowserConfig(
                headless=True,
                enable_stealth=True,
                text_mode=True,
                viewport_width=1280,
                viewport_height=720,
                verbose=False,
                user_agent_mode="random"
            )

            config = CrawlerRunConfig(
                wait_until="domcontentloaded",
                delay_before_return_html=3.0,
                page_timeout=60000,

                excluded_tags=['script', 'style', 'noscript'],
                word_count_threshold=10,
                simulate_user=True,
                remove_overlay_elements=True,
                verbose=True,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=PruningContentFilter(threshold=0.35)
                ) if DefaultMarkdownGenerator and PruningContentFilter else None,
                deep_crawl_strategy=strategy
            )

            async with AsyncWebCrawler(config=browser_config, verbose=False) as crawler:

                result = await crawler.arun(
                    url=url,
                    config=config
                )

                # Avec deep_crawl_strategy, result est une LISTE de CrawlResult
                if not isinstance(result, list):
                    results = [result] if result else []
                else:
                    results = result

                if not results:
                    if log_fn:
                        log_fn(f"⚠️ [Crawl4AI] Aucun résultat retourné pour {url}", "WARNING")
                    return None

                combined_content = ""
                pages_scraped = 0

                for result in results:
                    if result.success and result.markdown:
                        markdown_text = ""
                        if hasattr(result.markdown, "fit_markdown") and result.markdown.fit_markdown:
                            markdown_text = result.markdown.fit_markdown
                        elif hasattr(result.markdown, "raw_markdown"):
                            markdown_text = result.markdown.raw_markdown
                        else:
                            markdown_text = str(result.markdown)

                        if markdown_text:
                            cleaned_markdown = clean_scraped_markdown(markdown_text)
                            combined_content += f"\n\n{cleaned_markdown}\n\n"
                            pages_scraped += 1
                    else:
                        if log_fn:
                            error_msg = getattr(result, "error_message", "") or "résultat sans markdown"
                            status_code = getattr(result, "status_code", None)
                            details = f"status={status_code}" if status_code else ""
                            log_fn(f"⚠️ [Crawl4AI] Page ignorée ({error_msg}) {details}".strip(), "WARNING")

                if combined_content:
                    # Limiter à 20000 chars pour Groq (augmenté pour avoir plus d'infos)
                    content = combined_content[:20000]
                    is_valid, reason = evaluate_content_quality(content, min_chars=min_chars)
                    if not is_valid:
                        if log_fn:
                            log_fn(f"⚠️ [Crawl4AI] Contenu jugé bruité ({reason}) pour {url}", "WARNING")
                            snippet = content[:400].replace("\n", " ")
                            log_fn(f"📝 [Crawl4AI] Aperçu contenu rejeté: {snippet}...", "DEBUG")
                        if not allow_noisy_content:
                            return None
                        if log_fn:
                            log_fn(f"ℹ️ [Crawl4AI] Contenu bruité conservé (mode debug) pour {url}", "INFO")

                    if log_fn:
                        log_fn(f"✅ [Crawl4AI] {pages_scraped} pages scrapées, {len(content)} caractères", "DEBUG")
                    return content
                else:
                    if log_fn:
                        log_fn(f"⚠️ [Crawl4AI] Aucun contenu Markdown exploitable pour {url}", "WARNING")
                return None

        except Exception as e:
            if log_fn:
                import traceback
                tb = traceback.format_exc(limit=4)
                log_fn(f"❌ [Crawl4AI] Erreur scraping {url}: {e}", "ERROR")
                log_fn(f"📄 Traceback Crawl4AI: {tb}", "ERROR")
            return None

    try:
        return asyncio.run(crawl())
    except Exception as e:
        if log_fn:
            log_fn(f"💥 [Crawl4AI] Exception asyncio pour {url}: {e}", "ERROR")
        return None
