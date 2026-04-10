$ErrorActionPreference = "Stop"

$repoName = "football_intelligence_pro"
$visibility = "private" # Change to "public" if desired

Write-Host "Inicializando processo automatizado de repositório no GitHub..." -ForegroundColor Cyan

# 1. Verifica se o git está inicializado
if (-not (Test-Path ".git")) {
    Write-Host "Inicializando repositório Git local..." -ForegroundColor Yellow
    git init
}

# 2. Verifica status do GitHub CLI (gh)
Write-Host "Verificando autenticação no GitHub CLI..." -ForegroundColor Yellow
try {
    gh auth status
} catch {
    Write-Host "GitHub CLI não autenticado. Executando 'gh auth login'..." -ForegroundColor Red
    gh auth login
}

# 3. Adiciona arquivos e gera o primeiro commit
Write-Host "Adicionando arquivos e realizando commit..." -ForegroundColor Yellow
git add .
try {
    git commit -m "chore: initial MVP commit with scraping, DB, tests, Docker, and CI"
} catch {
    Write-Host "Aviso: Sem mudanças para commitar." -ForegroundColor Yellow
}

git branch -M main

# 4. Cria repositório remoto via GH CLI
Write-Host "Criando repositório remoto: $repoName ($visibility)..." -ForegroundColor Yellow
try {
    # Isso vai criar o repositório, linkar o remote "origin" e fazer o git push origin main.
    gh repo create $repoName --$visibility --source=. --remote=origin --push
    Write-Host "Repositório criado e arquivos enviados com sucesso!" -ForegroundColor Green
} catch {
    Write-Host "Aviso: Repositório pode já existir ou houve uma falha de rede. Tentando sync manual..." -ForegroundColor Yellow
    # Se falhar porque já existe na interface cloud, você pode tentar rodar isso depois:
    # git remote add origin https://github.com/<USERNAME>/$repoName.git
    git push -u origin main
}

# 5. Instruções finais
Write-Host " "
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploy Concluído!" -ForegroundColor Green
Write-Host "Acesse o Streamlit Cloud (share.streamlit.io) e importe este repositório recém criado."
Write-Host "Não esqueça de copiar as keys do '.streamlit/secrets.toml.example' para os Segredos do projeto web."
Write-Host "==========================================" -ForegroundColor Cyan
