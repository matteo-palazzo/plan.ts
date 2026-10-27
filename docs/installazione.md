# Installazione e aggiornamento

Questa guida porta da zero a un'app funzionante sul Raspberry Pi. Servono Docker con il plugin Compose e l'istanza MySQL già in esecuzione.

## 1. Database e utente dedicati

L'app usa un database separato e un utente con i soli permessi necessari. Collegati all'istanza MySQL esistente come amministratore, ad esempio:

```bash
docker exec -it <container-mysql> mysql -uroot -p
```

e crea database e utente:

```sql
CREATE DATABASE piante CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'piante'@'%' IDENTIFIED BY 'una-password-lunga-e-casuale';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, DROP, REFERENCES
    ON piante.* TO 'piante'@'%';
FLUSH PRIVILEGES;
```

`CREATE`, `ALTER`, `INDEX`, `DROP` e `REFERENCES` servono alle migrazioni dello schema; `DROP` serve anche alla procedura di ripristino. I permessi valgono solo sul database `piante`: gli altri database dell'istanza restano inaccessibili all'app.

Se preferisci limitare l'host di provenienza, sostituisci `'%'` con la subnet della rete Docker (ad esempio `'172.18.%'`).

L'app non modifica la configurazione di MySQL e non crea un nuovo container MySQL.

## 2. Raggiungere MySQL dal container

Dentro un container `localhost` indica il container stesso, non il Raspberry. Ci sono due modi per raggiungere MySQL; scegli quello adatto alla tua installazione.

### A. MySQL pubblica una porta sull'host (consigliato se già configurato così)

Se il container MySQL espone la porta 3306 sul Raspberry (`ports: - "3306:3306"` nel suo compose), nel `.env` usa:

```dotenv
DB_HOST=host.docker.internal
DB_PORT=3306
```

`docker-compose.yml` mappa già `host.docker.internal` sull'host tramite `host-gateway`. Se MySQL pubblica la porta solo su `127.0.0.1`, il container non la raggiunge: in quel caso usa l'opzione B.

### B. Rete Docker condivisa con il container MySQL

Trova la rete del container MySQL e il suo nome:

```bash
docker inspect <container-mysql> --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

Nel `.env`:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.mysql-network.yml
MYSQL_DOCKER_NETWORK=nome_della_rete
DB_HOST=nome-del-container-o-servizio-mysql
DB_PORT=3306
```

Il backend viene collegato a quella rete in sola aggiunta: la configurazione del container MySQL non cambia.

## 3. Configurazione

```bash
git clone <repository> piante && cd piante
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # valore per SECRET_KEY
```

Completa almeno `DB_*` e `SECRET_KEY`. Tutte le variabili sono descritte in [configurazione.md](configurazione.md). Il file `.env` contiene segreti: tienilo leggibile solo dal tuo utente (`chmod 600 .env`) ed escluso dal controllo versione (lo è già tramite `.gitignore`).

Crea le cartelle persistenti con il tuo utente, così il container (che gira con UID/GID `APP_UID`/`APP_GID`, default 1000) può scriverci:

```bash
mkdir -p data backups
id -u; id -g        # se diversi da 1000, imposta APP_UID e APP_GID nel .env
```

## 4. Avvio

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

La prima build sul Raspberry richiede qualche minuto (compilazione del frontend). Agli avvii successivi non si ricompila nulla. All'avvio il backend applica le migrazioni del database (`alembic upgrade head`): sono solo additive e non cancellano dati.

Entrambi i container hanno `restart: unless-stopped` e un healthcheck: ripartono da soli dopo un riavvio del Raspberry.

## 5. Primo account

Non esistono credenziali predefinite. Crea l'unico account con:

```bash
docker compose exec backend python -m app.cli create-user --username tuonome
```

Il comando chiede la password (almeno 10 caratteri) due volte e rifiuta di creare un secondo account. Per cambiare password senza accedere all'app:

```bash
docker compose exec backend python -m app.cli reset-password
```

Apri `http://<ip-del-raspberry>:8080` (o la porta indicata in `APP_PORT`).

## 6. Esposizione in rete

Viene pubblicata una sola porta, quella di nginx (`APP_PORT`). Backend e database non sono raggiungibili dall'esterno dei container. Per restringere l'accesso a una sola interfaccia imposta `APP_BIND` all'IP LAN del Raspberry. Non inoltrare la porta dal router verso Internet: l'app è pensata per la rete locale.

## Aggiornamento

```bash
cd piante
docker compose exec backend python -m app.cli backup     # backup prima di aggiornare
git pull
docker compose up -d --build
docker compose logs -f backend                           # verifica migrazioni e avvio
```

Dati e foto vivono in `data/` e `backups/` sull'host: ricreare o aggiornare i container non li tocca. Le migrazioni vengono applicate automaticamente all'avvio del nuovo backend.

Per tornare indietro dopo un aggiornamento problematico: `git checkout <versione-precedente>`, `docker compose up -d --build` e, se lo schema era già stato migrato, ripristina il backup fatto prima dell'aggiornamento (vedi [backup.md](backup.md)).

## Comandi di amministrazione

| Comando | Effetto |
| --- | --- |
| `python -m app.cli create-user` | Crea l'account (solo se non esiste) |
| `python -m app.cli reset-password` | Nuova password, chiude tutte le sessioni |
| `python -m app.cli backup` | Backup immediato |
| `python -m app.cli backup-status` | Esito dell'ultimo backup ed elenco degli archivi |
| `python -m app.cli restore <file> [--force]` | Ripristino (vedi [backup.md](backup.md)) |
| `python -m app.cli cleanup-orphans [--delete]` | Cerca file di foto non collegati al database |
| `python -m app.cli test-telegram` | Invia un messaggio Telegram di prova |

Tutti si eseguono con `docker compose exec backend …`.
