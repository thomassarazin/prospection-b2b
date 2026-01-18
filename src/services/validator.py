import aiohttp
import asyncio
import logging
import re
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Configuration des validateurs (pattern regex + endpoint de test)
KEY_VALIDATORS = {
    "stripe_live": {
        "pattern": r"sk_live_[0-9a-zA-Z]{24}",
        "name": "Stripe Live Token",
        "method": "GET",
        "url": "https://api.stripe.com/v1/charges",
        "auth_type": "basic",  # username=key, password=""
        "impact": "Accès critique : Liste des transactions clients accessible."
    },
    "google_maps": {
        "pattern": r"AIza[0-9a-zA-Z-_]{35}",
        "name": "Google Maps API Key",
        "method": "GET",
        "url": "https://maps.googleapis.com/maps/api/staticmap?center=45%2C10&zoom=7&size=400x400&key={KEY}",
        "auth_type": "url",
        "impact": "Exposition financière : Clé utilisable sans restriction de domaine."
    },
    "aws_access_key": {
        "pattern": r"AKIA[0-9A-Z]{16}",
        "name": "AWS Access Key",
        "method": None,  # Nécessite aussi le secret
        "url": None,
        "auth_type": None,
        "impact": "Clé AWS détectée (nécessite le secret pour validation)."
    },
    "mailgun": {
        "pattern": r"key-[0-9a-zA-Z]{32}",
        "name": "Mailgun Private Key",
        "method": "GET",
        "url": "https://api.mailgun.net/v3/domains",
        "auth_type": "basic",  # username=api, password=key
        "auth_user": "api",
        "impact": "Accès emails : Peut envoyer/lire des emails depuis le domaine."
    },
    "sendgrid": {
        "pattern": r"SG\.[0-9a-zA-Z-_]{22}\.[0-9a-zA-Z-_]{43}",
        "name": "SendGrid API Token",
        "method": "GET",
        "url": "https://api.sendgrid.com/v3/scopes",
        "auth_type": "bearer",
        "impact": "Accès emails : Peut envoyer des emails en masse."
    },
    "github_token": {
        "pattern": r"ghp_[0-9a-zA-Z]{36}",
        "name": "GitHub Personal Access Token",
        "method": "GET",
        "url": "https://api.github.com/user",
        "auth_type": "bearer",
        "impact": "Accès GitHub : Peut lire/modifier les repos selon les scopes."
    },
    "telegram_bot": {
        "pattern": r"[0-9]{9,10}:[0-9a-zA-Z_-]{35}",
        "name": "Telegram Bot API Token",
        "method": "GET",
        "url": "https://api.telegram.org/bot{KEY}/getMe",
        "auth_type": "url",
        "impact": "Contrôle du bot Telegram : Peut envoyer des messages."
    },
    "slack_webhook": {
        "pattern": r"https://hooks\.slack\.com/services/T[0-9A-Z]{8}/B[0-9A-Z]{8,}/[0-9a-zA-Z]{24}",
        "name": "Slack Webhook",
        "method": "POST",
        "url": "{KEY}",
        "auth_type": "url",
        "body": {"text": "KeyHacks validation test"},
        "impact": "Peut publier des messages dans un canal Slack."
    },
    "mailchimp": {
        "pattern": r"[0-9a-f]{32}-us[0-9]{1,2}",
        "name": "MailChimp API Key",
        "method": "GET",
        "url": "https://{DC}.api.mailchimp.com/3.0/",
        "auth_type": "basic",
        "auth_user": "anystring",
        "impact": "Accès MailChimp : Peut gérer les listes d'abonnés."
    },
    "twilio": {
        "pattern": r"SK[0-9a-fA-F]{32}",
        "name": "Twilio API Key",
        "method": None,  # Nécessite Account SID
        "url": None,
        "auth_type": None,
        "impact": "Clé Twilio détectée (nécessite Account SID pour validation)."
    },
    "paypal_client": {
        "pattern": r"A[A-Z0-9]{79}",
        "name": "PayPal Client ID",
        "method": None,
        "url": None,
        "auth_type": None,
        "impact": "PayPal Client ID détecté (nécessite secret pour validation)."
    },
    "cloudflare": {
        "pattern": r"[A-Za-z0-9_-]{40}",
        "name": "Cloudflare API Token",
        "method": "GET",
        "url": "https://api.cloudflare.com/client/v4/user/tokens/verify",
        "auth_type": "bearer",
        "impact": "Accès Cloudflare : Peut gérer les zones DNS."
    },
    "heroku": {
        "pattern": r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "name": "Heroku API Key",
        "method": "GET",
        "url": "https://api.heroku.com/account",
        "auth_type": "bearer",
        "impact": "Accès Heroku : Peut gérer les applications."
    },
    "firebase": {
        "pattern": r"AIza[0-9a-zA-Z_-]{35}",  # Peut se confondre avec Google Maps
        "name": "Firebase/Google API Key",
        "method": "GET",
        "url": "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={KEY}",
        "auth_type": "url",
        "impact": "Accès Firebase : Peut authentifier ou accéder aux services Google."
    },
    "algolia": {
        "pattern": r"[0-9a-f]{32}",
        "name": "Algolia API Key",
        "method": "GET",
        "url": "https://{APP_ID}-dsn.algolia.net/1/keys",
        "auth_type": "header",
        "header_name": "X-Algolia-API-Key",
        "impact": "Accès Algolia : Peut effectuer des recherches."
    },
    "twitter_bearer": {
        "pattern": r"A{22}[0-9a-zA-Z%]{80,}",
        "name": "Twitter Bearer Token",
        "method": "GET",
        "url": "https://api.twitter.com/1.1/account/verify_credentials.json",
        "auth_type": "bearer",
        "impact": "Accès Twitter : Lecture des données publiques."
    },
    "facebook_access": {
        "pattern": r"EAA[0-9A-Za-z]+",
        "name": "Facebook Access Token",
        "method": "GET",
        "url": "https://graph.facebook.com/me?access_token={KEY}",
        "auth_type": "url",
        "impact": "Accès Facebook : Lecture du profil utilisateur."
    },
    "bitly": {
        "pattern": r"R_[0-9a-f]{32}",
        "name": "Bitly Access Token",
        "method": "GET",
        "url": "https://api-ssl.bitly.com/v4/user",
        "auth_type": "bearer",
        "impact": "Accès Bitly : Peut créer des liens raccourcis."
    },
    "travis_ci": {
        "pattern": r"[0-9a-zA-Z]{22}",
        "name": "Travis CI Token",
        "method": "GET",
        "url": "https://api.travis-ci.org/repos",
        "auth_type": "header",
        "header_name": "Travis-API-Version",
        "header_value": "3",
        "auth_bearer": True,
        "impact": "Accès Travis CI : Peut gérer les builds."
    },
    "circle_ci": {
        "pattern": r"[0-9a-f]{40}",
        "name": "CircleCI Token",
        "method": "GET",
        "url": "https://circleci.com/api/v1.1/me?circle-token={KEY}",
        "auth_type": "url",
        "impact": "Accès CircleCI : Peut gérer les pipelines CI/CD."
    },
    "gitlab_pat": {
        "pattern": r"glpat-[0-9a-zA-Z_-]{20}",
        "name": "GitLab Personal Access Token",
        "method": "GET",
        "url": "https://gitlab.com/api/v4/projects?private_token={KEY}",
        "auth_type": "url",
        "impact": "Accès GitLab : Peut lire/modifier les repos."
    },
    "asana": {
        "pattern": r"0/[0-9a-f]{32}",
        "name": "Asana Access Token",
        "method": "GET",
        "url": "https://app.asana.com/api/1.0/users/me",
        "auth_type": "bearer",
        "impact": "Accès Asana : Peut gérer les tâches."
    },
    "zendesk": {
        "pattern": r"[0-9a-zA-Z]{40}",
        "name": "Zendesk API Token",
        "method": "GET",
        "url": "https://{subdomain}.zendesk.com/api/v2/users.json",
        "auth_type": "basic",
        "impact": "Accès Zendesk : Peut gérer les tickets support."
    },
    "pagerduty": {
        "pattern": r"[a-zA-Z0-9_-]{20}",
        "name": "PagerDuty API Token",
        "method": "GET",
        "url": "https://api.pagerduty.com/users",
        "auth_type": "bearer",
        "impact": "Accès PagerDuty : Peut gérer les incidents."
    },
    "shopify": {
        "pattern": r"shpat_[0-9a-zA-Z]{32}",
        "name": "Shopify Access Token",
        "method": "GET",
        "url": "https://{shop}.myshopify.com/admin/api/2023-01/shop.json",
        "auth_type": "header",
        "header_name": "X-Shopify-Access-Token",
        "impact": "Accès Shopify : Peut gérer la boutique."
    },
    "spotify": {
        "pattern": r"BQA[0-9a-zA-Z_-]{130,}",
        "name": "Spotify Access Token",
        "method": "GET",
        "url": "https://api.spotify.com/v1/me",
        "auth_type": "bearer",
        "impact": "Accès Spotify : Lecture du profil utilisateur."
    },
    "datadog": {
        "pattern": r"[0-9a-f]{32}",
        "name": "DataDog API Key",
        "method": "GET",
        "url": "https://api.datadoghq.com/api/v1/validate",
        "auth_type": "header",
        "header_name": "DD-API-KEY",
        "impact": "Accès DataDog : Peut envoyer des métriques."
    },
    "newrelic": {
        "pattern": r"NRAK-[0-9A-Z]{27}",
        "name": "New Relic API Key",
        "method": "POST",
        "url": "https://api.newrelic.com/graphql",
        "auth_type": "header",
        "header_name": "API-Key",
        "body": {"query": "{actor {user {email}}}"},
        "impact": "Accès New Relic : Peut lire les données APM."
    },
    "razorpay": {
        "pattern": r"rzp_live_[0-9a-zA-Z]{14}",
        "name": "Razorpay Live Key",
        "method": "GET",
        "url": "https://api.razorpay.com/v1/payments",
        "auth_type": "basic",
        "impact": "Accès critique : Peut lire les transactions de paiement."
    },
    "mapbox": {
        "pattern": r"pk\\.[0-9a-zA-Z_.-]{60,}",
        "name": "Mapbox Public Token",
        "method": "GET",
        "url": "https://api.mapbox.com/geocoding/v5/mapbox.places/paris.json?access_token={KEY}",
        "auth_type": "url",
        "impact": "Accès Mapbox : Peut utiliser les services de cartographie."
    },
    "salesforce": {
        "pattern": r"00D[0-9a-zA-Z]{15}",
        "name": "Salesforce Org ID",
        "method": None,
        "url": None,
        "auth_type": None,
        "impact": "Salesforce Org ID détecté (nécessite session pour validation)."
    },
    "instagram_access": {
        "pattern": r"IGQ[0-9a-zA-Z_-]{50,}",
        "name": "Instagram Access Token",
        "method": "GET",
        "url": "https://graph.instagram.com/me?fields=id,username&access_token={KEY}",
        "auth_type": "url",
        "impact": "Accès Instagram : Lecture du profil."
    },
    "linkedin": {
        "pattern": r"AQV[0-9a-zA-Z_-]{50,}",
        "name": "LinkedIn OAuth Token",
        "method": "GET",
        "url": "https://api.linkedin.com/v2/me",
        "auth_type": "bearer",
        "impact": "Accès LinkedIn : Lecture du profil professionnel."
    },
    "shodan": {
        "pattern": r"[0-9a-zA-Z]{32}",
        "name": "Shodan API Key",
        "method": "GET",
        "url": "https://api.shodan.io/api-info?key={KEY}",
        "auth_type": "url",
        "impact": "Accès Shodan : Peut rechercher des appareils exposés."
    },
    "wakatime": {
        "pattern": r"waka_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "name": "WakaTime API Key",
        "method": "GET",
        "url": "https://wakatime.com/api/v1/users/current?api_key={KEY}",
        "auth_type": "url",
        "impact": "Accès WakaTime : Lecture des statistiques de codage."
    },
    "amplitude": {
        "pattern": r"[0-9a-f]{32}",
        "name": "Amplitude API Key",
        "method": "GET",
        "url": "https://amplitude.com/api/2/events/list",
        "auth_type": "header",
        "header_name": "Authorization",
        "impact": "Accès Amplitude : Lecture des analytics produit."
    },
    "sonarcloud": {
        "pattern": r"[0-9a-f]{40}",
        "name": "SonarCloud Token",
        "method": "GET",
        "url": "https://sonarcloud.io/api/authentication/validate",
        "auth_type": "basic",
        "impact": "Accès SonarCloud : Lecture de l'analyse de code."
    },
    "buildkite": {
        "pattern": r"[0-9a-f]{40}",
        "name": "Buildkite Access Token",
        "method": "GET",
        "url": "https://api.buildkite.com/v2/access-token",
        "auth_type": "bearer",
        "impact": "Accès Buildkite : Peut gérer les builds CI."
    }
}


class KeyValidator:
    """
    Service universel de validation d'API keys.
    Détecte automatiquement le type de clé et effectue le test approprié.
    """
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    async def validate_key(self, key: str, service_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valide une clé API selon sa configuration.
        """
        if not service_config.get("url"):
            return {
                "valid": None,
                "service": service_config["name"],
                "impact": service_config["impact"],
                "note": "Validation impossible (nécessite des données supplémentaires)"
            }
        
        try:
            url = service_config["url"].format(KEY=key)
            method = service_config.get("method", "GET")
            auth_type = service_config.get("auth_type")
            
            headers = {}
            auth = None
            json_body = None
            
            # Configuration de l'authentification
            if auth_type == "basic":
                username = service_config.get("auth_user", key)
                password = "" if username == key else key
                auth = aiohttp.BasicAuth(username, password)
            
            elif auth_type == "bearer":
                headers["Authorization"] = f"Bearer {key}"
                # Pour Travis CI : bearer + header custom
                if service_config.get("auth_bearer"):
                    headers["Authorization"] = f"token {key}"
            
            elif auth_type == "header":
                header_name = service_config.get("header_name")
                header_value = service_config.get("header_value", key)
                headers[header_name] = header_value
                # Si c'est une clé API, l'ajouter aussi
                if header_value == key:
                    headers[header_name] = key
            
            # Body pour POST
            if method == "POST" and "body" in service_config:
                json_body = service_config["body"]
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    auth=auth,
                    json=json_body,
                    timeout=self.timeout
                ) as response:
                    
                    # Vérification de la validité
                    if response.status in [200, 201]:
                        content_type = response.headers.get("Content-Type", "")
                        
                        # Pour Google Maps, vérifier si c'est une vraie image
                        if "image" in content_type:
                            return {
                                "valid": True,
                                "service": service_config["name"],
                                "impact": service_config["impact"],
                                "status": response.status
                            }
                        
                        # Pour les APIs JSON
                        try:
                            data = await response.json()
                            # Certaines APIs retournent 200 avec un message d'erreur
                            if "error" in str(data).lower():
                                return {"valid": False, "service": service_config["name"], "impact": "Clé invalide ou restreinte."}
                            
                            return {
                                "valid": True,
                                "service": service_config["name"],
                                "impact": service_config["impact"],
                                "status": response.status
                            }
                        except:
                            return {
                                "valid": True,
                                "service": service_config["name"],
                                "impact": service_config["impact"],
                                "status": response.status
                            }
                    
                    elif response.status == 401:
                        return {"valid": False, "service": service_config["name"], "impact": "Clé invalide ou révoquée."}
                    
                    else:
                        return {"valid": False, "service": service_config["name"], "impact": f"Erreur API ({response.status})"}
        
        except asyncio.TimeoutError:
            return {"valid": False, "service": service_config["name"], "error": "Timeout"}
        except Exception as e:
            return {"valid": False, "service": service_config["name"], "error": str(e)}
    
    async def scan_html(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Scanne le HTML brut pour détecter des clés API dans:
        1. Les attributs HTML (data-sitekey, data-key, etc.)
        2. Les URLs de scripts (paramètres ?key=...)
        3. Le code JS inline (const apiKey = "...", etc.)
        """
        found_keys = []
        logger.info(f"🔍 KeyValidator: Scan HTML ({len(html_content)} chars)...")
        
        # 1. Scan des attributs HTML
        html_attr_patterns = [
            r'data-sitekey=["\']([^"\'>]+)["\']',  # Recaptcha
            r'data-key=["\']([^"\'>]+)["\']',
            r'data-api-key=["\']([^"\'>]+)["\']',
            r'apikey=["\']([^"\'>]+)["\']',
        ]
        
        for pattern in html_attr_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                found_keys.append({"source": "HTML_ATTR", "key": match})
        
        # 2. Scan des URLs de scripts (query params)
        script_url_patterns = [
            r'src=["\']([^"\'>]*[?&]key=([^&"\'>]+))',  # ?key=...
            r'src=["\']([^"\'>]*[?&]apikey=([^&"\'>]+))',  # ?apikey=...
        ]
        
        for pattern in script_url_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                # match[1] contient la valeur du paramètre
                found_keys.append({"source": "SCRIPT_URL", "key": match[1]})
        
        # 3. Scan du code JS inline
        js_inline_patterns = [
            r'["\']?apiKey["\']?\s*[:=]\s*["\']([^"\'>]{10,})["\']',
            r'["\']?api_key["\']?\s*[:=]\s*["\']([^"\'>]{10,})["\']',
            r'["\']?stripeKey["\']?\s*[:=]\s*["\']([^"\'>]{10,})["\']',
            r'["\']?STRIPE_KEY["\']?\s*[:=]\s*["\']([^"\'>]{10,})["\']',
        ]
        
        for pattern in js_inline_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                found_keys.append({"source": "JS_INLINE", "key": match})
        
        # Validation des clés trouvées
        validated_results = []
        logger.info(f"🔑 {len(found_keys)} clés potentielles trouvées")
        
        for item in found_keys:
            key = item["key"]
            source = item["source"]
            
            # Détection automatique du service
            matched_service = None
            for service_id, config in KEY_VALIDATORS.items():
                pattern = config["pattern"]
                if re.fullmatch(pattern, key):
                    matched_service = config
                    logger.info(f"✅ Service détecté ({source}): {config['name']}")
                    break
            
            if matched_service:
                result = await self.validate_key(key, matched_service)
                if result:
                    result["source"] = source
                    result["key_preview"] = f"{key[:10]}...{key[-4:]}"
                    validated_results.append(result)
                    
                    if result.get("valid"):
                        logger.warning(f"⚠️ CLÉ VALIDE DÉTECTÉE ({source}): {matched_service['name']}")
        
        return validated_results
    
    async def check_alerts(self, alerts: List[str]) -> List[Dict[str, Any]]:
        """
        Analyse une liste d'alertes JS Hunter et valide les clés trouvées.
        Détecte automatiquement le type de clé via regex matching.
        """
        validated_results = []
        logger.info(f"🔎 KeyValidator: Analyse de {len(alerts)} alertes...")
        
        for alert in alerts:
            # Extraction de la clé dans le message d'alerte
            if "(" in alert and ")" in alert:
                key = alert.split("(")[-1].split(")")[0]
                logger.info(f"🔑 Clé extraite: {key[:15]}...")
                
                # Détection automatique du service
                matched_service = None
                for service_id, config in KEY_VALIDATORS.items():
                    pattern = config["pattern"]
                    if re.fullmatch(pattern, key):
                        matched_service = config
                        logger.info(f"✅ Service détecté: {config['name']}")
                        break
                
                if matched_service:
                    result = await self.validate_key(key, matched_service)
                    if result:
                        result["original_alert"] = alert
                        result["key_preview"] = f"{key[:10]}...{key[-4:]}"
                        validated_results.append(result)
                        
                        if result.get("valid"):
                            logger.warning(f"⚠️ CLÉ VALIDE DÉTECTÉE: {matched_service['name']}")
                        else:
                            logger.info(f"ℹ️ Clé testée (invalide): {matched_service['name']}")
                else:
                    logger.info(f"⚠️ Type de clé inconnu: {key[:20]}")
        
        return validated_results
