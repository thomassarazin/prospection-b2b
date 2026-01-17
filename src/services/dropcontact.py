import time
import logging
from typing import List, Dict, Any, Optional, Callable, Tuple
import os
from src.core.rate_limiter import RateLimiter
from src.core.retry import http_request_with_retry
from src.core.checkpoint import CheckpointManager
from src.config.settings import DROPCONTACT_BATCH_SIZE_MAX, DROPCONTACT_OVERSAMPLE
from src.services.search import enrich_missing_websites

# Instance locale du rate limiter (sera remplacée ou injectée si besoin)
_rate_limiter = RateLimiter()

def dropcontact_enrich_batch_polling(
    batch_prospects: List[Dict[str, Any]],
    dropcontact_headers: Dict[str, str],
    log_fn: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Version polling de l'enrichissement Dropcontact (fallback)."""
    if log_fn:
        log_fn(f"🔍 [DEBUG] ENTRÉE dropcontact_enrich_batch_polling avec {len(batch_prospects)} prospects", "DEBUG")

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
        if log_fn:
            log_fn(f"🔍 [DEBUG] Avant rate_limiter", "DEBUG")
        _rate_limiter.wait_if_needed("dropcontact")
        if log_fn:
            log_fn(f"🔍 [DEBUG] Avant http_request_with_retry (batch de {len(dropcontact_batch)} prospects)", "DEBUG")
        resp = http_request_with_retry(
            "POST",
            dropcontact_base_url,
            headers=dropcontact_headers,
            json_data={"data": dropcontact_batch, "siren": True, "language": "fr"},
            timeout=60
        )
        if log_fn:
            log_fn(f"🔍 [DEBUG] Après http_request_with_retry - Status: {resp.status_code}", "DEBUG")

        if resp.status_code != 200:
            # Détection spécifique de quota épuisé (401, 402, 403)
            if resp.status_code in [401, 402, 403]:
                error_msg = resp.text[:200] if resp.text else "Pas de détails"
                if log_fn:
                    log_fn(
                        f"🚫 [DROPCONTACT] QUOTA ÉPUISÉ OU ACCÈS REFUSÉ (code {resp.status_code})\n"
                        f"   Message API: {error_msg}\n"
                        f"   ⚠️ Vérifiez vos crédits Dropcontact restants",
                        "ERROR"
                    )
                # Lever une exception pour stopper la collecte
                raise Exception(f"DROPCONTACT_QUOTA_EXCEEDED: Code {resp.status_code} - {error_msg}")

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
            if log_fn:
                log_fn(f"🔍 [DEBUG] Avant rate_limiter pour GET polling", "DEBUG")
            _rate_limiter.wait_if_needed("dropcontact")
            if log_fn:
                log_fn(f"🔍 [DEBUG] Après rate_limiter, avant http_request_with_retry GET", "DEBUG")
            result_resp = http_request_with_retry(
                "GET", result_url, headers=dropcontact_headers, timeout=30
            )

            if log_fn:
                log_fn(f"🔍 [DEBUG] Status code reçu: {result_resp.status_code}", "DEBUG")

            if result_resp.status_code == 200:
                if log_fn:
                    log_fn(f"🔍 [DEBUG] Parsing JSON...", "DEBUG")
                result_data = result_resp.json()
                if log_fn:
                    log_fn(f"🔍 [DEBUG] Réponse Dropcontact: {result_data}", "DEBUG")
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
    except Exception as exc:  # noqa: BLE001
        if log_fn:
            log_fn(f"❌ Exception Dropcontact: {exc}", "ERROR")
        return []

def dropcontact_enrich_batch(
    batch_prospects: List[Dict[str, Any]],
    dropcontact_headers: Dict[str, str],
    log_fn: Optional[Callable[[str, str], None]] = None,
) -> List[Dict[str, Any]]:
    """Enrichissement Dropcontact via polling."""
    return dropcontact_enrich_batch_polling(batch_prospects, dropcontact_headers, log_fn)

# ---------------------------------------------------------------------------
# Helpers Dropcontact (Orchestration)
# ---------------------------------------------------------------------------

def dropcontact_enrich_loop(
    prospects_valides: List[Dict[str, Any]],
    target_count: int,
    dropcontact_headers: Dict[str, str],
    log_fn: Optional[Callable[[str, str], None]] = None,
    segment_name: str = "pme"
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Orchestre la boucle d'enrichissement par batch de 10-20.
    Retourne (qualifies, rejetes).
    """
    # Instance locale du checkpoint manager pour cette boucle
    _checkpoint_manager = CheckpointManager()
    
    stock_prequalifie = prospects_valides.copy()
    prospects_qualifies: List[Dict[str, Any]] = []
    prospects_pourris: List[Dict[str, Any]] = []

    # Facteur d'oversampling optionnel (1 = désactivé)
    OVERSAMPLE = max(1, DROPCONTACT_OVERSAMPLE)

    # REPRISE: Charger les prospects déjà enrichis depuis un checkpoint de batch précédent
    try:
        # Note: on charge sans campaign_id pour la flexibilité dans cette fonction helper
        checkpoint_data = _checkpoint_manager.load_last_checkpoint()
        if checkpoint_data and checkpoint_data.get("segment", "").startswith(f"{segment_name}_batch"):
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
        log_fn(f"🎯 [COMPLÉTION] Objectif: {target_count} prospects qualifiés (géré par Million Verifier)", "INFO")
        log_fn(f"📦 Stock préqualifié disponible: {len(stock_prequalifie)}", "INFO")

    batch_counter = 0  # Compteur de batches pour les checkpoints
    
    while stock_prequalifie:
        batch_counter += 1

        # Batch = ce qu'on a sous la main (cappé à 100)
        batch_size_optimal = min(len(stock_prequalifie), DROPCONTACT_BATCH_SIZE_MAX)

        batch_courant = stock_prequalifie[:batch_size_optimal]
        stock_prequalifie = stock_prequalifie[batch_size_optimal:]

        if log_fn:
            log_fn(
                f"\n🔄 [BATCH] Envoi de {len(batch_courant)} prospects à Dropcontact",
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
            try:
                if log_fn:
                    log_fn(f"🔍 [DEBUG] Avant appel dropcontact_enrich_batch (retry {retry})", "DEBUG")
                enrichis = dropcontact_enrich_batch(batch_courant, dropcontact_headers, log_fn)
                if log_fn:
                    log_fn(f"🔍 [DEBUG] Après appel dropcontact_enrich_batch - {len(enrichis)} résultats", "DEBUG")
                if enrichis:
                    break
            except Exception as e:
                if log_fn:
                    log_fn(f"❌ [Dropcontact] Erreur: {e}", "ERROR")
                if retry >= max_retries:
                    break  # Abandon après tous les retries

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
                    if isinstance(emails, str):
                        emails_all.append(emails)
                    else:
                        emails_all.append(str(emails))

            if has_email:
                prospect_final.pop("motif_exclusion", None)
                if emails_all:
                    prospect_final["emails_all"] = ";".join(sorted(list(set(emails_all))))
                    # Pour compatibilité avec le reste du pipeline, on met le meilleur email dans "email"
                    if "email" not in prospect_final or not prospect_final["email"] or isinstance(prospect_final["email"], list):
                         prospect_final["email"] = emails_all[0]
                
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
            log_fn(f"📊 Total qualifiés: {len(prospects_qualifies)} (avant valid email)", "INFO")
            log_fn(f"📦 Stock restant: {len(stock_prequalifie)}", "INFO")

        # CHECKPOINT: Sauvegarder après chaque batch Dropcontact
        try:
            _checkpoint_manager.save_checkpoint(
                prospects=prospects_qualifies,
                segment_name=f"{segment_name}_batch",
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

    if log_fn:
        log_fn(f"📊 [Dropcontact] {len(prospects_qualifies)} qualifiés / {len(prospects_pourris)} rejetés sur ce run", "INFO")

    return prospects_qualifies, prospects_pourris
