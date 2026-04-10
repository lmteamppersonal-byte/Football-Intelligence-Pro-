# no topo de app.py
import streamlit as st
try:
    from data_manager import db_manager, load_from_file, fetch_players
except Exception as e:
    st.title("Erro de inicialização")
    st.error("Falha ao importar módulos internos. Verifique logs do deploy.")
    st.code(str(e))
    raise

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import threading
import time
from io import StringIO
import json

from impact_index import compute_impact
from sofascore import get_player_stats, parse_player_id

st.set_page_config(page_title="Football Intelligence Pro", page_icon="⚽", layout="wide")

# Sidebar Setup
st.sidebar.title("⚽ Football Intelligence")
st.sidebar.markdown("Plataforma MVP de Scouting Avançado")

page = st.sidebar.radio("Navegação", [
    "📂 Importar Dados", 
    "📊 Dashboard", 
    "🎯 Análise de Jogador", 
    "⚔️ Head-to-Head", 
    "🏆 Ranking de Impacto"
])

st.sidebar.markdown("---")
st.sidebar.subheader("Filtros Globais")
pos_filter = st.sidebar.selectbox("Posição", ["Todas", "Goleiro", "Zagueiros", "Laterais", "Volantes", "Médios", "Meias-atacantes", "Extremos", "Centroavantes"])
idade_max = st.sidebar.slider("Idade Máxima", 15, 45, 40)
liga_filter = st.sidebar.text_input("Liga", "")

def get_filters():
    f = {"idade_max": idade_max}
    if pos_filter != "Todas":
        f["position"] = pos_filter
    if liga_filter:
        f["liga"] = liga_filter
    return f

# --- SIDEBAR METRICS DASHBOARD ---
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Métricas do Scraper")
if "scrape_metrics" not in st.session_state:
    st.session_state.scrape_metrics = {
        "requests": 0,
        "403s": 0,
        "retries": 0,
        "fallbacks": 0
    }

m_col1, m_col2 = st.sidebar.columns(2)
m_col1.metric("Requests", st.session_state.scrape_metrics["requests"])
m_col2.metric("403s", st.session_state.scrape_metrics["403s"])
m_col3, m_col4 = st.sidebar.columns(2)
m_col3.metric("Retries", st.session_state.scrape_metrics["retries"])
m_col4.metric("Selenium", st.session_state.scrape_metrics["fallbacks"])

# --- BACKGROUND SCRAPING RUNNER ---
def background_scrape(url, temp_buffer_dict):
    import re
    from datetime import datetime
    import logging
    
    # Increment metrics arbitrarily to demonstrate the dashboard reactivity 
    # (in a real scenario, sofascore.py would pass these back via a shared queue)
    st.session_state.scrape_metrics["requests"] += 1
    
    match = re.search(r"/(\d+)(?:/|\?|#|$)", url.rstrip("/"))
    pid = match.group(1) if match else None
    
    if not pid:
        temp_buffer_dict["status"] = "error"
        temp_buffer_dict["msg"] = "❌ ID não identificado na URL."
        return
        
    temp_buffer_dict["status"] = "running"
    
    data, msg = get_player_stats(pid)
    if data:
        # Transform data into our expected flat shape for the DataFrame
        prof = data.get("profile", {}).get("player", {})
        stats_data = data.get("stats", {})
        # Depending on API structure, grab stats array
        if "statistics" in stats_data:
            s_obj = stats_data["statistics"]
            s = s_obj[0] if isinstance(s_obj, list) and s_obj else s_obj
        else:
            s = stats_data.get("playerStatistics", stats_data)
            
        pos_map = {"G": "Goleiro", "D": "Zagueiros", "LB": "Laterais", "RB": "Laterais",
                   "DM": "Volantes", "M": "Médios", "AM": "Meias-atacantes",
                   "LW": "Extremos", "RW": "Extremos", "F": "Centroavantes", "ST": "Centroavantes"}
        
        row = {
            "player_id": str(prof.get("id")),
            "full_name": prof.get("name", "Unknown"),
            "short_name": prof.get("shortName", ""),
            "position": pos_map.get(prof.get("position", "F"), "Centroavantes"),
            "nationality": prof.get("country", {}).get("name", ""),
            "current_club": prof.get("team", {}).get("name", ""),
            "club_id": str(prof.get("team", {}).get("id", "")),
            "market_value": prof.get("proposedMarketValue", 0) or 0,
            "photo_url": f"https://api.sofascore.app/api/v1/player/{pid}/image",
            "last_seen_at": datetime.now().isoformat(),
            "source_meta": json.dumps(prof),
            "metrics": json.dumps(s)
        }
        
        # Flatten stats
        stat_map = {
            "gols": s.get("goals", 0) or 0,
            "assistencias": s.get("goalAssist", 0) or 0,
            "xg": s.get("expectedGoals", 0) or 0,
            "passes_precisos_pct": s.get("accuratePassesPercentage", 0) or 0,
            "dribles_ganhos": s.get("successfulDribblesPercentage", 0) or 0,
            "duelos_aereos_ganhos_pct": s.get("aerialDuelsWonPercentage", 0) or 0,
            "interceptacoes": s.get("interceptions", 0) or 0,
            "desarmes": s.get("tackles", 0) or 0,
            "grandes_chances_criadas": s.get("bigChancesCreated", 0) or 0,
            "passes_decisivos": s.get("keyPasses", 0) or 0,
            "finalizacoes_no_alvo": s.get("shotsOnTarget", 0) or 0,
        }
        
        row.update(stat_map)
        df_new = pd.DataFrame([row])
        
        try:
            db_manager.upsert_players(df_new)
            temp_buffer_dict["status"] = "done"
            temp_buffer_dict["msg"] = msg
            temp_buffer_dict["data"] = df_new
        except Exception as e:
            temp_buffer_dict["status"] = "error"
            temp_buffer_dict["msg"] = f"❌ Erro ao salvar no banco: {e}"
    else:
        temp_buffer_dict["status"] = "error"
        temp_buffer_dict["msg"] = msg

# --- PÁGINAS ---

if page == "📂 Importar Dados":
    st.header("📂 Ingestão de Dados")
    st.markdown("Carregue datasets robustos ou busque atletas individuais via API avançada.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📁 Upload CSV / Excel")
        st.markdown("Carrega dados enriquecidos para o banco SQLite via SQLAlchemy (UPSERT).")
        uploaded_file = st.file_uploader("Selecione um arquivo", type=["csv", "xlsx"])
        
        if uploaded_file is not None:
            if st.button("💾 Processar Upload"):
                with st.spinner("Lendo e populando banco de dados..."):
                    try:
                        df = load_from_file(uploaded_file)
                        n_rows = db_manager.upsert_players(df)
                        st.success(f"✅ Arquivo `{uploaded_file.name}` processado! {n_rows} registros inseridos/atualizados com sucesso.")
                    except Exception as e:
                        st.error(f"❌ Falha ao processar arquivo: {str(e)}")

    with col2:
        st.subheader("🌐 Sofascore Scraping")
        st.markdown("Busca dados em background passando por Requests → Cloudscraper → Selenium.")
        sofa_url = st.text_input("URL do Jogador", placeholder="https://www.sofascore.com/player...")
        
        if "scrape_thread" not in st.session_state:
            st.session_state.scrape_thread = None
        if "scrape_result" not in st.session_state:
            st.session_state.scrape_result = {}
            
        if st.button("🔍 Iniciar Extração"):
            if sofa_url:
                st.session_state.scrape_result = {"status": "starting", "msg": "Iniciando.."}
                thread = threading.Thread(target=background_scrape, args=(sofa_url, st.session_state.scrape_result))
                st.session_state.scrape_thread = thread
                thread.start()
            else:
                st.warning("Insira uma URL válida.")
                
        # Status monitor placeholder
        if st.session_state.scrape_result.get("status") in ["starting", "running"]:
            st.info("Scraping em andamento... aguarde.")
            # Auto-refresh using st.rerun until done
            time.sleep(1)
            st.rerun()
            
        if st.session_state.scrape_result.get("status") == "done":
            st.success(st.session_state.scrape_result.get("msg"))
            st.dataframe(st.session_state.scrape_result.get("data"))
            # st.session_state.scrape_result = {} # Clear if you want
        elif st.session_state.scrape_result.get("status") == "error":
            st.error(st.session_state.scrape_result.get("msg"))
            
    st.markdown("---")
    st.subheader("🗄️ Status do Banco de Dados")
    df_preview = fetch_players(get_filters())
    
    if df_preview.empty:
        st.info("Banco de dados vazio de acordo com os filtros atuais.")
    else:
        st.metric("Total de Jogadores (Filtro)", len(df_preview))
        st.dataframe(df_preview.head(100), use_container_width=True)
        if st.button("🗑️ Limpar DB (Reset)"):
            import os
            try:
                if os.path.exists("data/football.db"):
                    os.remove("data/football.db")
                db_manager.init_db()
                st.success("Banco de dados resetado com sucesso!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Não foi possível remover o banco: {e}")

elif page == "📊 Dashboard":
    st.header("📊 Dashboard Analítico")
    df = fetch_players(get_filters())
    
    if df.empty:
        st.warning("Sem dados para exibir. Vá para **Importar Dados**.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Jogadores", len(df))
        if "idade" in df.columns:
            c2.metric("Média de Idade", f"{df['idade'].mean():.1f} anos")
        c3.metric("Média Gols", f"{df['gols'].mean():.1f}")
        c4.metric("Média Passes Prec. (%)", f"{df['passes_precisos_pct'].mean():.1f}")
        
        st.markdown("### xG vs Gols Marcados")
        df_scatter = df.copy()
        
        # Safe trendline
        try:
            trendline_val = "ols" if len(df_scatter) > 2 else None
        except Exception:
            trendline_val = None
            
        fig = px.scatter(
            df_scatter, 
            x="xg", 
            y="gols", 
            color="position",
            hover_name="nome",
            hover_data=["current_club"] + (["idade"] if "idade" in df_scatter.columns else []),
            labels={"xg": "Gols Esperados (xG)", "gols": "Gols Marcados", "position": "Posição"},
            title="Eficiência de Finalização: Quem faz mais com menos chances?",
            trendline=trendline_val,
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

elif page == "🎯 Análise de Jogador":
    st.header("🎯 Perfil do Jogador")
    df = fetch_players(get_filters())
    
    if df.empty:
        st.warning("Sem dados.")
    else:
        player_name = st.selectbox("Selecione o Jogador", options=sorted(df["nome"].unique()))
        p_idx = df[df["nome"] == player_name].index[0]
        p_data = df.loc[p_idx]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            if pd.notna(p_data.get("photo_url")):
                st.image(p_data["photo_url"], width=150)
            st.markdown(f"## {p_data['nome']}")
            st.markdown(f"**Posição**: {p_data['position']}")
            st.markdown(f"**Clube**: {p_data.get('current_club', 'N/A')}")
            if "idade" in p_data:
                st.markdown(f"**Idade**: {int(p_data['idade'])} anos")
            st.markdown(f"**Valor de Mercado**: €{p_data.get('market_value', 0)}M")
        
        with c2:
            radar_cols = ["gols", "assistencias", "xg", "passes_decisivos", 
                          "passes_precisos_pct", "dribles_ganhos", "desarmes", "interceptacoes"]
            values = [float(p_data.get(c, 0)) for c in radar_cols]
            
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=values,
                theta=radar_cols,
                fill='toself',
                name=player_name,
                line_color="#00FFAA"
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, max(values) * 1.2 if max(values) > 0 else 10])),
                showlegend=False,
                title="Atributos Chave",
                template="plotly_dark"
            )
            st.plotly_chart(fig, use_container_width=True)

elif page == "⚔️ Head-to-Head":
    st.header("⚔️ Comparativo Head-to-Head")
    df = fetch_players(get_filters())
    
    if df.empty or len(df) < 2:
        st.warning("Necessário pelo menos 2 jogadores no banco de dados para comparar.")
    else:
        colA, colB = st.columns(2)
        with colA:
            jogadorA = st.selectbox("Jogador A", options=df["nome"].unique(), key="s_A")
        with colB:
            jogadorB = st.selectbox("Jogador B", options=df["nome"].unique(), key="s_B")
            
        pA = df[df["nome"] == jogadorA].iloc[0]
        pB = df[df["nome"] == jogadorB].iloc[0]
        
        st.markdown("### Radar Comparativo")
        radar_cols = ["gols", "assistencias", "xg", "passes_decisivos", 
                      "passes_precisos_pct", "dribles_ganhos", "desarmes", "interceptacoes"]
        
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=[float(pA.get(c, 0)) for c in radar_cols], theta=radar_cols, fill='toself', name=jogadorA, line_color="#00FFAA"
        ))
        fig.add_trace(go.Scatterpolar(
            r=[float(pB.get(c, 0)) for c in radar_cols], theta=radar_cols, fill='toself', name=jogadorB, line_color="#FF0055"
        ))
        
        max_val = max(max([float(pA.get(c, 0)) for c in radar_cols]), max([float(pB.get(c, 0)) for c in radar_cols]))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, max_val * 1.2 if max_val > 0 else 10])),
            showlegend=True,
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        comp_df = pd.DataFrame([pA[[c for c in radar_cols if c in pA.index]].to_dict(), 
                                pB[[c for c in radar_cols if c in pB.index]].to_dict()], 
                               index=[jogadorA, jogadorB]).T
        st.dataframe(comp_df, use_container_width=True)

elif page == "🏆 Ranking de Impacto":
    st.header("🏆 Ranking de Impacto Global")
    st.markdown("Z-Score normalizado por posição e perfeitamente escalonado de 0-100.")
    
    df = fetch_players(get_filters())
    
    if df.empty:
        st.warning("Sem dados.")
    else:
        ranked_df = compute_impact(df)
        if "idade" not in ranked_df: ranked_df["idade"] = 0
        
        st.dataframe(ranked_df[["nome", "position", "current_club", "idade", "impact_score"]].head(250), use_container_width=True)
        
        fig = px.bar(
            ranked_df.head(20).sort_values("impact_score", ascending=True), 
            x="impact_score", 
            y="nome", 
            orientation="h",
            color="impact_score",
            color_continuous_scale="Viridis",
            title="Top 20 Jogadores por Índice de Impacto"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        csv = ranked_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Exportar Ranking Completo (CSV)", data=csv, file_name="ranking_fip.csv", mime="text/csv")
