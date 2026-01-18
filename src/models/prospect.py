from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class UnifiedProspect:
    """Représentation unifiée d'un prospect, quelle que soit la source."""
    segment: str
    prospect_name: str
    company_name: str
    email: str
    website: str
    linkedin: str
    instagram: str
    location: str
    source: str
    notes: str = ""
    icebreaker_a: str = ""
    icebreaker_b: str = ""
    icebreaker_c: str = ""
    icebreaker_d: str = ""
    
    # Audit Fields (New)
    audit_decision: str = ""      # GO / NO GO / PENDING
    audit_score: float = 0.0      # Priority Score (0-100)
    audit_summary: str = ""       # Synthesis rationale
    audit_alerts: int = 0         # Number of security alerts
    
    # Detailed Reports (Full JSON/Text)
    audit_tech_report: str = ""
    audit_ui_report: str = ""
    audit_vision_report: str = ""


    def to_dict(self):
        return asdict(self)
