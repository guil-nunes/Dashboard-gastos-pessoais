# Dashboard de Gastos Pessoais

Dashboard local para fechar o mês: importa extratos e faturas do Nubank e do Itaú, categoriza as despesas e mostra os gastos por categoria e por mês. Roda 100% na máquina, com FastAPI + SQLite no backend e React + Vite no frontend.

- Requisitos e decisões: [docs/SPEC-MVP.md](docs/SPEC-MVP.md)
- Ordem de implementação: [docs/ROADMAP.md](docs/ROADMAP.md)

## Pré-requisitos

- Python 3.11 ou mais novo
- Node.js 20 ou mais novo (com npm)

Os comandos abaixo são para o PowerShell, no Windows.

## Backend (`backend/`)

Primeira vez:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # opcional: os valores padrão já funcionam
alembic upgrade head     # cria o banco local com as tabelas e as categorias iniciais
```

No dia a dia, com o ambiente ativado (`.venv\Scripts\Activate.ps1`):

| Para | Comando |
|---|---|
| Subir a API em `http://localhost:8000` | `uvicorn app.main:app --reload` |
| Rodar os testes | `pytest` |
| Lint | `ruff check .` |
| Conferir formatação | `ruff format --check .` (sem `--check` para formatar) |

Com a API no ar, a documentação interativa fica em `http://localhost:8000/docs`. Todas as rotas ficam sob `/api`.

O banco local fica em `data/gastos.db` e os backups em `backups/`, na raiz do repositório. Nenhum dos dois vai para o git.

### Banco de dados

O esquema é versionado com Alembic, em `backend/migrations/`. Rode os comandos em `backend/`, com o ambiente ativado:

| Para | Comando |
|---|---|
| Criar ou atualizar o banco (rode depois de cada `git pull`) | `alembic upgrade head` |
| Ver em que versão o banco está | `alembic current` |
| Gerar uma migração depois de mudar `app/repo/models.py` | `alembic revision --autogenerate -m "descrição"` (revise o arquivo gerado) |
| Conferir se modelos e migrações estão em dia | `alembic check` |

Antes de cada importação, uma cópia do banco é salva em `backups/AAAA-MM-DD_HHMMSS.db`, mantendo as 10 mais recentes (`BACKUPS_KEEP` no `.env`). Para voltar a uma cópia, feche a API e copie o arquivo do backup sobre `data/gastos.db`.

## Frontend (`frontend/`)

Primeira vez:

```powershell
cd frontend
npm install
```

| Para | Comando |
|---|---|
| Subir o app em `http://localhost:5173` | `npm run dev` |
| Regenerar os tipos da API (com o backend no ar) | `npm run gen:api` |
| Lint | `npm run lint` |
| Build de produção | `npm run build` |

Em desenvolvimento, o Vite repassa as chamadas a `/api` para o backend em `localhost:8000`. Suba os dois para usar o app; o indicador "API: ok" no topo da página confirma a conexão.

Os tipos TypeScript da API ficam em `frontend/src/api/schema.d.ts` e são gerados a partir do OpenAPI do backend. Não edite esse arquivo à mão: rode `npm run gen:api` sempre que uma rota mudar.

## Dados pessoais

Arquivos reais dos bancos ficam em `samples/`, que não vai para o git. Os testes usam apenas arquivos anonimizados em `backend/tests/fixtures/`.

Os PDFs de teste do Itaú (`backend/tests/fixtures/itau/`) são desenhados com dados inventados por um script. Para regerá-los depois de mudar o layout, rode em `backend/`: `python tests/fixtures/itau/make_fixtures.py`.
