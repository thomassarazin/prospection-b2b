import logging
import os
from typing import Optional, Dict, Any
from pymongo import MongoClient

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, uri: str):
        # Création d'un index unique sur le SIREN pour éviter les doublons
        try:
            # On tente une opération légère pour vérifier la connexion (timeout court)
            self.client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            self.db = self.client.get_database("prospection_v1")
            self.prospects = self.db.get_collection("prospects")
            self.prompts = self.db.get_collection("prompts")
            self.audits = self.db.get_collection("audits")
            
            # Force check
            self.client.server_info()
            
            self.prospects.create_index("siren", unique=True)
            self.connected = True
            logger.info("✅ Connexion MongoDB établie.")
        except Exception as e:
            self.connected = False
            self.db = None
            logger.warning(f"⚠️ Impossible de se connecter à MongoDB ({e}). Mode SANS base de données activé.")

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
