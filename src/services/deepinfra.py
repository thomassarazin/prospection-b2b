import time
import json
import logging
from typing import Optional, Callable, Dict, Any

from src.core.retry import http_request_with_retry
from src.config.settings import DEEPINFRA_API_KEY, DEEPINFRA_MODEL, DEEPINFRA_URL
from src.config.templates import TEMPLATES_ICEBREAKER_NAF, TEMPLATES_AUTOMATIONS_NAF

def try_metadata_fallback(
    prospect: Dict[str, Any],
    deepinfra_api_key: str,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> bool:
    """
    Fallback intelligent basé sur le code NAF (template pré-défini).
    """
    # Récupérer le code NAF et le normaliser (enlever le point si présent)
    code_naf = prospect.get("code_naf", "")
    if not code_naf:
        if log_fn:
            log_fn(f"⚠️ {prospect.get('nom_complet', 'Inconnu')} - Pas de code NAF, impossible d'utiliser le template", "WARNING")
        return False

    # Normaliser (enlever le point : "70.21Z" → "7021Z")
    code_naf_normalise = code_naf.replace(".", "")

    # Chercher le template correspondant
    template = TEMPLATES_ICEBREAKER_NAF.get(code_naf_normalise)
    if not template:
        if log_fn:
            log_fn(f"⚠️ {prospect.get('nom_complet', 'Inconnu')} - Pas de template pour le code NAF {code_naf_normalise}", "WARNING")
        return False

    # Appliquer le template icebreaker
    prospect["icebreaker_a"] = template["activite_principale"]
    prospect["icebreaker_b"] = template["operations_concretes"]
    prospect["icebreaker_c"] = template["valeur_humaine"]
    prospect["icebreaker_d"] = template["description_entreprise"]
    prospect["icebreaker_origin"] = "template_naf"

    # Appliquer également le template d'automatisations correspondant
    template_automation = TEMPLATES_AUTOMATIONS_NAF.get(code_naf_normalise)
    if template_automation:
        prospect["automation_list"] = template_automation
        prospect["automation_origin"] = "template_naf"
    else:
        prospect["automation_list"] = ""
        prospect["automation_origin"] = "none"

    if log_fn:
        log_fn(f"✅ {prospect.get('nom_complet', 'Inconnu')} - Icebreaker + automatisations via template NAF {code_naf_normalise}", "INFO")

    return True

def extract_detailed_summary_with_deepinfra(
    website_content: str,
    deepinfra_api_key: str,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> Optional[str]:
    """PROMPT 1 : Génère un résumé TRÈS détaillé de l'entreprise"""
    system_prompt = """Tu es un analyste d'entreprise expert avec un ton simple et direct (pas de jargon corporate).

À partir du contenu du site web fourni, crée un résumé TRÈS DÉTAILLÉ, structuré et factuel de cette entreprise.

Le résumé doit inclure IMPÉRATIVEMENT (si les informations sont présentes) :

1. **Activité principale** : Que fait exactement cette entreprise ? Dans quel secteur ? Quelle est son histoire si mentionnée ?
2. **Services/Produits** : Détaille TOUS les services ou produits proposés, leurs spécificités
3. **Positionnement** : Quelle est sa particularité, son approche, sa méthodologie, sa différence ?
4. **Clients cibles** : À qui s'adresse-t-elle ? (particuliers, entreprises, secteur spécifique, taille)
5. **Valeurs/Mission** : Quelles valeurs humaines ou professionnelles met-elle en avant ? Quelle est sa vision ?
6. **Éléments opérationnels** : Quels sont les process, étapes, outils, technologies mentionnés ? Comment travaille-t-elle ?
7. **Équipe/Expertise** : Si mentionné, qui sont les fondateurs, quelle est leur expertise ?
8. **Réalisations/Clients** : Exemples de projets, clients, partenaires si mentionnés
9. **Points de friction** : Toutes les tâches répétitives, processus chronophages ou contraintes qui semblent prendre du temps/énergie.

IMPORTANT - ANALYSE PSYCHOLOGIQUE :
En plus du résumé factuel, identifie et ajoute à la fin (séparé par "---") :

10. **FRUSTRATION PRINCIPALE** : Quelle est LA principale source de stress/frustration/fatigue dans leur quotidien ? (Pas d'argent, pas de chiffres - juste l'émotion brute : "passer ses vendredis soirs à...", "jongler sans cesse entre...", "perdre le fil de...")

11. **BIAIS PSYCHOLOGIQUE** : Quel biais psychologique humain peut-on toucher ? (FOMO de rater une opportunité, peur de perdre du temps, besoin de contrôle, culpabilité de ne pas suivre, anxiété du chaos, fatigue décisionnelle)

12. **ANGLE ÉMOTIONNEL** : Comment pitcher une solution d'automatisation pour toucher l'émotion, pas la raison ? (Récupérer ses soirées, arrêter de jongler, reprendre le contrôle, retrouver sa sérénité, ne plus oublier, dormir tranquille)

RÈGLES STRICTES :
- Ton neutre et factuel pour le résumé, humain et émotionnel pour l'analyse psychologique
- Base-toi UNIQUEMENT sur le contenu fourni, pas d'invention
- Sois TRÈS précis et concret, évite les généralités
- N'hésite pas à faire un résumé de 2000-3000 caractères si le contenu le justifie
- JAMAIS de chiffres, JAMAIS d'argent, JAMAIS de ROI - on touche l'humain, pas le comptable
- Structure en paragraphes clairs

FORMAT DE SORTIE :
[Résumé factuel détaillé]

---
FRUSTRATION PRINCIPALE: [description émotionnelle concrète]
BIAIS: [nom du biais + explication courte]
ANGLE: [comment pitcher émotionnellement]"""

    try:
        headers = {
            "Authorization": f"Bearer {deepinfra_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": DEEPINFRA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": website_content}
            ],
            "temperature": 0.2,
            "max_tokens": 2000
        }

        response = http_request_with_retry(
            "POST",
            DEEPINFRA_URL,
            headers=headers,
            json_data=payload,
            timeout=120,
            max_retries=2
        )

        if response.status_code == 429:
            if log_fn:
                log_fn("🚨 [DeepInfra Prompt1] Rate limit - pause 10s", "WARNING")
            time.sleep(10)
            response = http_request_with_retry(
                "POST",
                DEEPINFRA_URL,
                headers=headers,
                json_data=payload,
                timeout=120,
                max_retries=1
            )

        if response.ok:
            summary = response.json()['choices'][0]['message']['content'].strip()
            refusal_keywords = [
                "il semble que le contenu", "ne permet pas de créer", "il n'est pas possible",
                "informations insuffisantes", "contenu se limite", "pas d'informations spécifiques",
                "je n'ai pas d'information", "ne contient pas d'informations"
            ]
            summary_lower = summary.lower()
            if any(keyword in summary_lower for keyword in refusal_keywords):
                if log_fn:
                    log_fn(f"⚠️ [DeepInfra Prompt1] Résumé refusé (contenu insuffisant détecté)", "WARNING")
                return None

            if log_fn:
                log_fn(f"✅ [DeepInfra Prompt1] Résumé généré ({len(summary)} chars)", "DEBUG")
            return summary
        else:
            if log_fn:
                log_fn(f"❌ [DeepInfra Prompt1] Erreur HTTP {response.status_code}", "ERROR")
            return None

    except Exception as e:
        if log_fn:
            log_fn(f"💥 [DeepInfra Prompt1] Exception: {e}", "ERROR")
        return None

def extract_abc_from_summary_with_deepinfra(
    summary: str,
    deepinfra_api_key: str,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> Optional[Dict[str, str]]:
    """PROMPT 2 : Extrait A/B/C à partir du résumé détaillé"""
    system_prompt = """À partir du résumé d'entreprise que je vais te fournir, extrait EXACTEMENT trois variables.

Ces variables doivent pouvoir être insérées telles quelles dans les phrases suivantes :
« Vous bossez sur [activite_principale]. »
« Que ce soit [operations_concretes], ça prend énormément de temps… »
« Vous valorisez [valeur_humaine]. »

Définitions STRICTES :

**activite_principale** = un groupe nominal court décrivant l'activité principale de l'entreprise.
Il doit pouvoir suivre directement « Vous bossez sur ».
Formes attendues : « la gestion locative », « la création de contenus », « la rénovation de biens », « la communication digitale ».
Pas de verbe, pas de phrase complète. Maximum 7 mots.

**operations_concretes** = une chaîne unique contenant 1 à 3 contraintes opérationnelles concrètes (ce qui leur fait perdre du temps/énergie et qu'on pourrait automatiser).
Formulés comme des groupes nominaux (sans verbe conjugué) qui évoquent les process lourds, allers-retours, tâches répétitives ou manuelles.
Les éléments doivent être séparés par des virgules, avec « et » avant le dernier.
Exemples :
- « plusieurs formulaires de demande, les validations internes et les échanges clients »
- « la gestion des dossiers, les relances administratives et les demandes entrantes »
- « les étapes de suivi, la production de contenus variés et la coordination interne »
Chaque élément doit faire sentir que c'est manuel, répétitif ou chronophage (idées d'automatisation). Aucun verbe conjugué. Maximum 15 mots au total.

**valeur_humaine** = une valeur humaine explicitement mentionnée dans le résumé, formulée AVEC son article défini.
Formes attendues : « la proximité », « l'accompagnement », « la pédagogie », « la transparence », « l'écoute ».
Pas d'adjectif seul. Pas de phrase. Maximum 5 mots.

RÈGLES STRICTES :
- Base-toi UNIQUEMENT sur le résumé fourni
- Pas d'invention, pas d'interprétation
- Ton simple, naturel (pas de jargon B2B super formel)
- Si le résumé parle principalement de cookies, erreurs, login, wix, disclaimers → retourne {"activite_principale": "", "operations_concretes": "", "valeur_humaine": ""}
- Si une variable ne peut pas être extraite avec confiance, retourne "" pour cette variable
- REJETTE les résumés de mauvaise qualité (pas d'infos métier réelles)

IMPORTANT : Retourne UNIQUEMENT du JSON valide.

Format EXACT de sortie :
{
"activite_principale": "...",
"operations_concretes": "...",
"valeur_humaine": "..."
}"""

    try:
        headers = {
            "Authorization": f"Bearer {deepinfra_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": DEEPINFRA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Voici le résumé de l'entreprise :\n\n{summary}"}
            ],
            "temperature": 0.3,
            "max_tokens": 1500
        }

        response = http_request_with_retry(
            "POST",
            DEEPINFRA_URL,
            headers=headers,
            json_data=payload,
            timeout=120,
            max_retries=2
        )

        if response.status_code == 429:
            if log_fn:
                log_fn("🚨 [DeepInfra Prompt2] Rate limit - pause 10s", "WARNING")
            time.sleep(10)
            response = http_request_with_retry(
                "POST",
                DEEPINFRA_URL,
                headers=headers,
                json_data=payload,
                timeout=120,
                max_retries=1
            )

        if response.ok:
            response_data = response.json()
            content = response_data['choices'][0]['message']['content']
            
            # Nettoyer markdown
            content_clean = content.strip()
            if content_clean.startswith("```json"):
                content_clean = content_clean[7:]
            if content_clean.startswith("```"):
                content_clean = content_clean[3:]
            if content_clean.endswith("```"):
                content_clean = content_clean[:-3]
            content_clean = content_clean.strip()

            parsed = json.loads(content_clean)
            if "activite_principale" in parsed and "operations_concretes" in parsed and "valeur_humaine" in parsed:
                if log_fn:
                    log_fn(f"✅ [DeepInfra Prompt2] Variables icebreaker extraites", "DEBUG")
                return parsed
            else:
                if log_fn:
                    log_fn("⚠️ [DeepInfra Prompt2] Variables icebreaker manquantes", "WARNING")
                return None
        else:
            if log_fn:
                log_fn(f"❌ [DeepInfra Prompt2] Erreur HTTP {response.status_code}", "ERROR")
            return None

    except Exception as e:
        if log_fn:
            log_fn(f"💥 [DeepInfra Prompt2] Exception: {e}", "ERROR")
        return None

def generate_automation_list_with_deepinfra(
    company_description: str,
    code_naf: str,
    deepinfra_api_key: str,
    log_fn: Optional[Callable[[str, str], None]] = None
) -> Optional[str]:
    """PROMPT 3 : Génère une liste de 3 automatisations concrètes"""
    system_prompt = """Tu analyses comme un expert en automatisation et développement qui comprend vraiment les vrais problèmes des entrepreneurs.

Tu ÉCRIS avec le TON BIGXBANG : vif, clair, joueur mais expert. Un mix rare entre expertise technique sans froideur, énergie créative sans bullshit, et simplicité sans naïveté.

CONTEXTE : Cette liste vient juste après la phrase "Voici des exemples de choses qui pourraient être mises en place pour rendre le quotidien de votre boîte plus agréable et libérer du temps à vos équipes pour ce qui compte vraiment :"

Génère une liste de **3 automatisations concrètes et réalistes** à partir de la description d'entreprise fournie.

STRUCTURE DE COMPLEXITÉ OBLIGATOIRE (effet ancrage de valeur) :
- **Automatisation 1** : SIMPLE - Résout un petit point de friction quotidien. Point d'entrée accessible.
- **Automatisation 2** : INTERMÉDIAIRE - Résout un vrai problème structurel du secteur. Combine plusieurs sources/process. C'est le SWEET SPOT à vendre.
- **Automatisation 3** : COMPLEXE - Solution complète quasi-propriétaire qui résout le problème de fond. Peut être un mini-outil dédié. Ancre la valeur.

RECETTE D'ÉCRITURE BIGXBANG (CRITICAL) :
1. STRUCTURE : 2-3 phrases explicatives par automatisation. Pas de phrase interminable.
2. RYTHME : Court. Direct. Impact.
3. TON : Expert mais accessible. Explicatif sans infantiliser.
4. CLARTÉ : Le client doit comprendre concrètement ce que fait l'automatisation.

INTERDICTIONS ABSOLUES :
- JAMAIS de chiffres, d'argent, de ROI, de temps gagné
- JAMAIS de tirets au milieu d'une phrase pour séparer problème/solution
- JAMAIS de formules robotiques type "Arrêtez de X - Faites Y"
- JAMAIS de promesses vagues
- JAMAIS mentionner la techno ("API", "python")

Format de sortie :
- Liste markdown avec tirets simples (-)
- 2-3 phrases maximum par automatisation
- Pas de numérotation
- Commence directement par le premier tiret

Retourne UNIQUEMENT la liste markdown, rien d'autre."""

    user_prompt = f"""Voici la description de l'entreprise :

{company_description}

Code NAF : {code_naf}

Génère 3 automatisations concrètes et pertinentes pour cette entreprise."""

    try:
        headers = {
            "Authorization": f"Bearer {deepinfra_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": DEEPINFRA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        response = http_request_with_retry(
            "POST",
            DEEPINFRA_URL,
            headers=headers,
            json_data=payload,
            timeout=120,
            max_retries=2
        )

        if response.status_code == 429:
            if log_fn:
                log_fn("🚨 [DeepInfra Automation] Rate limit - pause 10s", "WARNING")
            time.sleep(10)
            response = http_request_with_retry(
                "POST",
                DEEPINFRA_URL,
                headers=headers,
                json_data=payload,
                timeout=120,
                max_retries=1
            )

        if response.ok:
            automation_list = response.json()['choices'][0]['message']['content'].strip()
            # Post-processing : remplacer tous les tirets longs/cadratins par des tirets simples
            automation_list = automation_list.replace('–', '-')
            automation_list = automation_list.replace('—', '-')
            automation_list = automation_list.replace('‑', '-')

            if automation_list.count('-') < 2:
                if log_fn:
                    log_fn(f"⚠️ [DeepInfra Automation] Liste invalide (pas assez de tirets)", "WARNING")
                return None
            return automation_list
        else:
            if log_fn:
                log_fn(f"❌ [DeepInfra Automation] Erreur HTTP {response.status_code}", "ERROR")
            return None

    except Exception as e:
        if log_fn:
            log_fn(f"💥 [DeepInfra Automation] Exception: {e}", "ERROR")
        return None
