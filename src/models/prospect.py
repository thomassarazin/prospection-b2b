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


    def to_dict(self):
        return asdict(self)
