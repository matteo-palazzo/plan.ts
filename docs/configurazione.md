# Configurazione, cartelle e volumi

## Variabili d'ambiente

Tutte le variabili stanno nel file `.env` nella radice del progetto, letto sia da Docker Compose sia dal backend. Il modello completo è `.env.example`.

### Applicazione

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `TZ` | `Europe/Rome` | Fuso orario per scadenze, «giorno prima», orario dei promemoria e dei backup |
| `APP_PORT` | `8080` | Porta dell'host su cui nginx pubblica l'app |
| `APP_BIND` | `0.0.0.0` | Indirizzo su cui pubblicare la porta (IP LAN per limitarla a un'interfaccia) |
| `APP_UID`, `APP_GID` | `1000` | Utente e gruppo con cui gira il backend; devono poter scrivere in `data/` e `backups/` |
| `DASHBOARD_DAYS` | `7` | Giorni futuri mostrati di default in dashboard (massimo 31; modificabile anche dall'interfaccia) |

### Database

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `DB_HOST` | `127.0.0.1` | Host MySQL visto dal container (vedi [installazione.md](installazione.md#2-raggiungere-mysql-dal-container)) |
| `DB_PORT` | `3306` | Porta MySQL |
| `DB_NAME` | `plants` | Database dedicato |
| `DB_USER` | `plants` | Utente dedicato |
| `DB_PASSWORD` | vuoto | Password dell'utente |
| `COMPOSE_FILE` | non impostato | `docker-compose.yml:docker-compose.mysql-network.yml` per usare la rete Docker di MySQL |
| `MYSQL_DOCKER_NETWORK` | non impostato | Nome della rete Docker di MySQL (solo con il file aggiuntivo sopra) |
| `DATABASE_URL` | non impostato | URL SQLAlchemy completo che sostituisce le variabili `DB_*`; utile in sviluppo |

### Sicurezza

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `SECRET_KEY` | obbligatoria | Almeno 32 caratteri casuali; firma i token di sessione. Il backend non parte se manca |
| `SESSION_DAYS` | `30` | Durata della sessione dopo il login |
| `COOKIE_SECURE` | `false` | `true` se l'app è servita in HTTPS: il cookie di sessione viaggia solo su connessioni cifrate |

### Foto

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `PHOTO_MAX_MB` | `15` | Dimensione massima per singola foto |
| `PHOTOS_PER_ENTRY` | `10` | Foto massime per voce del diario o completamento |
| `DATA_HOST_DIR` | `./data` | Cartella dell'host montata in `/data` |

Formati accettati: JPEG, PNG e WebP. Il tipo è verificato dal backend leggendo i primi byte del file, non dall'estensione. nginx accetta richieste fino a 160 MB (10 foto da 15 MB, più margine): se aumenti `PHOTO_MAX_MB` oltre 15, aggiorna anche `client_max_body_size` in `frontend/nginx.conf`.

Le foto HEIC degli iPhone non sono accettate perché la maggior parte dei browser non sa mostrarle; caricando dal browser, iOS le converte normalmente in JPEG.

### Telegram

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `TELEGRAM_ENABLED` | `false` | Attiva l'invio dei promemoria |
| `TELEGRAM_BOT_TOKEN` | vuoto | Token del bot |
| `TELEGRAM_CHAT_ID` | vuoto | Chat che riceve i messaggi |
| `NOTIFY_TIME` | `08:00` | Ora locale da cui si inviano i promemoria del giorno |
| `NOTIFY_CHECK_MINUTES` | `10` | Ogni quanti minuti lo scheduler controlla i promemoria da inviare |
| `NOTIFY_MAX_ATTEMPTS` | `3` | Tentativi massimi per un promemoria il cui invio fallisce |

Vedi [telegram.md](telegram.md).

### Backup

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `BACKUP_SCHEDULE` | `30 3 * * 0` | Espressione cron nel fuso `TZ`: di default domenica alle 03:30 |
| `BACKUP_RETENTION_DAYS` | `30` | Gli archivi più vecchi vengono eliminati dopo ogni backup riuscito |
| `BACKUP_HOST_DIR` | `./backups` | Cartella dell'host montata in `/backups` |

### Variabili interne

`DATA_DIR` e `BACKUP_DIR` indicano i percorsi dentro il container e sono impostate da `docker-compose.yml` (`/data`, `/backups`): non vanno cambiate nel `.env`. `SCHEDULER_ENABLED=false` disattiva lo scheduler interno ed è usata solo dai test.

## Cartelle e volumi persistenti

```text
piante/
├── .env                 configurazione e segreti (non versionato)
├── data/                montata in /data nel backend
│   └── photos/
│       └── AAAA/MM/<uuid>.jpg
└── backups/             montata in /backups nel backend
    ├── plants-backup-AAAAMMGG-HHMMSS.tar
    ├── last-backup.json     esito dell'ultimo backup
    └── backup-errors.log    errori dei backup, uno per riga
```

Il database vive nell'istanza MySQL esistente, fuori dal Compose dell'app. Ricreare, aggiornare o eliminare i container non tocca né il database né queste cartelle.

Le foto sono servite solo attraverso il backend (`/api/photos/<id>/file`), dopo il controllo della sessione: la cartella non è esposta direttamente da nginx.

## Risorse

Il backend gira con un solo processo uvicorn (lo scheduler interno deve essere unico) ed è limitato a 384 MB di RAM; nginx a 64 MB. In sviluppo, dopo un giro completo di operazioni, il backend occupava circa 120 MB di memoria residente.
