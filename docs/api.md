# API REST

Tutte le rotte sono sotto `/api`. La documentazione interattiva generata da FastAPI (OpenAPI) è su `http://<host>:<porta>/api/docs` e lo schema JSON su `/api/openapi.json`. Queste due pagine descrivono solo le rotte e non richiedono login; per provare le chiamate serve comunque una sessione.

## Autenticazione

Il login crea una sessione lato server e imposta il cookie `plants_session` (`HttpOnly`, `SameSite=Strict`, limitato a `/api`, `Secure` con `COOKIE_SECURE=true`). La risposta contiene un `csrf_token` da inviare nell'header `X-CSRF-Token` di ogni richiesta che modifica dati (`POST`, `PUT`, `PATCH`, `DELETE`).

```bash
curl -c jar -H 'Content-Type: application/json' \
     -d '{"username":"io","password":"…"}' http://pi:8080/api/auth/login
# {"username":"io","csrf_token":"…"}

curl -b jar -H 'X-CSRF-Token: …' -H 'Content-Type: application/json' \
     -d '{"name":"Ginepro"}' http://pi:8080/api/plants
```

Dopo 5 tentativi di login falliti dallo stesso indirizzo in 15 minuti, il login risponde `429`.

| Metodo e rotta | Descrizione |
| --- | --- |
| `POST /auth/login` | Accesso |
| `POST /auth/logout` | Chiude la sessione corrente |
| `GET /auth/me` | Utente corrente e token CSRF |
| `POST /auth/password` | Cambio password (chiude le altre sessioni) |

## Errori

Le risposte di errore hanno la forma `{"detail": "messaggio in italiano"}`. Gli errori di validazione (`422`) aggiungono `errors: [{"field": "...", "message": "..."}]`.

| Codice | Significato |
| --- | --- |
| `401` | Sessione assente o scaduta |
| `403` | Token CSRF mancante o errato |
| `404` | Risorsa inesistente |
| `409` | Operazione in conflitto con lo stato attuale (es. completare una scadenza già saltata, nome duplicato) |
| `422` | Dati non validi |
| `503` | Database non raggiungibile o backup in corso |
| `507` | Spazio su disco esaurito durante il caricamento di foto |

## Piante, gruppi e tag

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /plants?q=&status=active\|archived\|all&group_id=&tag_id=` | Elenco e ricerca per nome, nome comune, specie, gruppo e tag |
| `POST /plants` | Crea; solo `name` è obbligatorio |
| `GET /plants/{id}` | Dettaglio |
| `PUT /plants/{id}` | Aggiorna tutti i campi, gruppo (`group_id`) e tag (`tag_ids`) |
| `POST /plants/{id}/archive` / `restore` | Archivia o ripristina |
| `DELETE /plants/{id}?confirm=<nome esatto>` | Eliminazione definitiva con diario, foto (anche i file), misurazioni e task |
| `GET/POST /groups`, `PUT/DELETE /groups/{id}` | Gruppi; eliminare un gruppo lascia le piante senza gruppo |
| `GET/POST /tags`, `PUT/DELETE /tags/{id}` | Tag; eliminare un tag lo rimuove dalle piante |

## Task e scadenze

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /plants/{id}/tasks` | Task della pianta con le scadenze aperte (`pending`: arretrate, di oggi e la prossima) |
| `POST /plants/{id}/tasks` | Crea un task |
| `GET /tasks/{id}` / `PUT /tasks/{id}` / `DELETE /tasks/{id}` | Dettaglio, modifica (vale per le scadenze future), eliminazione |
| `GET /tasks/{id}/history` | Scadenze gestite (completate, saltate, sospese) |
| `POST /tasks/{id}/suspend` | `{"days": 14}` oppure `{"until": "2026-04-01"}` (giorno di riattivazione) |
| `POST /tasks/{id}/resume` | Termina subito la sospensione |
| `POST /tasks/{id}/active` | `{"active": false}` disattiva il task senza eliminarlo |
| `POST /occurrences/{id}/complete` | Completa; corpo facoltativo `{"note": "...", "completed_at": "<ISO con fuso>"}` |
| `POST /occurrences/{id}/skip` | Salta la singola scadenza |
| `POST /occurrences/{id}/reopen` | Annulla completamento o skip; elimina la voce di diario collegata |

Esempio di creazione:

```json
{
  "name": "Innaffiatura",
  "task_type": "watering",
  "recurrence": "calendar",
  "calendar_rule": {"kind": "weekly", "weekdays": [0, 3]},
  "start_date": "2026-03-01",
  "end_date": null,
  "notify": "day_before"
}
```

- `task_type`: `watering`, `fertilizing`, `repotting`, `pruning`, `check`, `other`.
- `recurrence`: `once` (scadenza = `start_date`), `interval` (con `interval_days`), `calendar` (con `calendar_rule`).
- `calendar_rule`: `{"kind": "weekly", "weekdays": [0..6]}` con 0 = lunedì, oppure `{"kind": "monthly", "day": 1..31}`.
- `notify`: `none`, `day_of`, `day_before`, `both`.

Completare due volte la stessa scadenza è idempotente: la seconda risposta ha `already_completed: true` e lo stesso `diary_entry_id`.

## Dashboard e calendario

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /dashboard?days=7` | `overdue`, `due_today`, `upcoming`; esclude task sospesi o disattivati e piante archiviate |
| `GET /calendar?start=&end=&plant_id=&group_id=&tag_id=&task_type=&status=` | Scadenze nell'intervallo (massimo 400 giorni), comprese quelle completate e saltate |

Ogni scadenza riporta uno `status` tra `todo`, `overdue`, `completed`, `skipped`, `suspended` e `planned`. `planned` indica una data futura di un task a calendario oltre l'orizzonte già generato: ha `id: null` e non si può completare finché non diventa una scadenza effettiva. Il parametro `status` si può ripetere; `todo` include anche `planned`.

## Diario e foto

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /plants/{id}/diary?offset=0&limit=20` | Voci dalla più recente; `has_more` indica se ce ne sono altre |
| `POST /plants/{id}/diary` | `multipart/form-data`: `body`, `category`, `occurred_at`, `files` (ripetuto) |
| `PATCH /diary/{id}` | Modifica testo, categoria e data (per i completamenti solo la nota) |
| `DELETE /diary/{id}` | Elimina una voce manuale e le sue foto |
| `POST /diary/{id}/photos` | Aggiunge foto (`files`) a una voce, anche a un completamento |
| `GET /photos/{id}/file` | File della foto (richiede la sessione) |
| `DELETE /photos/{id}` | Elimina foto e file |

`kind` di una voce: `manual`, `task_completion`, `measurement`. Categorie: `growth`, `health`, `pruning`, `repotting`, `fertilizing`, `watering`, `other`.

```bash
curl -b jar -H 'X-CSRF-Token: …' -F body='Nuove gemme' -F category=growth \
     -F files=@foto1.jpg -F files=@foto2.jpg http://pi:8080/api/plants/3/diary
```

## Misurazioni

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /plants/{id}/measurements` | Tutte le misurazioni, dalla più recente |
| `GET /plants/{id}/measurements/charts?range=month\|year\|all` | Serie per tipo, in ordine di data |
| `POST /plants/{id}/measurements` | `{"kind": "height", "measured_on": "2026-03-01", "value": "31.5", "unit": "cm"}` |
| `PUT /measurements/{id}` / `DELETE /measurements/{id}` | Modifica, elimina |

`kind`: `height`, `width`, `trunk_diameter`. I valori sono memorizzati e restituiti in millimetri (`value_mm`); `unit` può essere `mm` (default) o `cm` e indica solo l'unità di inserimento.

## Sistema

| Metodo e rotta | Descrizione |
| --- | --- |
| `GET /health` | Stato del servizio e del database, senza autenticazione |
| `GET /settings` | Impostazioni non sensibili (versione, fuso, limiti foto, stato Telegram) |
| `POST /settings/telegram/test` | Messaggio Telegram di prova |
| `GET /backups` | Esito dell'ultimo backup ed elenco degli archivi |
| `POST /backups` | Backup immediato |
