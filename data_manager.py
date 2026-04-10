import os
import pandas as pd
import json
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Numeric, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
import logging
logger = logging.getLogger(__name__)

# Import robusto para ambientes com diferenças de path/import
try:
    # tentativa de import relativo (quando o projeto é tratado como pacote)
    from .utils.logging_config import setup_logging
except Exception:
    try:
        # tentativa de import absoluto (quando executado como script)
        from utils.logging_config import setup_logging
    except Exception as exc:
        # fallback: define setup_logging local para evitar crash total
        logger.exception("Falha ao importar utils.logging_config; usando fallback de logging")
        import logging as _logging
        def setup_logging(level=_logging.INFO):
            _logging.basicConfig(level=level)
            return _logging.getLogger()

from dotenv import load_dotenv

load_dotenv()
logger = setup_logging("data_manager")

Base = declarative_base()

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=False)
    short_name = Column(String)
    position = Column(String, index=True)
    secondary_positions = Column(String)
    nationality = Column(String, index=True)
    birthdate = Column(Date)
    height_cm = Column(Integer)
    weight_kg = Column(Integer)
    preferred_foot = Column(String)
    current_club = Column(String, index=True)
    club_id = Column(String)
    market_value = Column(Numeric)
    contract_until = Column(Date)
    photo_url = Column(String)
    last_seen_at = Column(DateTime, index=True)
    source_meta = Column(JSON)
    metrics = Column(JSON)

    # Core stats normalized for fast querying (backwards compatibility with MVP)
    gols = Column(Integer, default=0)
    assistencias = Column(Integer, default=0)
    xg = Column(Numeric, default=0)
    passes_precisos_pct = Column(Numeric, default=0)
    dribles_ganhos = Column(Integer, default=0)
    duelos_aereos_ganhos_pct = Column(Numeric, default=0)
    interceptacoes = Column(Integer, default=0)
    desarmes = Column(Integer, default=0)
    grandes_chances_criadas = Column(Integer, default=0)
    passes_decisivos = Column(Integer, default=0)
    finalizacoes_no_alvo = Column(Integer, default=0)

class DataManager:
    def __init__(self, db_path: str = None):
        if not db_path:
            db_path = os.environ.get("DB_PATH", "data/football.db")
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        db_url = f"sqlite:///{db_path}"
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        
        # Enable WAL (Write-Ahead Logging) for better concurrency
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            
        self.init_db()

    def init_db(self) -> None:
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing DB: {e}")

    def load_file(self, file_source) -> pd.DataFrame:
        """Validate and return DataFrame read from CSV/Excel."""
        try:
            filename = getattr(file_source, "name", str(file_source)).lower()
            if filename.endswith(".csv"):
                df = pd.read_csv(file_source)
            else:
                df = pd.read_excel(file_source)
            
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # Basic validation
            if "player_id" not in df.columns or "full_name" not in df.columns:
                raise ValueError("Missing required columns: 'player_id' and/or 'full_name'")
                
            return df
        except Exception as e:
            logger.error(f"Failed to load file: {e}")
            raise ValueError(f"File validation error: {e}")

    def upsert_players(self, df: pd.DataFrame) -> int:
        """Robust UPSERT using SQLAlchemy SQLite dialect."""
        records = df.to_dict(orient="records")
        for rec in records:
            # Ensure JSON columns are handled correctly
            if "source_meta" in rec and isinstance(rec["source_meta"], str):
                try: rec["source_meta"] = json.loads(rec["source_meta"])
                except: pass
            if "metrics" in rec and isinstance(rec["metrics"], str):
                try: rec["metrics"] = json.loads(rec["metrics"])
                except: pass
            
            # Map basic string to datetime if needed
            for date_col in ["birthdate", "contract_until", "last_seen_at"]:
                if date_col in rec and pd.isna(rec[date_col]):
                    rec[date_col] = None
        
        session = self.Session()
        inserted_count = 0
        try:
            valid_cols = {c.name for c in Player.__table__.columns}
            for rec in records:
                # Remove NaN
                cleaned_rec = {k: v for k, v in rec.items() if not pd.isna(v)}
                if "player_id" not in cleaned_rec:
                    continue
                
                # Filter to only known columns
                cleaned_rec = {k: v for k, v in cleaned_rec.items() if k in valid_cols}
                
                # Convert numeric types from numpy to standard python
                for k, v in cleaned_rec.items():
                    if hasattr(v, 'item'):
                        cleaned_rec[k] = v.item()

                # Convert date/datetime strings
                if "birthdate" in cleaned_rec and isinstance(cleaned_rec["birthdate"], str):
                    try: cleaned_rec["birthdate"] = datetime.datetime.fromisoformat(cleaned_rec["birthdate"]).date()
                    except: del cleaned_rec["birthdate"]
                if "contract_until" in cleaned_rec and isinstance(cleaned_rec["contract_until"], str):
                    try: cleaned_rec["contract_until"] = datetime.datetime.fromisoformat(cleaned_rec["contract_until"]).date()
                    except: del cleaned_rec["contract_until"]
                if "last_seen_at" in cleaned_rec and isinstance(cleaned_rec["last_seen_at"], str):
                    try: cleaned_rec["last_seen_at"] = datetime.datetime.fromisoformat(cleaned_rec["last_seen_at"])
                    except: del cleaned_rec["last_seen_at"]

                stmt = sqlite_upsert(Player).values(cleaned_rec)
                
                # Update all columns on conflict except player_id and id
                update_dict = {c.name: c for c in stmt.excluded if c.name not in ["id", "player_id"]}
                stmt = stmt.on_conflict_do_update(
                    index_elements=["player_id"],
                    set_=update_dict
                )
                session.execute(stmt)
                inserted_count += 1
            session.commit()
            logger.info(f"Successfully upserted {inserted_count} records.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error during UPSERT: {e}")
            raise
        finally:
            session.close()
        return inserted_count

    def query_players(self, filters: dict = None) -> pd.DataFrame:
        """Query DB and return a DataFrame based on filters."""
        query = "SELECT * FROM players WHERE 1=1"
        params = {}
        
        if filters:
            if "position" in filters and filters["position"] != "Todas":
                query += " AND position = :position"
                params["position"] = filters["position"]
            if "idade_max" in filters:
                # Approximation of age using birthdate
                n_days = filters["idade_max"] * 365
                date_thresh = (datetime.date.today() - datetime.timedelta(days=n_days)).isoformat()
                query += " AND birthdate >= :date_thresh"
                params["date_thresh"] = date_thresh
                
        try:
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params=params)
            # Calculate age dynamically if birthdate exists
            if not df.empty and "birthdate" in df.columns:
                df["birthdate"] = pd.to_datetime(df["birthdate"], errors="coerce")
                df["idade"] = (pd.Timestamp.now() - df["birthdate"]).dt.days // 365
                # map back 'nome' for UI compatibility quickly if 'full_name' exists
                df["nome"] = df["full_name"]
            return df
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return pd.DataFrame()

# Provide easy compat instances
db_manager = DataManager()
init_db = db_manager.init_db
load_from_file = db_manager.load_file
fetch_players = db_manager.query_players
