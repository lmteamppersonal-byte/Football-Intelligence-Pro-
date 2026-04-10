# Football Intelligence Pro

MVP de Scouting Avançado focado em estatísticas de jogadores com cálculos de Z-Score padronizados por posição e extração tolerante à falhas.

## Arquitetura
1. **Model** (`SQLAlchemy`): Operações otimizadas via WAL SQLite base para alta concorrência.
2. **Scraper** (`SofaClient`): fallback requests -> Cloudscraper -> Selenium (headless) syncando persistentemente os cookies de acesso.
3. **Analytics** (`Impact Index`): Processamento matemático unificado isolando performance por demografia dentro do campo.

---

## 🚀 Como testar Online (Deploy)

A aplicação foi rigorosamente testada preparando o terreno tanto para Deploy Conteinerizado (AWS/GCP/Render) quanto Deploy Direto via (Streamlit Community Cloud).

### Opção A: Streamlit Community Cloud (Mais Fácil)
1. Conecte este repositório no seu painel [share.streamlit.io](https://share.streamlit.io/).
2. O arquivo `packages.txt` já garantirá a instalação do `chromium` para o scraper Headless do backend.
3. (Opcional): Preencha as chaves do `.streamlit/secrets.toml.example` na aba "Advanced Settings -> Secrets".
4. Clique em **Deploy**!

### Opção B: Docker / Container Runtime (Mais Escalável)
Esse projeto já contém o mapeamento perfeito entre os web-drivers Selenium e o seu app web Streamlit contendo o database.
```bash
docker-compose up --build
```
Isso vai construir a interface no porto `:8501`.

## Local Dev
```powershell
.\run_local.ps1 # No Windows
./run_local.sh  # No MacOS/Linux
```
Execute os testes unitários via `pytest tests/`.
