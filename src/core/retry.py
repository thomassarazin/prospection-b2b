import time
import random
import logging
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from typing import Dict, Any, Optional, Callable

def http_request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: int = 20,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    log_fn: Optional[Callable[[str, str], None]] = None  # Backward compatibility
) -> requests.Response:
    """
    Fonction robuste pour appels HTTP avec retry exponentiel.

    Args:
        method: GET, POST, etc.
        url: URL cible
        max_retries: Nombre max de tentatives (défaut: 3)
        base_delay: Délai de base en secondes (défaut: 1s)
        timeout: Timeout par tentative (défaut: 20s)
        headers, params, json_data: Paramètres requests
        log_fn: Fonction de log optionnelle

    Returns:
        Response requests

    Raises:
        requests.RequestException: Si toutes les tentatives échouent
    """
    last_exception = None
    logger = logging.getLogger("prospection_pipeline")

    for attempt in range(max_retries + 1):
        try:
            logger.info(f"🔍 [DEBUG] http_request_with_retry - Tentative {attempt + 1}/{max_retries + 1}")
            if attempt > 0:
                logger.debug(f"🔄 Tentative {attempt + 1}/{max_retries + 1} pour {url}")

            logger.info(f"🔍 [DEBUG] Avant appel requests.{method.upper()} vers {url[:50]}...")

            # Appel HTTP
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                logger.info(f"🔍 [DEBUG] Appel requests.post avec timeout={timeout}s")
                response = requests.post(url, params=params, headers=headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")

            logger.info(f"🔍 [DEBUG] Après appel requests - Status: {response.status_code}")

            # Vérifier le statut
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limit
                logger.warning(f"⚠️ Rate limit atteint (429), retry dans {base_delay * (2 ** attempt)}s")
                raise HTTPError(f"Rate limit: {response.status_code}")
            elif 400 <= response.status_code < 500:  # Erreur client
                logger.error(f"❌ Erreur client {response.status_code}: {response.text[:1000]}")  # Augmenté pour voir l'erreur complète
                return response  # Pas de retry pour erreurs client
            else:  # Erreur serveur 5xx
                logger.warning(f"⚠️ Erreur serveur {response.status_code}, retry possible")
                raise HTTPError(f"Erreur serveur: {response.status_code}")

        except (Timeout, ConnectionError, HTTPError) as e:
            last_exception = e
            if attempt < max_retries:
                # Backoff exponentiel avec jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"⏳ Erreur {type(e).__name__}, retry dans {delay:.1f}s")
                time.sleep(delay)
            else:
                logger.error(f"💥 Échec définitif après {max_retries + 1} tentatives")
        except Exception as e:
            # Erreur inattendue
            logger.error(f"💥 Erreur inattendue: {e}")
            last_exception = e
            break

    # Si on arrive ici, toutes les tentatives ont échoué
    raise RequestException(f"Échec après {max_retries + 1} tentatives") from last_exception
