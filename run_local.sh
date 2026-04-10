#!/usr/bin/env bash
set -e
source venv/bin/activate
export FI_PROJ_ENV=local
python ingest.py --seed-synthetic --rows 500
python -m data_manager --init-db
streamlit run app.py
