# Roadmap: Football Intelligence Pro

Este documento descreve as etapas de médio e longo prazo (Post-MVP) projetadas para suportar alta escalabilidade e concorrência no nível Enterprise de Football Intelligence Pro.

## 1. Banco de Dados: Migração para PostgreSQL
Atualmente, o projeto utiliza `SQLite` em modo `WAL`, que é excelente para leitura concorrente em MVP. No entanto, para escalar workers persistentes distribuídos, precisaremos de PostgreSQL.

### Ações Necessárias:
- Instalar driver Postgres (`psycopg2-binary`).
- Ajustar o `DataManager` para ler a nova connection string em ambiente de produção (ex: `DB_URL=postgresql://user:pass@host:5432/db`).
- Desabilitar a chamada obrigatória pragmática do `WAL` (`PRAGMA journal_mode=WAL`) caso o driver não seja `sqlite://`.
- Gerenciar as migrações arquiteturais de Schema via `Alembic` (inicializar um `alembic init alembic`).

## 2. Observabilidade Extensiva & Prometheus
Implementar rotas para exportação metrificada padronizada (padrão OpenMetrics) visando ser raspada (scraped) rotineiramente pelo Prometheus.

### Ações Necessárias:
- Utilizar o `prometheus_client` framework e integrar nosso exportador rodando assíncrono.
- Hospedar painéis analíticos complexos usando o **Grafana** amarrando localmente no `docker-compose.yml`.

## 3. Gestão de Filas & Celery / Redis
Quando o uso de memória por threading começar a custar, devemos adotar o `Celery`.
- Migrar o método de disparo `background_scrape` do Streamlit UI para push de tarefas no broker Redis.
- Fazer a UI apenas ler o status do job.
