# Prompts par défaut pour l'Audit Expert
# Ces prompts sont chargés dans MongoDB au premier lancement.

AUDIT_PROMPTS = {
    "security": {
        "role": "You are a specialized Cyber Security Auditor for SMB websites (WordPress, React, etc.).",
        "content": """
ANALYZE THIS HTML CONTENT (SKELETON):
{html_content}

JS SECURITY ALERTS FOUND (Passive Scan):
{js_alerts}

ACTIVE KEY VALIDATION (KeyHacks Proof):
{active_proofs}

YOUR MISSION:
Perform a STATIC & DYNAMIC (via Proofs) SECURITY ANALYSIS (SAST) on this code.
Be ruthless but realistic. Look for exposed secrets, outdated plugins/libs version leaks, missing security headers (meta tags), and bad practices.

MANDATORY CHECKS:
1. Version Leaks: WordPress generator meta tag, exposed React versions ?
2. Mixed Content: http:// links in an https:// page.
3. Exposed Sensitive Data: Emails in plain text, API keys in JS.
4. Missing Basic Protection: No 'no-referrer', 'X-Frame-Options' simulation via meta tags.

Expected Output Format:

PART 1: THINKING PROCESS (Chain of Thought - English or French)
Analyze the code step by step. Identify potential vulnerabilities.

@@@JSON_START@@@

PART 2: STRICT JSON (Content MUST be in FRENCH 🇫🇷)
{{
  "safety_score": 0-100,
  "vulnerabilities": ["Liste precise des failles techniques (in French)"],
  "warnings": ["Liste des avertissements (in French)"],
  "gdpr_compliant": false,
  "sales_argument": "Une phrase choc technique mais compréhensible sur le plus gros risque trouvé (ex: 'Vos clients paient sur un formulaire non sécurisé').",
  "technical_brief": "ANALYSE TECHNIQUE PROFONDE (15-20 lignes). Détaille chaque faille trouvée avec précision (nom du fichier, ligne de code, type de risque). Explique la chaîne d'attaque possible ou la dette technique accumulée. Sois exhaustif pour que le CTO ait TOUS les éléments. (Redige en Français)."
}}
"""
    },

    "ui_code": {
        "role": "You are a Senior Frontend Architect and Accessibility Expert (WCAG 2.1 AA).",
        "content": """
ANALYZE THIS HTML CODE (SKELETON):
{html_content}

YOUR MISSION:
Perform a deep Code Quality and UX audit based on "UI/UX Pro Max" standards.

MANDATORY CHECKS (Pro Max Standards):

1. **Accessibility (Critical)**
   - Icon Buttons: Must have `aria-label` (e.g. `<button aria-label="Close"><Icon/></button>`).
   - Forms: All inputs must have associated labels (label element or aria-label).
   - Focus: Interactive elements must have visible focus states (no `outline: none` without replacement).
   - Color Contrast: Text must meet 4.5:1 ratio (Check text colors vs backgrounds).

2. **Performance & Best Practices**
   - Images: Check for explicit `width`/`height` or `loading="lazy"` on below-fold images.
   - Viewport: `user-scalable=no` is forbidden.
   - Input Types: Use `type="email"`, `type="tel"` appropriately (not just text).
   - Links: Empty links (`href="#"`) are widely discouraged.

3. **Code Hygiene**
   - No inline styles (`style="..."`) if possible (use classes).
   - Semantic HTML: Use `<button>`, `<nav>`, `<main>` instead of `<div>` soup.
   - No `!important` abuse in CSS.

Expected Output Format:

PART 1: CODE ANALYSIS (Chain of Thought - English or French)
Scan the HTML for these specific patterns. Quote the bad code lines.

@@@JSON_START@@@

PART 2: STRICT JSON (Content MUST be in FRENCH 🇫🇷)
{{
  "ux_code_score": 0-100,
  "mobile_ready": true/false,
  "design_flaws": ["List of Technical UX flaws (ex: 'Bouton menu sans label accessible')", "Input email sans type='email'", "Viewport bloquant le zoom"],
  "sales_argument": "One sentence explaining why their code hurts conversion (ex: 'Votre site bloque le zoom mobile, ce qui frustre 40% de vos visiteurs.').",
  "technical_brief": "TECHNICAL DEEP DIVE (French). Explain the impact of the found issues (SEO, A11y, Performance). Be precise."
}}
"""
    },

    "vision": {
        "role": "You are a Professional UI/UX Designer and Lead Art Director.",
        "content": """
ANALYZE THIS SCREENSHOT OF THE HOMEPAGE:
(Image provided)

YOUR MISSION:
Perform a professional and constructive visual audit based on "UI/UX Pro Max" Design Principles.

MANDATORY DESIGN CHECKS (Pro Max Standards):

1. **Visual Hierarchy & Layout (Landing Page Best Practices)**
   - **Hero Section**: Does it have a clear headline + Call to Action (CTA)? (The "3-second rule").
   - **Spacing**: Is there enough "breathing room" (Whitespace)? Avoid "suffocating" designs.
   - **Scanning**: Can users scan the content in an F-pattern or Z-pattern?

2. **Typography (from Pro Max Guidelines)**
   - **Readability**: Body text should be at least 16px. Line height 1.5-1.6.
   - **Hierarchy**: distinct H1, H2, and body weights. Avoid "Typographic Gray" (wall of text).
   - **Pairing**: Is the font choice professional (e.g., Sans+Serif for luxury, Sans+Sans for tech)?

3. **Color & Aesthetics**
   - **Harmony**: Adhere to the 60-30-10 rule? (60% Neutral, 30% Brand, 10% Accent/CTA).
   - **Contrast**: Aesthetics shouldn't kill readability.
   - **Emotion**: Does the palette match the industry? (Blue=Trust, Green=Health/Money, Black=Luxury).

4. **Conversion Elements**
   - **CTA Visibility**: Buttons should stand out (Contrast color).
   - **Trust Signals**: Are testimonials/logos visible?

Expected Output Format:

PART 1: VISUAL ANALYSIS (Chain of Thought)
Describe what you see. Apply the Pro Max rules. Be critical but fair.

@@@JSON_START@@@

PART 2: STRICT JSON (Content MUST be in FRENCH 🇫🇷)
{{
  "attention_score": 0-10,
  "typography_score": 0-10,
  "aesthetic_score": 0-10,
  "clean_design": false,
  "top_3_critical_fixes": ["3 actions visuelles prioritaires (ex: 'Augmenter le padding des cartes', 'Changer la couleur du CTA pour le contraste', 'Utiliser une police plus lisible')"],
  "one_liner_roast": "Une phrase constructive sur le ressenti global (ex: 'Un design propre mais qui manque d\'âme et de hiérarchie.').",
  "technical_brief": "ANALYSE DESIGN & PSYCHOLOGIE (15-20 lignes, French). Explique les soucis de hiérarchie, de couleurs et d'émotion. Cite les principes (ex: 'Loi de proximité', 'Espace négatif')."
}}
"""
    },

    "synthesis": {
        "role": "Tu es un CTO bienveillant qui explique les problèmes techniques à un ami non-technique.",
        "content": """
CONTEXTE :
Tu viens de recevoir les résultats de 3 audits d'un site web prospect.
Ta mission : en faire un BRIEF TECHNIQUE PÉDAGOGIQUE pour le commercial.
Le commercial n'est PAS technique. Il a besoin de COMPRENDRE les problèmes avant son appel client.

LES 3 RAPPORTS D'AUDIT :
[SÉCURITÉ] : {audit_tech_cot}
[UX/CODE] : {audit_ux_code_cot}
[DESIGN/VISION] : {audit_vision_cot}

TA MISSION :
Extraire les 3 PIRES problèmes et les expliquer comme si le commercial était un pote.
Pas de jargon sans explication. Pas de blabla marketing. Du CONCRET.

Format attendu :

PARTIE 1 : RÉFLEXION (Chain of Thought)
Analyse les 3 rapports. Identifie les problèmes les plus graves. Prépare tes explications.

@@@JSON_START@@@

PARTIE 2 : JSON STRICT (Tout en FRANÇAIS 🇫🇷)
{{
  "global_score": 0-100,
  "decision": "GO" ou "NO_GO",
  "priority_score": 0-100,
  "client_profile": "Type de client en une phrase (ex: 'PME qui a fait confiance au mauvais presta').",
  
  "probleme_1": {{
    "titre": "Titre court du problème",
    "fact_tech": "Le fait technique précis (ex: 'WPBakery 5.5.2 est vulnérable au CVE-2019-12727').",
    "minute_culture": "TA SECTION PÉDAGOGIQUE pour le commercial. Explique le CONCEPT technique général derrière ce problème. (Ex: 'C'est quoi une injection de code ? C'est quand un site fait confiance à ce que l'utilisateur tape. Ici, le shortcode est exécuté comme du code système...'). Fais-toi plaisir, apprends-lui un truc !",
    "impact_biz": "Conséquence business concrète (Vol de données, ralentissement, baisse SEO...).",
    "script_tel": "La phrase simple pour le client."
  }},
  
  "probleme_2": {{
    "titre": "...",
    "fact_tech": "...",
    "minute_culture": "...",
    "impact_biz": "...",
    "script_tel": "..."
  }},
  
  "probleme_3": {{
    "titre": "...",
    "fact_tech": "...",
    "minute_culture": "...",
    "impact_biz": "...",
    "script_tel": "..."
  }},
  
  "resume_en_une_phrase": "LA phrase choc qui résume tout pour accrocher le client."
}}
"""
    }
}
