import pandas as pd
import numpy as np
from scipy.stats import zscore
import yaml
import logging

logger = logging.getLogger("impact_index")
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(ch)

DEFAULT_WEIGHTS = {
    "Goleiro": {"off": 0.1, "def": 0.8, "creation": 0.1},
    "Zagueiros": {"off": 0.1, "def": 0.8, "creation": 0.1},
    "Laterais": {"off": 0.2, "def": 0.5, "creation": 0.3},
    "Volantes": {"off": 0.15, "def": 0.6, "creation": 0.25},
    "Médios": {"off": 0.35, "def": 0.3, "creation": 0.35},
    "Meias-atacantes": {"off": 0.4, "def": 0.1, "creation": 0.5},
    "Extremos": {"off": 0.5, "def": 0.1, "creation": 0.4},
    "Centroavantes": {"off": 0.8, "def": 0.05, "creation": 0.15},
}

def load_weights(path: str = None):
    if path:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    return DEFAULT_WEIGHTS

def compute_raw_scores(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    df = df.copy()
    
    # Calculate dimensional indexes
    df["offensive_index"] = df[["gols", "finalizacoes_no_alvo", "grandes_chances_criadas"]].sum(axis=1)
    df["defensive_index"] = df[["interceptacoes", "desarmes", "duelos_aereos_ganhos_pct"]].sum(axis=1)
    df["creation_index"] = df[["passes_decisivos", "passes_precisos_pct", "dribles_ganhos"]].sum(axis=1)
    
    # We first apply Z-score to dimensions overall before weighting them
    # Wait, the prompt says "Z-score normalization per position".
    # So we compute weighted raw score per player, then zscore the raw score per position.
    
    def compute_row(r):
        pos = r["position"]
        w = weights.get(pos, {"off":0.33, "def":0.33, "creation":0.34})
        return (r["offensive_index"] * w["off"] + 
                r["defensive_index"] * w["def"] + 
                r["creation_index"] * w["creation"])
                
    df["impact_raw"] = df.apply(compute_row, axis=1)
    return df

def normalize_by_position_zscore(df: pd.DataFrame, score_col: str, position_col: str) -> pd.DataFrame:
    df = df.copy()
    
    def calc_z(x):
        if len(x) <= 1 or x.nunique() <= 1:
            return pd.Series(0, index=x.index)
        return zscore(x.fillna(x.mean()))
        
    df["impact_zscore"] = df.groupby(position_col)[score_col].transform(calc_z)
    return df

def scale_to_0_100(df: pd.DataFrame, zscore_col: str) -> pd.DataFrame:
    df = df.copy()
    
    # Scale min-max per position to ensure each position has a 0 and 100
    def min_max(x):
        minv, maxv = x.min(), x.max()
        if pd.isna(minv) or pd.isna(maxv) or minv == maxv:
            return pd.Series(50.0, index=x.index)
        return ((x - minv) / (maxv - minv)) * 100
        
    df["impact_score"] = df.groupby("position")[zscore_col].transform(min_max).round(2)
    return df

def compute_impact(df: pd.DataFrame, position_col: str = "position") -> pd.DataFrame:
    """End-to-end: raw -> zscore per position -> scaled 0-100"""
    if df.empty: return df
    
    weights = load_weights()
    df = compute_raw_scores(df, weights)
    df = normalize_by_position_zscore(df, "impact_raw", position_col)
    df = scale_to_0_100(df, "impact_zscore")
    
    return df.sort_values("impact_score", ascending=False)
