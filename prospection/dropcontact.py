#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module d'enrichissement via l'API Dropcontact."""

import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from requests.exceptions import RequestException

from .config import DROPCONTACT_BATCH_SIZE_MAX


def http_request_with_retry(
    method: str,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: int = 20,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> requests.Response:
    """Fonction robuste pour appels HTTP avec retry exponentiel.

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
    import random
    from requests.exceptions import Timeout, ConnectionError, HTTPError

    last_exception = None
    logger = logging.getLogger("prospection_pipeline")

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.debug(f"🔄 Tentative {attempt + 1}/{max_retries + 1} pour {url}")

            # Appel HTTP
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, params=params, headers=headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")

            # Vérifier le statut
            if response.status_code == 200:
                return response
            elif response.status_code == 429:  # Rate limit
                logger.warning(f"⚠️ Rate limit atteint (429), retry dans {base_delay * (2 ** attempt)}s")
                raise HTTPError(f"Rate limit: {response.status_code}")
            elif 400 <= response.status_code < 500:  # Erreur client
                logger.error(f"❌ Erreur client {response.status_code}: {response.text[:100]}")
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


def dropcontact_enrich_batch_polling(
    batch_prospects: List[Dict[str, Any]],
    dropcontact_headers: Dict[str, str],
    rate_limiter: Any,
    log_fn: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Version polling de l'enrichissement Dropcontact.

    Args:
        batch_prospects: Liste de prospects à enrichir
        dropcontact_headers: Headers HTTP avec clé API
        rate_limiter: Instance de RateLimiter
        log_fn: Fonction de logging optionnelle

    Returns:
        Liste des prospects enrichis
    """
    dropcontact_batch: List[Dict[str, Any]] = []
    for prospect in batch_prospects:
        dropcontact_batch.append(
            {
                "first_name": prospect.get("prenom", ""),
                "last_name": prospect.get("nom", ""),
                "company": prospect.get("entreprise_nom", ""),
                "num_siren": prospect.get("siren", ""),
            }
        )

    if not dropcontact_batch:
        return []

    dropcontact_base_url = "https://api.dropcontact.com/v1/enrich/all"
    try:
        rate_limiter.wait_if_needed("dropcontact")
        resp = http_request_with_retry(
            "POST",
            dropcontact_base_url,
            headers=dropcontact_headers,
            json_data={"data": dropcontact_batch, "siren": True, "language": "fr"},
            timeout=60
        )

        if resp.status_code != 200:
            if log_fn:
                log_fn(f"❌ Erreur Dropcontact: {resp.status_code}", "ERROR")
            return []

        data = resp.json()
        request_id = data.get("request_id")
        if not request_id:
            return []

        if log_fn:
            log_fn("🔄 [DROPCONTACT] Polling...", "DEBUG")

        # Exponential backoff: commence à 10s, augmente progressivement jusqu'à 60s max
        delays = [10, 15, 20, 30, 30, 45, 45, 60, 60, 60, 60, 60]  # Total: ~7 minutes max
        total_time = 0

        for attempt, delay in enumerate(delays, 1):
            if log_fn:
                log_fn(f"   ⏳ Tentative {attempt}/{len(delays)} - Attente {delay}s... (total: {total_time}s)", "DEBUG")
            time.sleep(delay)
            total_time += delay

            result_url = f"{dropcontact_base_url}/{request_id}"
            rate_limiter.wait_if_needed("dropcontact")
            result_resp = http_request_with_retry(
                "GET", result_url, headers=dropcontact_headers, timeout=30
            )

            if result_resp.status_code == 200:
                result_data = result_resp.json()
                if result_data.get("success"):
                    if log_fn:
                        log_fn(f"✅ [DROPCONTACT] Prêt en {total_time}s!", "DEBUG")
                    return result_data.get("data", [])
                elif log_fn:
                    log_fn(f"   📊 Pas encore prêt (attempt {attempt})", "DEBUG")
            elif log_fn:
                log_fn(f"   ❌ Erreur GET #{attempt}: {result_resp.status_code}", "ERROR")

        if log_fn:
            log_fn(f"⏰ [DROPCONTACT] Timeout après {total_time}s", "WARNING")
        return []
    except Exception as exc:
        if log_fn:
            log_fn(f"❌ Exception Dropcontact: {exc}", "ERROR")
        return []


def dropcontact_enrich_batch(
    batch_prospects: List[Dict[str, Any]],
    dropcontact_headers: Dict[str, str],
    rate_limiter: Any,
    log_fn: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Enrichissement Dropcontact via polling."""
    return dropcontact_enrich_batch_polling(batch_prospects, dropcontact_headers, rate_limiter, log_fn)


def dropcontact_enrich_loop(
    prospects_valides: List[Dict[str, Any]],
    target_count: int,
    dropcontact_headers: Dict[str, str],
    checkpoint_manager: Any,
    rate_limiter: Any,
    log_fn: Optional[Callable[[str, str], None]] = None,
    segment_name: str = "unknown",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Boucle d'enrichissement Dropcontact avec checkpointing.

    Args:
        prospects_valides: Liste de prospects préqualifiés
        target_count: Nombre cible de prospects qualifiés
        dropcontact_headers: Headers HTTP avec clé API
        checkpoint_manager: Instance de CheckpointManager
        rate_limiter: Instance de RateLimiter
        log_fn: Fonction de logging optionnelle
        segment_name: Nom du segment (pour checkpoints)

    Returns:
        Tuple (prospects_qualifiés, prospects_pourris)
    """
    stock_prequalifie = prospects_valides.copy()
    prospects_qualifies: List[Dict[str, Any]] = []
    prospects_pourris: List[Dict[str, Any]] = []

    # Facteur d'oversampling optionnel (1 = désactivé)
    OVERSAMPLE = max(1, int(os.getenv("DROPCONTACT_OVERSAMPLE", "1")))

    # REPRISE: Charger les prospects déjà enrichis depuis un checkpoint de batch précédent
    try:
        checkpoint_data = checkpoint_manager.load_last_checkpoint()
        if checkpoint_data and checkpoint_data.get("segment_name", "").startswith(f"{segment_name}_batch"):
            # On a un checkpoint d'un batch Dropcontact précédent
            existing_prospects = checkpoint_data.get("prospects", [])
            if existing_prospects:
                prospects_qualifies = existing_prospects.copy()
                if log_fn:
                    log_fn(f"♻️ [REPRISE] {len(prospects_qualifies)} prospects déjà enrichis chargés depuis checkpoint", "INFO")

                # Retirer du stock les prospects déjà traités (basé sur siren ou nom_complet)
                already_processed = set()
                for p in prospects_qualifies:
                    siren = p.get("siren", "")
                    nom = p.get("nom_complet", "")
                    if siren:
                        already_processed.add(siren)
                    elif nom:
                        already_processed.add(nom)

                # Filtrer le stock
                original_count = len(stock_prequalifie)
                stock_prequalifie = [
                    p for p in stock_prequalifie
                    if not (p.get("siren") in already_processed or p.get("nom_complet") in already_processed)
                ]
                if log_fn:
                    removed = original_count - len(stock_prequalifie)
                    log_fn(f"♻️ [REPRISE] {removed} prospects déjà traités retirés du stock", "INFO")
    except Exception as e:
        if log_fn:
            log_fn(f"⚠️ [REPRISE] Impossible de charger checkpoint batch: {e}", "WARNING")

    if log_fn:
        log_fn(f"🎯 [COMPLÉTION] Objectif: {target_count} prospects qualifiés", "INFO")
        log_fn(f"📦 Stock préqualifié disponible: {len(stock_prequalifie)}", "INFO")

    batch_counter = 0  # Compteur de batches pour les checkpoints
    while len(prospects_qualifies) < target_count and stock_prequalifie:
        batch_counter += 1
        manquants = target_count - len(prospects_qualifies)

        # 1) Batch = ce qu'on a sous la main (cappé à 100)
        batch_size_optimal = min(len(stock_prequalifie), DROPCONTACT_BATCH_SIZE_MAX)

        # 2) (optionnel) éviter de trop enrichir si on est proche de l'objectif
        if OVERSAMPLE > 1:
            batch_size_optimal = min(batch_size_optimal, manquants * OVERSAMPLE)

        batch_courant = stock_prequalifie[:batch_size_optimal]
        stock_prequalifie = stock_prequalifie[batch_size_optimal:]

        if log_fn:
            log_fn(
                f"\n🔄 [BATCH] Envoi de {len(batch_courant)} prospects à Dropcontact (manque: {manquants})",
                "INFO",
            )
            for prospect in batch_courant:
                log_fn(f"   → {prospect.get('nom_complet', 'Inconnu')} ({prospect.get('entreprise_nom', '')})", "INFO")

        enrichis: List[Dict[str, Any]] = []
        max_retries = 2
        for retry in range(max_retries + 1):
            if retry > 0 and log_fn:
                log_fn(
                    f"⚠️ [Dropcontact] Retry {retry}/{max_retries} pour un batch de {len(batch_courant)}",
                    "WARNING",
                )
                time.sleep(5)
            enrichis = dropcontact_enrich_batch(batch_courant, dropcontact_headers, rate_limiter, log_fn)
            if enrichis:
                break

        if not enrichis:
            if log_fn:
                log_fn("❌ Pas de résultats Dropcontact pour ce batch après retries", "WARNING")
            continue

        bons_batch: List[Dict[str, Any]] = []
        pourris_batch: List[Dict[str, Any]] = []

        # Vérification de sécurité : Dropcontact doit retourner le même nombre de résultats
        if len(enrichis) != len(batch_courant):
            if log_fn:
                log_fn(
                    f"⚠️ [DROPCONTACT] Mismatch: {len(enrichis)} résultats pour {len(batch_courant)} envoyés",
                    "WARNING"
                )

        for index, enrichi in enumerate(enrichis):
            # Sécurité : vérifier l'index avant d'accéder
            if index >= len(batch_courant):
                if log_fn:
                    log_fn(
                        f"❌ [DROPCONTACT] Index {index} hors limites (batch size: {len(batch_courant)})",
                        "ERROR"
                    )
                break

            prospect_original = batch_courant[index]

            # Vérification de cohérence par SIREN si disponible
            siren_original = prospect_original.get("siren", "")
            siren_enrichi = enrichi.get("siren", "")
            if siren_original and siren_enrichi and siren_original != siren_enrichi:
                if log_fn:
                    log_fn(
                        f"⚠️ [DROPCONTACT] SIREN mismatch à l'index {index}: "
                        f"attendu {siren_original}, reçu {siren_enrichi}",
                        "WARNING"
                    )

            prospect_final = {**prospect_original, **enrichi}

            emails = enrichi.get("email", [])
            linkedin = enrichi.get("linkedin", "")

            has_email = False
            emails_all: List[str] = []
            if emails:
                if isinstance(emails, list) and emails:
                    first = emails[0]
                    if isinstance(first, dict):
                        has_email = bool(first.get("email", ""))
                    else:
                        has_email = bool(first)
                    for item in emails:
                        if isinstance(item, dict):
                            value = item.get("email", "")
                            if value:
                                emails_all.append(value)
                        elif item:
                            emails_all.append(str(item))
                else:
                    has_email = bool(emails)
                    emails_all.append(str(emails))

            if has_email:
                prospect_final.pop("motif_exclusion", None)
                if emails_all:
                    prospect_final["emails_all"] = ";".join(dict.fromkeys(emails_all))
                if log_fn:
                    if linkedin:
                        log_fn(f"   ✅ {prospect_final.get('nom_complet', 'Inconnu')} - QUALIFIÉ", "INFO")
                    else:
                        log_fn(
                            f"   ⚠️ {prospect_final.get('nom_complet', 'Inconnu')} - LinkedIn manquant, mais email OK",
                            "WARNING",
                        )
                bons_batch.append(prospect_final)
            else:
                prospect_final = prospect_final.copy()
                prospect_final["motif_exclusion"] = "email manquant"
                pourris_batch.append(prospect_final)
                if log_fn:
                    log_fn(
                        f"   ❌ {prospect_final.get('nom_complet', 'Inconnu')} - POURRI (email manquant)",
                        "WARNING",
                    )

        prospects_qualifies.extend(bons_batch)
        prospects_pourris.extend(pourris_batch)

        if log_fn:
            log_fn(f"📊 Bilan batch: {len(bons_batch)} qualifiés, {len(pourris_batch)} pourris", "INFO")
            log_fn(f"📊 Total qualifiés: {len(prospects_qualifies)}/{target_count}", "INFO")
            log_fn(f"📦 Stock restant: {len(stock_prequalifie)}", "INFO")

        # CHECKPOINT: Sauvegarder après chaque batch Dropcontact
        try:
            checkpoint_manager.save_checkpoint(
                prospects=prospects_qualifies,
                segment_name=f"{segment_name}_batch{batch_counter}",
                progress_info={
                    "segment": segment_name,
                    "batch_number": batch_counter,
                    "qualified_count": len(prospects_qualifies),
                    "target_count": target_count,
                    "rejected_count": len(prospects_pourris),
                    "remaining_stock": len(stock_prequalifie)
                }
            )
        except Exception as e:
            if log_fn:
                log_fn(f"⚠️ Erreur sauvegarde checkpoint batch: {e}", "WARNING")

    return prospects_qualifies, prospects_pourris
