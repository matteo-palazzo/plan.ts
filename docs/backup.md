# Backup e ripristino

## Cosa viene salvato

Ogni backup è un singolo archivio `backups/plants-backup-AAAAMMGG-HHMMSS.tar` (data e ora locali) che contiene:

| File nell'archivio | Contenuto |
| --- | --- |
| `manifest.json` | Data del backup, versione dell'app, revisione dello schema (Alembic), fuso orario, numero di righe per tabella, numero di foto, eventuali foto mancanti sul disco |
| `database.jsonl.gz` | Tutte le tabelle dell'app, una riga JSON per record |
| `photos/AAAA/MM/…` | I file delle foto referenziate dal database |

Le sessioni di login non vengono salvate: dopo un ripristino si accede di nuovo.

L'archivio non è compresso nel suo insieme (le foto JPEG/WebP lo sono già) per non caricare la CPU del Raspberry; il dump del database è compresso con gzip.

### Coerenza tra database e foto

Il dump viene letto dentro un'unica transazione MySQL in sola lettura con snapshot consistente (`START TRANSACTION WITH CONSISTENT SNAPSHOT`): tutte le tabelle riflettono lo stesso istante, senza bloccare le altre operazioni sul database. Durante il backup l'app sospende caricamenti ed eliminazioni di foto (le richieste attendono, o ricevono «Backup in corso: riprova tra qualche minuto»), così l'elenco delle foto nel dump corrisponde ai file copiati.

L'export è fatto dall'app stessa invece che con `mysqldump`: copre esattamente le tabelle dell'app, non richiede client MySQL nell'immagine né permessi aggiuntivi sull'istanza esistente, e il ripristino ricrea lo schema con le migrazioni versionate. Se vuoi anche un dump SQL classico dell'intero database, puoi farlo in qualsiasi momento dal container MySQL:

```bash
docker exec <container-mysql> mysqldump --single-transaction --routines -upiante -p piante > piante.sql
```

## Pianificazione e retention

- Backup automatico settimanale secondo `BACKUP_SCHEDULE` (default domenica alle 03:30, fuso `TZ`).
- Dopo ogni backup riuscito vengono eliminati gli archivi più vecchi di `BACKUP_RETENTION_DAYS` giorni (default 30), riconosciuti dal nome. Altri file nella cartella non vengono toccati.
- Se il Raspberry è spento all'orario previsto, quel backup non viene recuperato all'orario. All'avvio però il backend controlla l'ultimo backup riuscito: se è più vecchio di 8 giorni (o non esiste), ne esegue uno di recupero dopo 10 minuti.

## Verificare l'ultimo backup

Dall'interfaccia: **Impostazioni → Backup** mostra l'ultimo backup riuscito, l'eventuale errore e gli archivi presenti.

Da terminale:

```bash
docker compose exec backend python -m app.cli backup-status
cat backups/backup-errors.log        # una riga per ogni backup fallito
docker compose logs backend | grep -i backup
```

Un backup fallito non lascia archivi parziali: l'archivio viene scritto con estensione `.partial` e rinominato solo a fine operazione.

## Backup manuale

```bash
docker compose exec backend python -m app.cli backup
```

oppure **Impostazioni → Backup → Esegui backup ora**.

## Ripristino

Il ripristino sostituisce **tutti** i dati dell'app con quelli dell'archivio: database e cartella delle foto. Fermalo prima l'app, così nessuno scrive dati durante l'operazione.

```bash
docker compose stop backend web
docker compose run --rm backend python -m app.cli restore /backups/plants-backup-20261025-033000.tar --force
docker compose up -d
```

Cosa succede:

1. Viene letto `manifest.json` e controllato il formato.
2. Se il database contiene già dati e manca `--force`, l'operazione si ferma senza toccare nulla. Con `--force` viene chiesta una conferma esplicita (scrivi `ripristina`; `--yes` la salta).
3. Le tabelle dell'app vengono eliminate e ricreate con le migrazioni fino alla revisione indicata nel manifest. Le altre tabelle e gli altri database dell'istanza non vengono toccati.
4. I record vengono reinseriti e il numero di righe viene confrontato con il manifest.
5. Le foto vengono estratte in una cartella temporanea e poi sostituiscono `data/photos`. La cartella precedente non viene cancellata: viene rinominata in `data/photos-before-restore-AAAAMMGG-HHMMSS`, da eliminare a mano quando hai verificato il ripristino.
6. Lo schema viene aggiornato all'ultima versione dell'app (`alembic upgrade head`).

### Ripristinare solo il database o solo le foto

Il comando `restore` ripristina sempre entrambi, perché database e foto devono restare coerenti. Per recuperare singoli file di foto senza toccare il database:

```bash
mkdir /tmp/estratto && tar -xf backups/plants-backup-….tar -C /tmp/estratto photos/
```

e copia i file che ti servono in `data/photos/` mantenendo lo stesso percorso relativo.

### Dopo una reinstallazione o la sostituzione dei container

1. Recupera la cartella `backups/` (o almeno l'archivio più recente) e il file `.env`.
2. Se il database è andato perso, ricrea database e utente come in [installazione.md](installazione.md#1-database-e-utente-dedicati).
3. Clona il progetto, rimetti `.env` e i backup al loro posto e costruisci le immagini: `docker compose build`.
4. Esegui il ripristino come sopra (`--force` non serve se il database è vuoto).
5. `docker compose up -d` e accedi con le credenziali presenti nel backup.

## Provare il ripristino

È buona pratica verificare periodicamente che un backup sia ripristinabile, senza toccare l'installazione principale: crea un database di prova (`piante_prova`) con gli stessi permessi e lancia il ripristino puntando a quel database e a una cartella dati temporanea:

```bash
docker compose run --rm -e DB_NAME=piante_prova -e DATA_DIR=/tmp/prova \
    backend python -m app.cli restore /backups/plants-backup-….tar
```

Il comando stampa il numero di righe e di foto ripristinate; un conteggio diverso dal manifest produce un errore.

## Limiti

I backup restano sul disco del Raspberry: proteggono da errori, cancellazioni accidentali e aggiornamenti andati male, ma **non** da guasto o furto del Raspberry o della sua scheda/SSD. Copia periodicamente la cartella `backups/` su un altro dispositivo, ad esempio con `rsync` verso un PC o un NAS. Non è prevista una copia automatica sul cloud.
