import argparse
import logging
from src.config.logging_config import setup_logging
from src.pipelines.pme import collect_pme_prospects
from src.config.settings import TARGET_TOTAL, MODE_PROSPECTION
import pandas as pd
from dataclasses import asdict
from datetime import datetime

def dedup_key(row: pd.Series) -> str:
    """Génère une clé de déduplication multi-champs."""
    fields = [row.get('email'), row.get('linkedin'), row.get('instagram'), row.get('company_name')]
    return "|".join(
        str(field).lower().strip()
        for field in fields
        if field and isinstance(field, (str, bytes))
    )

def main():
    # Setup Parsing Arguments
    parser = argparse.ArgumentParser(description="Outil de Prospection Automatisé (Refactored)")
    parser.add_argument("--limit", type=int, default=TARGET_TOTAL, help="Nombre total de prospects cibles")
    parser.add_argument("--mode", type=str, default=MODE_PROSPECTION, choices=["code_naf", "objet_social"], help="Mode de prospection")
    parser.add_argument("--debug", action="store_true", help="Activer les logs DEBUG")
    
    args = parser.parse_args()
    
    # Setup Logging
    log_level = "DEBUG" if args.debug else "INFO"
    logger = setup_logging(level=log_level)
    
    logger.info("🚀 Démarrage de l'outil de prospection (Version Refactorisée)")
    logger.info(f"🎯 Objectif : {args.limit} prospects")
    logger.info(f"🛠️  Mode : {args.mode}")
    
    try:
        # Exécution du Pipeline PME
        prospects = collect_pme_prospects(target_count=args.limit)
        
        logger.info("")
        if prospects:
            logger.info(f"✨ Succès ! {len(prospects)} prospects qualifiés ont été générés.")
            
            # Conversion sécurisée en DataFrame (unify)
            rows = []
            for p in prospects:
                if isinstance(p, dict): rows.append(p)
                else: 
                    try: rows.append(asdict(p))
                    except: continue
            
            df = pd.DataFrame(rows)
            
            if not df.empty:
                # Déduplication avancée
                df["_dedup_key"] = df.apply(dedup_key, axis=1)
                initial_len = len(df)
                df = df.drop_duplicates(subset=["_dedup_key"]).drop(columns=["_dedup_key"])
                
                if len(df) < initial_len:
                    logger.info(f"🧹 Déduplication: {initial_len - len(df)} doublons retirés (clé complexe)")
                
                # Export CSV
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"prospects_final_{timestamp}.csv"
                df.to_csv(filename, index=False, encoding="utf-8")
                logger.info(f"💾 Fichier sauvegardé : {filename} ({len(df)} lignes)")
                
                # Nettoyer les checkpoints après succès complet
                from src.core.checkpoint import CheckpointManager
                _checkpoint_manager = CheckpointManager()
                _checkpoint_manager.clear_checkpoints()
                logger.info("✅ Pipeline terminé avec succès - checkpoints nettoyés")
            else:
                logger.warning("⚠️ DataFrame vide après conversion.")
            
        else:
            logger.warning("⚠️ Aucune donnée n'a été générée.")
            
    except KeyboardInterrupt:
        logger.warning("\n🛑 Interruption utilisateur (CTRL+C). Arrêt propre.")
    except Exception as e:
        logger.critical(f"💥 Erreur critique : {e}", exc_info=True)

if __name__ == "__main__":
    main()
