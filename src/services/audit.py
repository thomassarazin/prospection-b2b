import re
import json
import logging
import asyncio
from openai import OpenAI
import concurrent.futures
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.config.settings import DEEPINFRA_API_KEY
from src.config.pricing import calculate_cost
from src.config.prompts import AUDIT_PROMPTS
from src.core.retry import http_request_with_retry
from src.services.database import DatabaseService
from src.services.scraping import scrape_for_audit

logger = logging.getLogger(__name__)

class AuditService:
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.api_key = DEEPINFRA_API_KEY
        # Client OpenAI pour DeepInfra (Plus fiable que requests brut pour le streaming)
        self.openai_client = OpenAI(
            api_key=DEEPINFRA_API_KEY,
            base_url="https://api.deepinfra.com/v1/openai"
        )


    def _get_prompt_content(self, prompt_key: str) -> Dict[str, str]:
        """
        Récupère le prompt depuis la DB ou fallback sur la config locale.
        """
        # 1. Essai DB (Prompts dynamiques)
        try:
            if self.db and getattr(self.db, 'connected', False):
                db_prompt = self.db.prompts.find_one({"key": prompt_key}, maxTimeMS=2000)
                if db_prompt and "data" in db_prompt:
                    return db_prompt["data"]
        except Exception as e:
            logger.warning(f"⚠️ Erreur lors de la récupération du prompt '{prompt_key}' en DB: {e}. Fallback local.")
        
        # 2. Fallback Code (Prompts par défaut)
        return AUDIT_PROMPTS.get(prompt_key, {"role": "System", "content": "Error: Prompt not found"})

    def _parse_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Le Couperet 🪓 : Sépare la réflexion (CoT) du JSON.
        """
        delimiter = "@@@JSON_START@@@"
        thinking = ""
        json_data = {}

        if delimiter in raw_text:
            parts = raw_text.split(delimiter)
            thinking = parts[0].strip()
            # On prend tout ce qui est à droite comme candidat JSON
            if len(parts) > 1:
                json_part = parts[1].strip()
            else:
                json_part = "" 
        else:
            # Mode Rescue : On essaie de trouver le JSON quand même
            thinking = raw_text
            json_part = raw_text

        # --- ECRASAGE DU TEXTE PARASITE ---
        # 1. Nettoyage Markdown
        json_part = json_part.replace("```json", "").replace("```", "").strip()
        
        # 2. Nettoyage Commentaires JS (Code Models aiment mettre des // comments dans le JSON)
        # Regex pour enlever // comments mais pas http://
        json_part = re.sub(r'(?<!:)//.*', '', json_part)

        # 3. Extraction brute { ... } via Regex (plus robuste que find/rfind)
        # On cherche le premier { et le dernier }
        try:
            start_idx = json_part.find('{')
            end_idx = json_part.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_part = json_part[start_idx : end_idx + 1]
            else:
                raise ValueError("No braces found")

            # Tentative de parsing JSON
            json_data = json.loads(json_part)

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ Echec parsing JSON dans _parse_response: {e}")
            logger.error(f"🔍 RAW CONTENT (First 500): {raw_text[:500]}")
            logger.error(f"🔍 RAW CONTENT (Last 500): {raw_text[-500:]}")
            json_data = {"error": "Invalid JSON output from AI"}

        return {
            "thinking": thinking,
            "data": json_data
        }

    def _call_llm(self, model_id: str, system_prompt: str, user_content: str, image_b64: Optional[str] = None, timeout: int = 120, stream: bool = True) -> Dict[str, Any]:
        """
        Appel générique à DeepInfra via SDK OpenAI (Plus fiable pour streaming).
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        if image_b64:
            # Format Multimodal (Vision)
            messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": user_content}
                ]
            })
        else:
            # Format Texte Standard
            messages.append({"role": "user", "content": user_content})

        full_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        
        try:
            if stream:
                # Mode STREAMING - Le SDK gère nativement le format SSE
                response = self.openai_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2500,
                    stream=True
                )
                
                for event in response:
                    if event.choices[0].finish_reason:
                        # Fin du stream - récupérer usage si disponible
                        if hasattr(event, 'usage') and event.usage:
                            prompt_tokens = event.usage.prompt_tokens
                            completion_tokens = event.usage.completion_tokens
                    else:
                        # Chunk de contenu
                        delta_content = event.choices[0].delta.content
                        if delta_content:
                            full_content += delta_content
            else:
                # Mode NON-STREAMING - Pour Vision ou modèles lents
                response = self.openai_client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2500,
                    stream=False
                )
                
                full_content = response.choices[0].message.content or ""
                if response.usage:
                    prompt_tokens = response.usage.prompt_tokens
                    completion_tokens = response.usage.completion_tokens

            # Si 'usage' MANQUANT, on l'estime
            if prompt_tokens == 0:
                prompt_tokens = len(user_content) // 4
                completion_tokens = len(full_content) // 4

            # Parsing
            parsed_result = self._parse_response(full_content)
            
            # FinOps
            cost = calculate_cost(
                model_id, 
                prompt_tokens, 
                completion_tokens,
                cache_hits=0
            )

            return {
                "parsed": parsed_result,
                "raw_response": full_content,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost": cost
                },
                "model_id": model_id
            }

        except Exception as e:
            logger.error(f"💥 Exception during LLM call: {e}")
            return {"error": str(e)}

    def run_audit(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestre l'audit complet du prospect.
        """
        siren = prospect.get("siren")
        url = prospect.get("site_web") or prospect.get("website") # Support both keys
        if not url:
            return {"error": "No URL provided", "decision": "ERROR"}

        logger.info(f"🚀 Démarrage Audit Expert pour {prospect.get('nom_complet')} ({url})")

        # 1. SCRAPING (Sonde)
        scrape_data = scrape_for_audit(url)
        if not scrape_data or "error" in scrape_data:
            err_msg = scrape_data.get("error", "Unknown scraping error") if scrape_data else "No data returned"
            return {"error": f"Scraping failed: {err_msg}"}

        html_home = scrape_data["home"].get("html", "")
        combined_html = scrape_data.get("combined_html", html_home)  # Home + Contact/Login
        screenshot = scrape_data["home"].get("screenshot", "") # Base64 (now full-page!)
        js_alerts = scrape_data.get("security_alerts", [])
        
        # 1-bis. VALIDATION ACTIVE (KeyHacks)
        from src.services.validator import KeyValidator
        validator = KeyValidator()
        
        # Scan JS alerts (ancienne méthode)
        active_proofs = asyncio.run(validator.check_alerts(js_alerts))
        
        # Scan HTML brut des DEUX pages (nouvelle méthode - attributs, URLs, inline JS)
        html_scan_results = asyncio.run(validator.scan_html(combined_html))
        
        # Fusion des résultats
        active_proofs.extend(html_scan_results)
        
        # 2. RUN SÉQUENTIEL (Plus stable pour l'API)
        # Modèles
        MODEL_CODE = "Qwen/Qwen3-Coder-480B-A35B-Instruct-Turbo" # The Best
        MODEL_VISION = "Qwen/Qwen3-VL-235B-A22B-Instruct"

        # Prompts
        p_tech = self._get_prompt_content("security")
        p_ui = self._get_prompt_content("ui_code")
        p_vision = self._get_prompt_content("vision")
        
        
        # Inputs
        # Use combined HTML (Home + Contact/Login) for comprehensive analysis
        html_diet = combined_html[:50000]  # Analyze both pages
        input_tech = p_tech["content"].format(
            html_content=html_diet, 
            js_alerts=json.dumps(js_alerts),
            active_proofs=json.dumps(active_proofs)
        )
        input_ui = p_ui["content"].format(html_content=html_diet)
        input_vision = p_vision["content"] 

        results = {}

        # -- EXECUTION SÉQUENTIELLE (Avoid Rate Limit / Connection Error) --
        
        logger.info(f"🔒 [1/3] Audit SÉCURITÉ en cours ({MODEL_CODE})...")
        results["tech"] = self._call_llm(MODEL_CODE, p_tech["role"], input_tech, timeout=300, stream=True)
        
        logger.info(f"🎨 [2/3] Audit UX/UI en cours ({MODEL_CODE})...")
        results["ui"] = self._call_llm(MODEL_CODE, p_ui["role"], input_ui, timeout=300, stream=True)
        logger.info(f"👁️ [3/3] Audit VISION en cours ({MODEL_VISION})...")
        if screenshot:
             # DEBUG: Sauvegarder l'image pour vérification utilisateur
             try:
                 import base64
                 with open(f"debug_screenshot_{siren}.jpg", "wb") as f:
                     f.write(base64.b64decode(screenshot))
                 logger.info(f"📸 Screenshot sauvegardé pour vérification: debug_screenshot_{siren}.jpg")
             except Exception as e:
                 logger.warning(f"⚠️ Echec sauvegarde screenshot debug: {e}")

             results["vision"] = self._call_llm(MODEL_VISION, p_vision["role"], input_vision, image_b64=screenshot, timeout=300, stream=False)
        else:
             logger.warning("⚠️ Pas de screenshot, Audit Vision annulé")
             results["vision"] = {"parsed": {"data": {}, "thinking": "No screenshot available"}}

        # 3. SYNTHESE (Le Mentor) - OPTIMISATION INPUT
        p_synth = self._get_prompt_content("synthesis")
        
        # On n'envoie PAS le 'Thinking' brut (trop long/verbeux pour rien), on envoie le JSON structuré + un résumé
        # Cela réduit drastiquement la charge pour le Mentor et évite le Timeout.
        def summary_audit(res):
            parsed = res.get("parsed", {})
            data = parsed.get("data", {})
            brief = parsed.get("technical_brief", "")
            return json.dumps({"data": data, "technical_brief": brief}, ensure_ascii=False, indent=2)

        input_synth = p_synth["content"].format(
            audit_tech_cot=summary_audit(results["tech"]),
            audit_ux_code_cot=summary_audit(results["ui"]),
            audit_vision_cot=summary_audit(results["vision"])
        )

        logger.info("🧠 Lancement de la Synthèse (Mentor) [Input Optimisé]...")
        # Timeout augmenté spécifiquement pour la synthèse
        synth_result = self._call_llm(MODEL_CODE, p_synth["role"], input_synth, timeout=180)

        # 4. AGREGATION & SAVE
        total_cost = (
            results["tech"].get("usage", {}).get("cost_usd", 0) +
            results["ui"].get("usage", {}).get("cost_usd", 0) +
            results["vision"].get("usage", {}).get("cost_usd", 0) +
            synth_result.get("usage", {}).get("cost_usd", 0)
        )

        final_audit = {
            "siren": siren,
            "url": url,
            "timestamp": datetime.now(),
            "total_cost_usd": round(total_cost, 4),
            "step_scraping": {
                "security_alerts": js_alerts, # INDISPENSABLE POUR LE FRONT
                "html_sample": html_diet,
                "screenshot_sample": screenshot[:200] if screenshot else None # Juste un indicateur
            },
            "active_proofs": active_proofs,
            "step_tech": results["tech"],
            "step_ui_code": results["ui"],
            "step_vision": results["vision"],
            "step_synthesis": synth_result,
            # Raccourcis pour le dashboard
            "decision": synth_result.get("parsed", {}).get("data", {}).get("decision", "PENDING"),
            "score_priority": synth_result.get("parsed", {}).get("data", {}).get("priority_score", 0),
        }

        # Sauvegarde MongoDB
        try:
            if self.db and getattr(self.db, 'connected', False):
                self.db.audits.insert_one(final_audit)
                logger.info(f"✅ Audit sauvegardé en DB pour {siren}.")
            else:
                logger.warning(f"⚠️ DB non connectée ou absente, audit non sauvegardé pour {siren}.")
        except Exception as e:
            logger.error(f"❌ Erreur lors de la sauvegarde MongoDB pour {siren}: {e}")

        logger.info(f"✅ Audit terminé pour {siren}. Coût: ${final_audit['total_cost_usd']}")

        return final_audit
