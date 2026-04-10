import argparse
import pandas as pd
import numpy as np
import random
import json
from datetime import date, datetime, timedelta
from typing import Optional
from data_manager import db_manager

try:
    from faker import Faker
except ImportError:
    Faker = None

from utils.logging_config import setup_logging
logger = setup_logging("ingestion")

def generate_synthetic_data(num_rows: int, output_path: str = "sample_data_expanded.csv"):
    if not Faker:
        raise ImportError("Please install Faker to generate synthetic data: pip install faker")
    
    fake = Faker('pt_BR')
    
    positions = ['Goleiro', 'Zagueiros', 'Laterais', 'Volantes', 'Médios', 'Meias-atacantes', 'Extremos', 'Centroavantes']
    nationalities = ['Brasil', 'Argentina', 'Espanha', 'França', 'Inglaterra', 'Alemanha']
    clubs = ['Flamengo', 'Palmeiras', 'Real Madrid', 'Man City', 'Arsenal', 'Inter Milan', 'Bayern Munich', 'Botafogo', 'São Paulo']
    feet = ['Left', 'Right', 'Ambidextrous']
    
    data = []
    for _ in range(num_rows):
        pos = random.choice(positions)
        idade = random.randint(17, 36)
        birthdate = date.today() - timedelta(days=idade * 365 + random.randint(0, 364))
        
        # Base attributes
        is_gk = pos == 'Goleiro'
        is_def = pos in ['Zagueiros', 'Laterais', 'Volantes']
        is_att = pos in ['Extremos', 'Centroavantes', 'Meias-atacantes']
        
        player_id = str(fake.unique.random_number(digits=6))
        
        # Precompute metrics we also put in exact columns
        metrics = {
            "gols": random.randint(0, 30) if is_att else random.randint(0, 5),
            "assistencias": random.randint(0, 20) if not is_gk else 0,
            "xg": round(random.uniform(0.0, 25.0) if is_att else random.uniform(0.0, 3.0), 2),
            "passes_precisos_pct": round(random.uniform(50.0, 95.0), 1),
            "dribles_ganhos": random.randint(0, 100) if not is_gk else 0,
            "duelos_aereos_ganhos_pct": round(random.uniform(20.0, 90.0), 1),
            "interceptacoes": random.randint(0, 100) if is_def else random.randint(0, 20),
            "desarmes": random.randint(0, 120) if is_def else random.randint(0, 30),
            "grandes_chances_criadas": random.randint(0, 25) if not is_gk else 0,
            "passes_decisivos": random.randint(0, 80) if not is_gk else 0,
            "finalizacoes_no_alvo": random.randint(0, 80) if is_att else random.randint(0, 10),
            "minutos_jogados": random.randint(500, 3420),
            "jogos": random.randint(10, 38)
        }
        
        if metrics["gols"] > metrics["finalizacoes_no_alvo"]:
            metrics["finalizacoes_no_alvo"] = metrics["gols"] + random.randint(0, 10)
            
        row = {
            "player_id": player_id,
            "full_name": fake.name_male(),
            "short_name": fake.first_name_male(),
            "position": pos,
            "secondary_positions": "",
            "nationality": random.choice(nationalities),
            "birthdate": birthdate.isoformat(),
            "height_cm": random.randint(165, 200),
            "weight_kg": random.randint(60, 95),
            "preferred_foot": random.choice(feet),
            "current_club": random.choice(clubs),
            "club_id": str(random.randint(1, 1000)),
            "market_value": round(random.uniform(1.0, 150.0), 1),
            "contract_until": (date.today() + timedelta(days=random.randint(365, 1800))).isoformat(),
            "photo_url": "https://example.com/photo.jpg",
            "last_seen_at": datetime.now().isoformat(),
            "source_meta": json.dumps({"source": "synthetic", "created_at": datetime.now().isoformat()}),
            "metrics": json.dumps(metrics)
        }
        
        # Flatten metrics to root for backwards compat with model columns
        row.update(metrics)
        data.append(row)
        
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    logger.info(f"Generated {num_rows} rows of synthetic data at {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest or generate data for Football Intelligence Pro")
    parser.add_argument("--seed-synthetic", action="store_true", help="Generate synthetic data and ingest to DB")
    parser.add_argument("--rows", type=int, default=500, help="Number of rows for synthetic generation")
    parser.add_argument("--file", type=str, help="Path to CSV/Excel file to ingest into DB")
    
    args = parser.parse_args()
    
    if args.seed_synthetic:
        generate_synthetic_data(args.rows, "sample_data_expanded.csv")
        n_rows = db_manager.upsert_players(pd.read_csv("sample_data_expanded.csv"))
        logger.info(f"Successfully ingested {n_rows} synthetic rows into DB.")
        
    elif args.file:
        try:
            df = db_manager.load_file(args.file)
            n_rows = db_manager.upsert_players(df)
            logger.info(f"Successfully ingested {n_rows} rows from {args.file} into DB.")
        except Exception as e:
            logger.error(f"Failed to ingest file: {e}")
