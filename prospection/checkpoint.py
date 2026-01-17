#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Système de checkpoints pour reprise en cas de crash."""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional


class CheckpointManager:
    """Gère les sauvegardes intermédiaires pour permettre la reprise en cas de crash."""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        self.logger = logging.getLogger("prospection_pipeline")

        # Créer le répertoire si nécessaire
        os.makedirs(checkpoint_dir, exist_ok=True)

        # Fichier de métadonnées
        self.metadata_file = os.path.join(checkpoint_dir, "checkpoint_metadata.json")

    def save_checkpoint(
        self,
        prospects: List[Dict[str, Any]],
        segment_name: str,
        progress_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """Sauvegarde un checkpoint avec les prospects collectés jusqu'à présent.

        Args:
            prospects: Liste des prospects à sauvegarder
            segment_name: Nom du segment en cours
            progress_info: Informations supplémentaires sur la progression
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = os.path.join(
            self.checkpoint_dir,
            f"checkpoint_{segment_name}_{timestamp}.json"
        )

        checkpoint_data = {
            "timestamp": timestamp,
            "segment_name": segment_name,
            "prospects_count": len(prospects),
            "prospects": prospects,
            "progress_info": progress_info or {}
        }

        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2, default=str)

            # Mettre à jour les métadonnées
            self._update_metadata(checkpoint_file, segment_name, len(prospects))

            self.logger.info(f"💾 Checkpoint sauvegardé: {len(prospects)} prospects → {checkpoint_file}")

        except Exception as e:
            self.logger.error(f"❌ Erreur sauvegarde checkpoint: {e}")

    def _update_metadata(self, checkpoint_file: str, segment_name: str, count: int) -> None:
        """Met à jour le fichier de métadonnées avec le dernier checkpoint."""
        metadata = self.load_metadata()
        metadata["last_checkpoint"] = {
            "file": checkpoint_file,
            "segment": segment_name,
            "count": count,
            "timestamp": datetime.now().isoformat()
        }

        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"❌ Erreur mise à jour métadonnées: {e}")

    def load_metadata(self) -> Dict[str, Any]:
        """Charge les métadonnées du dernier checkpoint."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"⚠️ Erreur lecture métadonnées: {e}")
        return {}

    def has_checkpoint(self) -> bool:
        """Vérifie si un checkpoint existe."""
        metadata = self.load_metadata()
        return "last_checkpoint" in metadata

    def load_last_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Charge le dernier checkpoint sauvegardé."""
        metadata = self.load_metadata()

        if "last_checkpoint" not in metadata:
            return None

        checkpoint_file = metadata["last_checkpoint"]["file"]

        if not os.path.exists(checkpoint_file):
            self.logger.warning(f"⚠️ Fichier checkpoint introuvable: {checkpoint_file}")
            return None

        try:
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)

            self.logger.info(
                f"📂 Checkpoint chargé: {checkpoint_data['prospects_count']} prospects "
                f"(segment: {checkpoint_data.get('segment_name', checkpoint_data.get('segment', 'unknown'))}, "
                f"date: {checkpoint_data['timestamp']})"
            )

            return checkpoint_data

        except Exception as e:
            self.logger.error(f"❌ Erreur chargement checkpoint: {e}")
            return None

    def clear_checkpoints(self) -> None:
        """Supprime tous les checkpoints (à appeler après succès complet)."""
        try:
            import shutil
            if os.path.exists(self.checkpoint_dir):
                shutil.rmtree(self.checkpoint_dir)
                os.makedirs(self.checkpoint_dir, exist_ok=True)
                self.logger.info("🗑️ Checkpoints nettoyés")
        except Exception as e:
            self.logger.warning(f"⚠️ Erreur nettoyage checkpoints: {e}")

    def get_all_checkpoints(self) -> List[str]:
        """Retourne la liste de tous les fichiers checkpoint."""
        if not os.path.exists(self.checkpoint_dir):
            return []

        return [
            f for f in os.listdir(self.checkpoint_dir)
            if f.startswith("checkpoint_") and f.endswith(".json")
        ]
