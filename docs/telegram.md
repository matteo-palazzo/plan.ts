# Notifiche Telegram

Il backend invia da solo i promemoria dei task, anche con il browser chiuso. Senza configurazione Telegram l'app funziona normalmente: semplicemente non invia nulla.

## 1. Creare il bot

1. In Telegram apri una chat con **@BotFather**.
2. Invia `/newbot`, scegli un nome visualizzato e uno username che finisca con `bot`.
3. BotFather risponde con il **token**, del tipo `123456789:AAH...`. Trattalo come una password.

## 2. Ricavare il chat ID

1. Apri la chat con il tuo nuovo bot e premi **Avvia** (o invia un messaggio qualsiasi): un bot non può scriverti finché non lo hai avviato.
2. Dal Raspberry, sostituendo il token:

   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```

3. Nella risposta cerca `"chat":{"id":123456789,...}`: quel numero è il chat ID. Per un gruppo l'ID è negativo (es. `-1001234567890`) e il bot deve essere membro del gruppo.

## 3. Configurare l'app

Nel file `.env`:

```dotenv
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:AAH...
TELEGRAM_CHAT_ID=123456789
NOTIFY_TIME=08:00
```

Applica la modifica e prova l'invio:

```bash
docker compose up -d
docker compose exec backend python -m app.cli test-telegram
```

In alternativa usa **Impostazioni → Notifiche Telegram → Invia messaggio di prova**. Il token resta solo nel `.env` del server: non viene mai inviato al browser né scritto nei log.

## Come funzionano i promemoria

Ogni task sceglie una delle opzioni: nessuna notifica, il giorno della scadenza, il giorno prima, oppure entrambi.

- Ogni `NOTIFY_CHECK_MINUTES` minuti lo scheduler cerca le scadenze di oggi e di domani, ma invia solo a partire da `NOTIFY_TIME`.
- «Giorno prima» significa il giorno di calendario precedente nel fuso `TZ`, non 24 ore prima.
- I promemoria di un controllo vengono raccolti in un unico messaggio con le sezioni «Da fare oggi» e «Da fare domani».
- Non si inviano messaggi per completamenti, skip, task sospesi o disattivati, piante archiviate, scadenze già completate o saltate, né per il solo fatto che un task è in ritardo.
- Non si recuperano promemoria di giorni passati: se il Raspberry resta spento il giorno prima, quel promemoria non viene inviato in seguito. Se si riaccende in giornata, i promemoria di quel giorno partono al primo controllo.

## Duplicati ed errori

Ogni promemoria è registrato nella tabella `notification_logs`, identificato da scadenza, tipo (giorno prima o giorno stesso) e data prevista. Il registro viene scritto prima dell'invio, quindi un riavvio del container non produce doppioni.

Se Telegram risponde con un errore o non è raggiungibile, il promemoria viene ritentato ai controlli successivi della stessa giornata, fino a `NOTIFY_MAX_ATTEMPTS` tentativi. Nei log del backend compare il motivo (es. `Telegram ha risposto 401: Unauthorized`), mai il token. Se il container si interrompe proprio durante un invio, quel promemoria non viene ripetuto: si preferisce perderne uno piuttosto che rischiare un duplicato.

Errori frequenti:

| Messaggio | Causa |
| --- | --- |
| `401: Unauthorized` | Token errato |
| `400: Bad Request: chat not found` | Chat ID errato, oppure non hai avviato il bot |
| `403: Forbidden: bot was blocked by the user` | Il bot è stato bloccato nella chat |
| `Errore di rete verso Telegram` | Il Raspberry non raggiunge `api.telegram.org` |
