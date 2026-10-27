# Piante

Applicazione web per gestire una collezione personale di piante: schede, gruppi e tag, task ricorrenti con promemoria Telegram, diario con foto, misurazioni con grafici, calendario e backup automatici.

Pensata per un singolo utente in rete locale, su Raspberry Pi 5 (ARM64) con un'istanza MySQL già esistente.

## Componenti

| Cartella | Contenuto |
| --- | --- |
| `backend/` | API REST in Python con FastAPI, SQLAlchemy 2, Alembic, scheduler interno (promemoria e backup) |
| `frontend/` | Interfaccia React + TypeScript (Vite), servita da nginx come file statici |
| `docs/` | Guide di installazione, configurazione, Telegram, backup, API e decisioni tecniche |
| `docker-compose.yml` | Due container: `backend` e `web` (nginx). MySQL resta esterno |

Il browser parla solo con nginx: i file dell'interfaccia sono serviti direttamente, le chiamate a `/api` sono inoltrate al backend. Backend e database non espongono porte verso l'esterno.

## Avvio rapido

```bash
cp .env.example .env        # completa DB_*, SECRET_KEY e gli altri valori
mkdir -p data backups
docker compose up -d --build
docker compose exec backend python -m app.cli create-user --username tuonome
```

Poi apri `http://<ip-del-raspberry>:8080`.

La procedura completa, compresa la creazione del database dedicato su MySQL, è in [docs/installazione.md](docs/installazione.md).

## Documentazione

- [Installazione e aggiornamento](docs/installazione.md)
- [Variabili d'ambiente, cartelle e volumi](docs/configurazione.md)
- [Notifiche Telegram](docs/telegram.md)
- [Backup e ripristino](docs/backup.md)
- [API REST](docs/api.md)
- [Decisioni tecniche e casi limite](docs/decisioni.md)

## Sviluppo

Backend (richiede [uv](https://docs.astral.sh/uv/)):

```bash
cd backend
uv sync
uv run pytest                                   # test su SQLite
TEST_DATABASE_URL="mysql+pymysql://utente:password@127.0.0.1:3306/piante_test" uv run pytest   # test su MySQL
uv run uvicorn app.main:app --reload            # usa le variabili DB_* e SECRET_KEY dall'ambiente
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, inoltra /api a 127.0.0.1:8000
npm test
npm run build
```

Dopo aver modificato le dipendenze Python, rigenera `backend/requirements.txt` (usato dall'immagine Docker):

```bash
cd backend && uv export --no-dev --no-hashes --format requirements-txt --no-emit-project -o requirements.txt
```
