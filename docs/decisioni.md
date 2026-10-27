# Decisioni tecniche e casi limite

Questo documento raccoglie le scelte che la specifica lasciava aperte (§27) e il comportamento dell'app nei casi limite.

## Stack

| Area | Scelta | Motivo |
| --- | --- | --- |
| Backend | FastAPI, SQLAlchemy 2 sincrono, PyMySQL | Il carico è di un solo utente: le rotte sincrone nel thread pool di FastAPI sono più semplici dell'async e bastano. PyMySQL è puro Python, quindi non serve compilare nulla su ARM64 |
| Migrazioni | Alembic, applicate all'avvio | Solo `upgrade`, mai operazioni distruttive automatiche |
| Scheduler | APScheduler 3 nel processo del backend | Nessun container o broker in più. Richiede un solo worker uvicorn |
| Password | Argon2id (`argon2-cffi`) | Algoritmo raccomandato per le password, wheel disponibili per ARM64 |
| Sessioni | Tabella `user_sessions` + cookie `HttpOnly`, `SameSite=Strict` | Logout e cambio password invalidano davvero le sessioni. Il token è salvato solo come HMAC |
| CSRF | Token per sessione nell'header `X-CSRF-Token` | Si aggiunge a `SameSite=Strict` per tutte le richieste che modificano dati |
| Frontend | React 19, React Router, Vite | Come da specifica |
| Grafici | Recharts | Diffuso e sufficiente; caricato solo quando si aprono le misurazioni, così il bundle iniziale resta circa 100 KB gzip |
| Calendario | Componente proprio (griglia mensile + agenda) | Più leggero di una libreria e adatto alle sole viste richieste |
| Stato client | Hook minimale `useAsync` | Evita una libreria di data fetching per poche schermate |
| Web server | nginx alpine | Serve i file statici e inoltra `/api`: niente CORS, una sola porta pubblicata |

## Modello delle scadenze

Ogni scadenza è una riga di `task_occurrences` con data prevista e stato registrato (`pending`, `completed`, `skipped`, `suspended`). «In ritardo» non è salvato: è una scadenza `pending` con data passata. Una scadenza non può essere completata e saltata insieme perché lo stato è un solo campo.

### Task a intervallo

- Esiste sempre al più una scadenza aperta.
- Al completamento, la successiva è `giorno locale del completamento + intervallo`. Il ritardo non si propaga (completato il 20 marzo con intervallo 14 → 3 aprile).
- **Skip**: la successiva è la prima data della serie `ultimo completamento + k × intervallo` successiva sia alla data saltata sia a oggi. **Se il task non è mai stato completato** la serie parte dalla data della scadenza saltata. Esempi con intervallo 7: prima scadenza 1 marzo saltata il 1 marzo → 8 marzo; saltata il 20 marzo → 22 marzo. In questo modo lo skip non riporta mai la scadenza nel passato.
- Non si generano mai serie di scadenze arretrate.

### Task a calendario

- Regole: giorni della settimana, oppure giorno del mese.
- **Giorni 29, 30 e 31**: nei mesi che non li hanno si usa l'ultimo giorno del mese (31 → 30 aprile, 28 o 29 febbraio).
- Le scadenze vengono create in anticipo fino a **31 giorni** da oggi (orizzonte di generazione) e restano ancorate al calendario: completare lunedì la scadenza di lunedì scorso non sposta quella di questo lunedì.
- Ogni data è una riga distinta (vincolo unico `task_id + data`): skip o completamento di una non toccano le altre. Le arretrate restano visibili finché non vengono gestite.
- Oltre l'orizzonte il calendario mostra le date future come «Previsto», calcolate al volo e non salvate.
- Se l'app resta spenta a lungo, alla ripartenza vengono create le scadenze mancanti (al massimo 400 per task per ciclo, poi si continua al ciclo successivo).

### Task una tantum

Una sola scadenza alla data indicata; dopo completamento o skip non ne genera altre.

### Sospensione

Si sospende per un numero di giorni o fino a una data: la data indicata è il **giorno di riattivazione** (il task torna attivo quel giorno).

Durante la sospensione il task non compare in dashboard e non invia promemoria. Alla riattivazione (automatica, o anticipata con «Riattiva ora»):

- **task a calendario**: le scadenze che cadevano nel periodo sospeso diventano «Sospese» (stato finale, visibile nello storico) e non vengono recuperate. Le scadenze già arretrate **prima** della sospensione restano da fare;
- **task a intervallo e una tantum**: se la scadenza aperta cadeva prima della riattivazione, slitta al giorno della riattivazione.

Non vengono mai inviati promemoria arretrati: si inviano solo i promemoria di oggi e di domani.

### Disattivazione ed eliminazione dei task

«Disattiva» ferma il task (niente dashboard, niente promemoria, niente nuove scadenze) conservando configurazione e storico. «Elimina» chiede conferma e rimuove task, scadenze e registro notifiche; le voci del diario già create restano, con il nome del task salvato al momento del completamento.

### Modifica di un task

Le modifiche valgono solo per le scadenze future; completamenti, skip e voci di diario passati non cambiano.

- Cambio della regola di calendario: le scadenze future ancora aperte che non rispettano più la regola vengono rimosse, quelle mancanti create. Le arretrate restano.
- Cambio dell'intervallo: la scadenza aperta viene ricalcolata dall'ultimo completamento (o dalla data iniziale se non ci sono state esecuzioni).
- Cambio del tipo di ricorrenza: le scadenze aperte future vengono sostituite secondo la nuova regola; le arretrate restano.

### Correzione di un completamento

«Annulla» riporta la scadenza a «da fare» ed elimina la voce di diario collegata (con nota e foto, anche i file), dopo una conferma che lo spiega.

- **Task a intervallo**: si può annullare solo l'ultima esecuzione registrata. La scadenza successiva generata da quel completamento viene eliminata, quindi la pianificazione torna esattamente com'era prima.
- **Task a calendario**: si può annullare qualunque scadenza; le altre non cambiano.

Lo stesso vale per annullare uno skip.

### Doppi completamenti

Il completamento blocca la riga della scadenza (`SELECT … FOR UPDATE`): una seconda richiesta, ad esempio un doppio tocco, trova la scadenza già completata e restituisce lo stesso risultato senza creare un'altra voce di diario.

## Piante archiviate

Le piante archiviate non compaiono nelle liste predefinite, nella dashboard né nei promemoria, e non generano nuove scadenze. Diario, foto, misurazioni e storico restano consultabili. Al ripristino, i task a calendario riprendono da oggi: le date trascorse durante l'archiviazione non vengono create.

## Eliminazioni a cascata

Le cancellazioni a cascata sono usate solo dove c'è una conferma esplicita:

- **pianta**: richiede di digitarne il nome; elimina tutto ciò che la riguarda, file delle foto compresi;
- **task**: conferma che spiega cosa si perde; il diario resta;
- **voce del diario e foto**: conferma; i file vengono eliminati dopo il commit sul database.

Il comando `cleanup-orphans` elenca (e con `--delete` rimuove) eventuali file di foto rimasti senza riferimento, ad esempio dopo un'interruzione di corrente durante un'eliminazione.

## Foto

- Formati: JPEG, PNG, WebP, riconosciuti dai primi byte del file. Limite 15 MB per foto (`PHOTO_MAX_MB`), 10 per voce.
- Il nome inviato dal client viene ignorato: i file sono salvati come `AAAA/MM/<uuid>.<estensione>`.
- Il caricamento scrive prima in `photos/.staging/` a blocchi da 256 KB (nessuna foto viene caricata interamente in memoria), poi sposta il file e salva il riferimento nel database. In caso di errore i file temporanei vengono rimossi.
- Nessuna miniatura viene generata, per non caricare la CPU del Raspberry: le immagini nelle gallerie sono caricate in modo differito (`loading="lazy"`) e messe in cache dal browser.

## Misurazioni

- I valori sono salvati in millimetri con due decimali; l'inserimento in centimetri viene convertito (× 10).
- Grafici: «ultimo mese» = 31 giorni, «ultimo anno» = 365 giorni. Se nello stesso giorno ci sono più misure dello stesso tipo, il grafico usa l'ultima inserita (l'elenco completo resta visibile).
- Ogni misurazione crea una voce nel diario che la referenzia: modificare o eliminare la misurazione aggiorna o elimina la voce.

## Notifiche

Vedi [telegram.md](telegram.md). In sintesi: registro con vincolo unico per scadenza, tipo e data; registrazione prima dell'invio; al massimo `NOTIFY_MAX_ATTEMPTS` tentativi nella stessa giornata; nessun recupero di promemoria di giorni passati.

## Backup

Vedi [backup.md](backup.md). Backup settimanale (domenica 03:30 di default), retention 30 giorni, export applicativo in uno snapshot consistente invece di `mysqldump`, foto bloccate in scrittura durante la copia, backup di recupero all'avvio se l'ultimo riuscito ha più di 8 giorni.

## Date e fusi orari

Gli istanti (completamenti, voci del diario, invii) sono salvati in UTC. Le date di scadenza sono date di calendario nel fuso `TZ`. Il «giorno» di un completamento, il «giorno prima» dei promemoria e l'orario dei backup usano sempre `TZ`.

## Primo account

Nessuna credenziale predefinita: l'account si crea dal terminale con `python -m app.cli create-user`, che rifiuta di crearne un secondo. Non esiste una pagina di registrazione.

## Verifiche svolte

- 94 test automatici del backend, eseguiti sia su SQLite sia su MySQL 8.4: piante, gruppi e tag, diario e foto, misurazioni, task (una tantum, intervallo, calendario, completamento, skip, sospensione, riattivazione, modifica, correzione, arretrati, idempotenza), notifiche, backup, retention e ripristino, autenticazione.
- Test unitari del frontend sulle utility di date e validazione delle foto.
- Flusso completo contro MySQL attraverso il proxy del frontend: pianta, gruppo e due tag, voce con due foto, misurazione, task una tantum, a intervallo e a calendario, completamento con nota e foto, skip, sospensione, calendario, archiviazione, backup. Ripristino via CLI dell'archivio prodotto in un database e una cartella dati vuoti, con file delle foto identici.
