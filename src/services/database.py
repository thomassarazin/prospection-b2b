import logging
import os
from typing import Optional, Dict, Any
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, uri: str):
        self.client = MongoClient(uri)
        self.db = self.client.get_database("prospection_v1")
        self.prospects = self.db.get_collection("prospects")
        self.prompts = self.db.get_collection("prompts")
        self.audits = self.db.get_collection("audits")
        
        # Création d'un index unique sur le SIREN pour éviter les doublons
        self.prospects.create_index("siren", unique=True)
        logger.info("✅ Connexion MongoDB établie et indexation terminée.")

    def get_prospect(self, siren: str) -> Optional[Dict[str, Any]]:
        return self.prospects.find_one({"siren": siren})

    def upsert_prospect(self, prospect_data: Dict[str, Any]):
        """Ajoute ou met à jour un prospect."""
        return self.prospects.update_one(
            {"siren": prospect_data.get("siren")},
            {"$set": prospect_data},
            upsert=True
        )

    def get_active_prompt(self, prompt_type: str) -> str:
        """Récupère le prompt dynamique depuis la DB."""
        doc = self.prompts.find_one({"type": prompt_type})
        return doc.get("content", "") if doc else ""
