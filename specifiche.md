# Specifica funzionale e tecnica
## Applicazione web per la gestione delle piante

**Versione:** 1.0  
**Stato:** Specifica iniziale consolidata  
**Lingua dell'interfaccia:** Italiano  
**Destinazione:** Raspberry Pi 5, 4 GB RAM  
**Utilizzo:** Personale, rete locale  
**Nome progetto:** Da definire

---

# 1. Obiettivo del progetto

Realizzare un'applicazione web per gestire una collezione personale di piante, tenendo traccia delle relative informazioni, delle attività di manutenzione, degli aggiornamenti fotografici e delle misurazioni nel tempo.

L'applicazione deve essere semplice da utilizzare quotidianamente, con particolare attenzione all'utilizzo da smartphone, e deve funzionare in modo affidabile su un Raspberry Pi 5 con 4 GB di RAM, sul quale sono già in esecuzione altri servizi Docker.

Il software deve essere un'applicazione completa e funzionante, non un prototipo o una semplice interfaccia dimostrativa.

## 1.1 Funzionalità principali

L'applicazione deve comprendere:

1. Gestione delle piante.
2. Organizzazione mediante gruppi e tag.
3. Dashboard operativa con task e ricerca delle piante.
4. Gestione di task ricorrenti e una tantum.
5. Completamento, skip e sospensione dei task.
6. Notifiche automatiche tramite Telegram.
7. Calendario con attività future, arretrate e completate.
8. Diario cronologico per ogni pianta.
9. Caricamento e gestione delle fotografie.
10. Registrazione delle misurazioni e visualizzazione dei grafici.
11. Archiviazione ed eliminazione delle piante.
12. Backup e ripristino dei dati.
13. Autenticazione mediante password.

---

# 2. Stack tecnologico obbligatorio

L'architettura deve utilizzare lo stack seguente. Non sostituire queste tecnologie con alternative senza una motivazione tecnica concreta e senza documentarla.

## 2.1 Frontend

- **React**
- **TypeScript**
- Vite come strumento di sviluppo e build, salvo incompatibilità motivata.
- React Router per la navigazione tra le pagine.
- Una libreria leggera per grafici, ad esempio Recharts.
- Una libreria per la visualizzazione del calendario, oppure un componente React dedicato se più leggero e adeguato.
- CSS responsive, con un sistema di componenti coerente e riutilizzabile.

Il frontend deve essere compilato in file statici di produzione e servito tramite un web server leggero, ad esempio Nginx.

Non utilizzare un server di sviluppo React in produzione.

### Requisiti del frontend

- Componenti riutilizzabili.
- Tipizzazione TypeScript rigorosa.
- Gestione centralizzata delle chiamate API.
- Gestione degli stati di caricamento, errore e assenza di dati.
- Validazione dei campi nei moduli.
- Interfaccia responsive per smartphone, tablet e PC.
- Navigazione semplice, senza schermate o passaggi inutili.
- Nessun accesso diretto al database dal browser.
- Nessun segreto o token Telegram incluso nel bundle frontend.

## 2.2 Backend

- **Python**
- **FastAPI**
- Pydantic per la validazione dei dati e degli schemi API.
- SQLAlchemy 2.x per l'accesso al database, con supporto asincrono se utile e compatibile con lo stack scelto.
- Alembic per le migrazioni dello schema del database.
- Driver MySQL compatibile con l'approccio SQLAlchemy scelto.
- Un sistema affidabile per la pianificazione dei task e delle notifiche.

Il backend deve esporre API REST documentate e utilizzare gli schemi OpenAPI generati da FastAPI.

### Requisiti del backend

- Validazione lato server di tutti gli input.
- Separazione tra router/API, logica di business e accesso ai dati.
- Gestione centralizzata delle eccezioni.
- Query parametrizzate tramite ORM o strumenti equivalenti sicuri.
- Autenticazione e autorizzazione per tutte le operazioni protette.
- Log applicativi senza password, token o altri segreti.
- Migrazioni versionate del database.
- Test automatici della logica di business.
- Compatibilità con Python e dipendenze disponibili per ARM64.

Non implementare la logica di ricorrenza esclusivamente nel frontend. Il backend è l'unica fonte autorevole per scadenze, completamenti, skip e notifiche.

## 2.3 Database

Utilizzare **MySQL già presente nell'ambiente Docker del Raspberry Pi**.

Non creare un nuovo container MySQL e non modificare automaticamente la configurazione dell'istanza esistente.

Il database dell'applicazione deve essere separato logicamente da quelli degli altri servizi, preferibilmente tramite un database dedicato e un utente con permessi minimi.

La connessione deve essere configurabile mediante variabili d'ambiente.

## 2.4 Deployment

Usare Docker Compose per distribuire i componenti dell'applicazione.

Il progetto deve prevedere, indicativamente:

- un container per il backend FastAPI;
- un container frontend/web server per i file React compilati;
- l'istanza MySQL già esistente, esterna al Compose dell'applicazione.

Non introdurre container aggiuntivi se non necessari.

La comunicazione tra frontend e backend deve essere configurata in modo esplicito. Il browser deve accedere alle API attraverso un percorso prevedibile, preferibilmente `/api`, evitando configurazioni CORS permissive non necessarie.

Tutti i servizi devono essere compatibili con architettura ARM64.

---

# 3. Ambiente di esecuzione e vincoli

Il software sarà ospitato su Raspberry Pi 5 con 4 GB di RAM, insieme ad altri servizi.

Di conseguenza:

- contenere il consumo di RAM e CPU;
- evitare microservizi non necessari;
- evitare sistemi di messaggistica o cache esterni senza una necessità concreta;
- non elaborare immagini in modo pesante se non indispensabile;
- non caricare tutte le fotografie contemporaneamente in memoria;
- limitare le dipendenze;
- utilizzare immagini Docker compatibili con ARM64;
- mantenere dati e file indipendenti dal ciclo di vita dei container;
- evitare operazioni di compilazione pesanti a ogni avvio;
- utilizzare una restart policy appropriata e healthcheck dove supportati.

Il sistema deve continuare a funzionare dopo riavvio del Raspberry, riavvio dei container e aggiornamento dell'applicazione.

Non è richiesto l'accesso pubblico a Internet. L'unica comunicazione esterna prevista per una funzionalità ordinaria è l'invio dei promemoria Telegram.

---

# 4. Utente e autenticazione

L'applicazione è destinata a un singolo utente.

È richiesto un account amministratore protetto da username e password.

Non sono necessari:
- gestione di più utenti;
- ruoli distinti;
- condivisione delle piante;
- registrazione pubblica;
- gestione di inviti.

La schermata di login deve essere semplice e responsive.

La password deve essere conservata esclusivamente come hash robusto, utilizzando una libreria e un algoritmo adatti alle password. Non salvarla mai in chiaro.

La sessione deve essere protetta e avere una procedura di logout.

Le API che modificano dati devono richiedere un'autenticazione valida. Proteggere le operazioni da richieste non autorizzate e, se si utilizzano cookie di sessione, adottare misure adeguate contro CSRF e furto della sessione.

Prevedere una procedura sicura per creare il primo account. Non distribuire credenziali predefinite note.

L'applicazione deve essere configurata per l'accesso dalla rete locale e non deve esporre automaticamente le porte del backend o del database verso Internet.

---

# 5. Struttura della navigazione

Le sezioni principali sono:

- Dashboard
- Calendario
- Piante
- Scheda della pianta
- Configurazione e informazioni essenziali dell'applicazione

La scheda di ogni pianta deve avere esattamente due tab principali:

1. **Diario**
2. **Modifica pianta**

Quando si apre una pianta, il tab iniziale deve essere il Diario.

I task della pianta devono essere raggiungibili dalla relativa scheda e devono poter essere completati, saltati o sospesi senza dover passare dal calendario.

---

# 6. Dashboard

La dashboard è una schermata operativa.

Non deve contenere statistiche decorative, grafici riepilogativi o riquadri con il numero totale di piante e task.

## 6.1 Task visibili

Mostrare:

- task da eseguire oggi;
- task in ritardo;
- task in scadenza nei prossimi giorni.

Il numero di giorni futuri visualizzati può essere configurabile. In assenza di una scelta specifica, utilizzare un intervallo predefinito ragionevole, ad esempio i successivi 7 giorni.

I task devono essere ordinati in modo da rendere immediatamente visibili quelli in ritardo e quelli in scadenza oggi.

Per ogni task mostrare almeno:

- nome della pianta;
- nome del task;
- scadenza;
- indicazione chiara se è in ritardo;
- azioni disponibili.

Le piante archiviate e i task sospesi non devono comparire tra le attività operative.

## 6.2 Completamento rapido

L'utente deve poter completare un task direttamente dalla dashboard.

Il completamento deve essere immediato e non deve richiedere l'inserimento di testo, fotografie o altre informazioni.

Dopo il completamento, il sistema può proporre di aggiungere facoltativamente una nota o una fotografia al diario. L'utente deve poter ignorare la proposta senza annullare il completamento.

## 6.3 Skip rapido

Deve essere disponibile un'azione distinta per saltare un task.

Lo skip non equivale a completamento e deve essere registrato nello storico.

L'interfaccia deve distinguere chiaramente le due azioni per evitare errori.

## 6.4 Ricerca delle piante

La dashboard deve contenere una ricerca per pianta.

Selezionando un risultato, si apre la scheda corrispondente, inizialmente sul tab Diario.

La ricerca deve trovare almeno le piante per nome. È preferibile supportare anche specie, gruppo e tag.

---

# 7. Gestione delle piante

## 7.1 Campi della scheda

Ogni pianta deve avere un nome identificativo obbligatorio.

Tutti gli altri campi sono facoltativi:

- nome comune;
- specie botanica;
- data di acquisizione;
- substrato e composizione;
- posizione;
- informazioni sul vaso;
- stile e obiettivi di coltivazione;
- note permanenti;
- gruppo;
- tag;
- data di creazione;
- data di ultima modifica;
- stato della pianta.

Le tipologie di piante di riferimento sono:

- bonsai e prebonsai;
- piante da interno;
- piante da esterno;
- terrari.

Queste tipologie non devono imporre campi obbligatori aggiuntivi. Una pianta può essere salvata anche quando non se ne conosce la specie o quando alcuni campi non sono pertinenti.

## 7.2 Note permanenti

Le note permanenti sono informazioni stabili associate alla scheda della pianta.

Devono essere distinte dalle voci del diario, che sono cronologiche.

Modificare le note permanenti non deve creare automaticamente una voce nel diario, salvo futura funzionalità esplicitamente richiesta.

## 7.3 Gruppi

Ogni pianta può appartenere a un gruppo.

I gruppi sono indipendenti, senza gerarchia o sottogruppi obbligatori.

Esempi:

- Balcone sud
- Balcone nord
- Interno
- Serra

Una pianta può appartenere a un solo gruppo alla volta. Deve essere possibile cambiare gruppo o lasciare la pianta senza gruppo.

## 7.4 Tag

Ogni pianta può avere zero o più tag.

Esempio:

- gruppo: `Balcone sud`;
- tag: `Bonsai`;
- tag: `Conifera`.

I tag sono indipendenti dai gruppi e possono essere condivisi da più piante.

Consentire di creare, modificare e rimuovere i tag, gestendo correttamente le associazioni esistenti.

## 7.5 Archiviazione ed eliminazione

Ogni pianta può essere:

- attiva;
- archiviata;
- eliminata definitivamente.

L'archiviazione deve nascondere la pianta dalle liste operative predefinite senza cancellare diario, foto, misurazioni o storico.

Una pianta archiviata non deve generare notifiche e i suoi task non devono comparire nella dashboard operativa.

La pianta archiviata deve poter essere riaperta e consultata.

L'eliminazione definitiva deve richiedere una conferma esplicita e gestire coerentemente tutti i dati collegati, compresi gli allegati. Non devono rimanere file orfani.

---

# 8. Scheda della pianta

La scheda della pianta deve contenere due tab.

## 8.1 Tab Diario

È il tab iniziale.

Deve mostrare gli aggiornamenti cronologici, le fotografie, gli eventi dei task e le registrazioni delle misurazioni.

Le voci devono essere ordinate dalla più recente alla più vecchia.

Il diario deve essere consultabile senza passare alla modalità di modifica della pianta.

## 8.2 Tab Modifica pianta

Deve permettere di modificare i campi della scheda, le note permanenti, il gruppo e i tag.

Da questo contesto devono essere raggiungibili le operazioni di archiviazione e di eliminazione definitiva.

Le azioni sui task devono essere disponibili nella scheda della pianta senza introdurre un terzo tab principale. La disposizione interna può essere una sezione dedicata, purché rimanga chiara e semplice.

---

# 9. Diario della pianta

Il diario è una timeline cronologica che raccoglie le attività significative relative alla pianta.

Deve includere:

1. aggiornamenti manuali;
2. completamenti dei task;
3. misurazioni registrate;
4. eventuali note e fotografie associate ai completamenti.

## 9.1 Aggiornamenti manuali

Ogni voce può contenere:

- data e ora;
- testo;
- categoria facoltativa;
- fotografie.

Le categorie iniziali suggerite sono:

- crescita;
- salute;
- potatura;
- rinvaso;
- concimazione;
- irrigazione;
- altro.

La categoria non deve essere obbligatoria.

L'utente deve poter creare, modificare ed eliminare le voci manuali.

## 9.2 Eventi automatici

Ogni completamento di un task deve generare una registrazione nello storico e un evento visibile nel diario della pianta.

L'evento deve contenere almeno:

- nome del task;
- data e ora effettiva di completamento;
- eventuale nota aggiunta;
- eventuali fotografie associate.

Le voci generate automaticamente devono essere distinguibili da quelle inserite manualmente.

Le misurazioni devono essere visibili nel contesto del diario, o tramite una voce cliccabile che apra il dettaglio della misurazione.

Il diario non deve diventare l'unica fonte dei dati: gli eventi devono mantenere un riferimento alle entità originali, così che le modifiche non producano inconsistenze.

## 9.3 Note e foto dopo un completamento

Dopo aver completato un task, l'app può offrire la possibilità di aggiungere una nota e/o fotografie.

Questi campi sono facoltativi.

Il completamento deve essere già registrato prima che l'utente decida se aggiungere informazioni.

L'utente deve poter chiudere la proposta senza perdere il completamento.

Deve essere possibile eliminare un completamento registrato per errore, con conferma quando l'operazione modifica le scadenze future. Diario, storico e pianificazione devono rimanere coerenti.

---

# 10. Fotografie

Le fotografie devono essere salvate localmente sul Raspberry Pi in una directory persistente.

Non è richiesta l'integrazione con servizi cloud.

## 10.1 Funzionalità

- Caricamento dal telefono.
- Caricamento dal computer.
- Selezione di file dalla galleria o dal filesystem del dispositivo.
- Massimo iniziale di 10 fotografie per singolo aggiornamento o evento.
- Visualizzazione delle immagini in galleria.
- Apertura a schermo intero.
- Navigazione tra le fotografie.
- Eliminazione di una singola fotografia.

L'interfaccia deve funzionare sia con mouse sia con touchscreen.

## 10.2 Requisiti tecnici

- Validare il tipo di file sul backend.
- Impostare un limite massimo di dimensione per file.
- Non fidarsi del nome file fornito dal client.
- Generare nomi file sicuri e univoci.
- Conservare nel database il percorso relativo e i metadati necessari.
- Non memorizzare immagini binarie direttamente nel database, salvo motivazione tecnica documentata.
- Non caricare tutte le immagini in memoria contemporaneamente.
- Gestire gli errori di caricamento e lo spazio esaurito.

I formati supportati e il limite di dimensione per foto devono essere documentati. Il valore massimo deve essere scelto in modo ragionevole per l'uso su Raspberry Pi e configurabile.

L'eliminazione di una foto deve rimuovere il riferimento dal database e il file effettivo, evitando file orfani.

---

# 11. Misurazioni

L'applicazione deve permettere di registrare manualmente le misure della pianta quando l'utente lo desidera.

Le misurazioni non sono associate ai task e non devono richiedere il completamento di un'attività.

## 11.1 Tipi di misura

Prevedere tre tipologie iniziali, fisse:

1. Altezza della pianta.
2. Larghezza della pianta.
3. Diametro del tronco.

Il diametro del tronco è misurato con il calibro.

Non è richiesto che l'utente possa creare liberamente nuove tipologie di misurazione.

## 11.2 Dati della misurazione

Ogni rilevazione deve contenere:

- pianta associata;
- tipo di misura;
- data della rilevazione;
- valore numerico;
- unità di misura.

L'unità predefinita deve essere il millimetro (`mm`).

Se vengono offerte altre unità, la conversione deve essere corretta e i valori devono essere visualizzati in modo coerente.

L'utente deve poter inserire una misura con una data precedente, nel caso in cui la registri in un secondo momento.

Deve essere possibile modificare ed eliminare una misurazione.

## 11.3 Grafici

Prevedere un grafico separato per ciascun tipo di misura.

I grafici devono mostrare l'evoluzione nel tempo, usando la data della rilevazione sull'asse temporale.

L'utente deve poter scegliere l'intervallo:

- ultimo mese;
- ultimo anno;
- tutto lo storico.

L'interfaccia deve gestire correttamente assenza di dati, date duplicate e valori mancanti.

Le misurazioni devono essere consultabili dal diario o da una sezione chiaramente accessibile nella scheda della pianta.

---

# 12. Task

Un task è un'attività collegata a una pianta.

Può essere ricorrente a intervallo, ricorrente a calendario oppure una tantum.

## 12.1 Campi del task

Ogni task deve poter contenere:

- nome obbligatorio;
- tipologia;
- descrizione o nota facoltativa;
- data iniziale o prima scadenza;
- eventuale data finale;
- regola di ricorrenza;
- impostazioni di notifica;
- stato attivo o sospeso;
- storico delle occorrenze.

Le tipologie predefinite possono comprendere:

- innaffiatura;
- fertilizzazione;
- rinvaso;
- potatura;
- controllo;
- altro.

Deve essere possibile assegnare un nome personalizzato.

Le note non devono essere obbligatorie.

## 12.2 Task a intervallo

Esempio: innaffiare ogni 7 giorni oppure fertilizzare ogni 14 giorni.

La prossima scadenza deve essere calcolata a partire dalla data/ora effettiva di completamento.

Esempio:

- intervallo impostato: 14 giorni;
- completamento effettivo: 20 marzo;
- prossima scadenza: 3 aprile.

Il ritardo rispetto alla scadenza precedente non deve essere propagato alla successiva.

Se un task non è mai stato completato, la prima scadenza deve derivare dalla data iniziale o dalla prima scadenza configurata.

## 12.3 Task a calendario

Esempi:

- ogni lunedì;
- ogni venerdì;
- il giorno 15 di ogni mese.

Il calendario deve restare ancorato alle date previste.

Se un task previsto lunedì viene completato martedì, la successiva scadenza resta il lunedì previsto dalla regola, non il martedì successivo.

Le scadenze non completate devono restare visibili come arretrate finché non vengono completate o saltate.

Le occorrenze successive continuano a essere generate secondo il calendario originario.

Ogni occorrenza deve essere identificabile separatamente, in modo che completamento o skip di una scadenza non modifichino retroattivamente le altre.

Per ricorrenze mensili in mesi più corti, implementare una regola prevedibile e documentata, ad esempio usare l'ultimo giorno del mese quando il giorno richiesto non esiste.

## 12.4 Task una tantum

Un task una tantum ha una sola scadenza.

Dopo il completamento o lo skip non deve generare ulteriori occorrenze.

## 12.5 Completamento

Quando un task viene completato, il backend deve:

1. registrare data e ora effettive;
2. aggiornare lo stato dell'occorrenza;
3. creare una voce nel diario;
4. conservare lo storico;
5. calcolare la prossima scadenza secondo la modalità di ricorrenza;
6. evitare doppi completamenti dovuti a richieste ripetute.

L'aggiunta di note e foto deve rimanere facoltativa.

## 12.6 Skip

L'utente deve poter saltare una singola occorrenza dalla dashboard o dalla scheda della pianta.

Lo skip deve:

- essere distinto dal completamento;
- registrare lo stato di occorrenza come saltato;
- conservare lo storico;
- non generare notifiche per l'occorrenza saltata;
- non essere conteggiato come completamento.

Per i task a calendario, lo skip di una scadenza non modifica il calendario originario.

Per i task a intervallo, la prossima scadenza si basa sull'ultima esecuzione effettiva. Se non esiste alcuna esecuzione precedente, applicare una regola iniziale documentata e coerente.

## 12.7 Sospensione

L'utente deve poter sospendere temporaneamente un task:

- per una durata;
- fino a una data specifica.

Durante la sospensione:

- il task non compare nella dashboard operativa;
- non vengono inviate notifiche;
- la configurazione del task viene conservata;
- lo storico non viene cancellato.

Alla scadenza della sospensione, il task deve tornare attivo.

Il comportamento per le scadenze che cadono durante la sospensione deve essere documentato. La riattivazione non deve produrre un invio massivo di notifiche arretrate.

## 12.8 Modifica dei task

Le modifiche alla configurazione di un task devono valere per le scadenze future.

Lo storico dei completamenti passati non deve essere modificato retroattivamente.

Se viene cambiata la regola di ricorrenza, aggiornare le occorrenze future non ancora gestite senza riscrivere le registrazioni storiche.

## 12.9 Eliminazione e correzione

Deve essere possibile correggere un completamento registrato per errore.

La correzione deve mantenere coerenti:

- storico;
- diario;
- stato dell'occorrenza;
- prossime scadenze.

L'eliminazione di un task non deve cancellare silenziosamente lo storico. Preferire una disattivazione oppure una conferma esplicita che spieghi le conseguenze.

---

# 13. Regole degli stati e delle scadenze

Il modello dati deve distinguere almeno:

- da fare;
- in ritardo;
- completato;
- saltato;
- sospeso, quando applicabile.

Lo stato in ritardo può essere derivato dal confronto tra data prevista e stato dell'occorrenza, mentre completato e saltato sono stati registrati esplicitamente.

Non rappresentare una stessa occorrenza come completata e saltata contemporaneamente.

Per i task a calendario, ogni data prevista deve essere una singola occorrenza. Se l'utente salta quella del 5, l'occorrenza del 5 diventa saltata e quella del 12 rimane la successiva scadenza.

Le occorrenze precedenti non devono scomparire dallo storico.

Per i task a intervallo, non generare una sequenza infinita di scadenze arretrate: il task mantiene la prossima scadenza determinata dalle regole dell'intervallo.

---

# 14. Calendario

Il calendario deve avere due viste:

1. mensile;
2. agenda cronologica.

Deve permettere di consultare le attività future e quelle passate, comprese quelle completate.

## 14.1 Informazioni visualizzate

Ogni voce deve mostrare almeno:

- nome del task;
- nome della pianta;
- data prevista;
- stato.

Distinguere visivamente gli stati, con colori e/o icone accessibili.

## 14.2 Filtri

Prevedere filtri per:

- pianta;
- gruppo;
- tag;
- tipologia di task;
- stato.

## 14.3 Interazioni

Cliccando su un task nel calendario si deve aprire la scheda della relativa pianta.

Non è richiesto completare o saltare un task direttamente dal calendario.

Queste azioni sono disponibili nella dashboard o nella scheda della pianta.

---

# 15. Notifiche Telegram

Le notifiche Telegram devono essere inviate automaticamente dal backend, senza richiedere che l'utente tenga aperto il browser.

La configurazione deve avvenire tramite variabili d'ambiente.

## 15.1 Configurazione

Prevedere variabili equivalenti a:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_ENABLED`
- `TZ`

I nomi definitivi devono essere documentati e riportati in `.env.example`.

Non inserire token reali nel codice, nel repository o nel frontend.

Fornire istruzioni per creare il bot Telegram, ricavare il chat ID e configurare l'ambiente.

## 15.2 Impostazioni per task

Ogni task deve poter scegliere una delle seguenti opzioni:

- nessuna notifica;
- il giorno della scadenza;
- il giorno prima;
- giorno prima e giorno della scadenza.

Le impostazioni devono essere configurabili indipendentemente per ogni task.

## 15.3 Regole di invio

Inviare esclusivamente promemoria programmati.

Non inviare notifiche per:

- completamento;
- skip;
- task sospesi;
- task appartenenti a piante archiviate;
- task già completati per la stessa occorrenza.

Non inviare notifiche aggiuntive per il solo fatto che un task è in ritardo.

Il significato di “giorno prima” deve essere basato sul calendario locale e non su una finestra mobile di 24 ore.

## 15.4 Affidabilità

Il sistema deve evitare duplicati dopo un riavvio del container.

Conservare un registro delle notifiche inviate, identificando almeno l'occorrenza e il tipo di promemoria.

La pianificazione deve continuare a funzionare anche quando nessun browser è aperto.

Gli errori di invio devono essere registrati senza esporre token o dati sensibili. Prevedere tentativi successivi limitati.

Se Telegram non è configurato, l'applicazione deve continuare a funzionare normalmente, senza bloccare la creazione o la gestione dei task.

---

# 16. Database MySQL

Il database deve essere MySQL, utilizzando l'istanza Docker esistente.

Non aggiungere un servizio database al Compose dell'app.

## 16.1 Configurazione della connessione

Usare variabili d'ambiente equivalenti a:

- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`

La connessione deve essere configurabile senza modificare il codice.

Non assumere che `localhost` sia corretto da un container. Documentare come impostare l'host in base alla rete Docker e alla configurazione MySQL già presente.

Non modificare automaticamente la configurazione degli altri servizi o i dati dell'istanza esistente.

## 16.2 Migrazioni

Usare Alembic o un sistema equivalente di migrazioni versionate.

Le migrazioni devono consentire di creare e aggiornare lo schema senza perdere dati esistenti.

Non eseguire cancellazioni distruttive automatiche durante l'avvio.

La creazione iniziale del database e dell'utente dedicato deve essere documentata.

## 16.3 Consistenza

Usare transazioni per operazioni che aggiornano contemporaneamente stato, storico e diario.

Prevedere indici per le query frequenti, ad esempio:

- task per data prevista e stato;
- task appartenenti a una pianta;
- voci del diario per pianta e data;
- misurazioni per pianta, tipo e data;
- registro delle notifiche.

Evitare duplicazioni non necessarie tra tabelle.

---

# 17. Modello dati indicativo

Il modello può essere adattato all'implementazione, ma deve rappresentare almeno le seguenti entità.

## 17.1 Plant

Campi indicativi:

- ID;
- nome;
- nome comune;
- specie;
- data acquisizione;
- substrato;
- posizione;
- dati vaso;
- stile;
- note permanenti;
- gruppo;
- stato;
- data creazione;
- data modifica.

## 17.2 Group

- ID;
- nome;
- eventuale descrizione;
- data creazione.

## 17.3 Tag

- ID;
- nome;
- eventuale colore o descrizione.

## 17.4 PlantTag

Tabella associativa tra piante e tag.

Deve impedire associazioni duplicate.

## 17.5 Task

Contiene la definizione del task:

- ID;
- pianta;
- nome;
- tipo;
- descrizione;
- modalità di ricorrenza;
- configurazione della ricorrenza;
- prima scadenza;
- eventuale data finale;
- impostazioni di notifica;
- stato;
- informazioni di sospensione;
- data creazione e modifica.

## 17.6 TaskOccurrence

Rappresenta la singola scadenza di un task.

Campi indicativi:

- ID;
- task;
- data prevista;
- stato;
- data/ora di completamento, se presente;
- data/ora dello skip, se presente;
- informazioni necessarie a conservare lo storico.

La singola occorrenza deve poter essere identificata senza ambiguità.

## 17.7 DiaryEntry

- ID;
- pianta;
- tipo di voce;
- categoria;
- titolo o testo;
- data/ora dell'evento;
- eventuale riferimento all'evento originale;
- data creazione e modifica.

I tipi di voce devono distinguere almeno gli aggiornamenti manuali, i completamenti dei task e le misurazioni.

## 17.8 Photo

- ID;
- voce del diario;
- percorso relativo;
- nome sicuro del file;
- tipo MIME;
- dimensione;
- data caricamento.

## 17.9 Measurement

- ID;
- pianta;
- tipo di misura;
- data rilevazione;
- valore;
- unità.

## 17.10 NotificationLog

- ID;
- task;
- occorrenza;
- tipo di promemoria;
- data/ora pianificata;
- data/ora di invio;
- esito;
- informazioni minime per evitare duplicati.

## 17.11 User

Contiene le credenziali del singolo account amministratore, con password memorizzata esclusivamente tramite hash robusto.

Il modello deve prevedere chiavi esterne, indici e regole di eliminazione coerenti.

Non eliminare lo storico tramite cascata senza una decisione esplicita.

---

# 18. Archiviazione locale e filesystem

Database e fotografie devono essere conservati in percorsi persistenti esterni al filesystem effimero dei container.

La struttura esatta può essere scelta durante l'implementazione, ma deve essere semplice da comprendere e gestire.

Esempio indicativo:

```text
app/
├── backend/
├── frontend/
├── docker-compose.yml
├── .env
├── .env.example
├── data/
│   └── photos/
├── backups/
└── docs/
```

Questa struttura è un esempio: non è obbligatorio adottare esattamente questi percorsi.

Il file `.env` reale deve essere escluso dal controllo versione.

I dati persistenti devono essere montati esplicitamente nei container. Ricreare un container non deve cancellare fotografie, configurazione o altri dati dell'applicazione.

---

# 19. Backup e ripristino

Il sistema deve prevedere un backup automatico settimanale, conservato sul disco del Raspberry Pi.

Le copie devono essere conservate per 30 giorni. Le copie più vecchie devono essere eliminate automaticamente.

## 19.1 Contenuto del backup

Il backup deve includere:

- database dell'applicazione;
- fotografie;
- allegati;
- informazioni necessarie al ripristino;
- versione dello schema e data del backup.

Database e fotografie devono rappresentare uno stato coerente.

Utilizzare un metodo di esportazione MySQL affidabile, con procedure documentate per evitare copie incoerenti.

## 19.2 Operazioni richieste

Fornire procedure per:

- verificare l'esito dell'ultimo backup;
- eseguire un backup manuale;
- ripristinare il database;
- ripristinare le fotografie;
- ripristinare l'app dopo reinstallazione o sostituzione dei container.

I backup devono avere nomi identificabili per data e devono produrre log in caso di errore.

Il ripristino deve essere documentato e testabile.

Il backup locale protegge da alcuni errori logici e applicativi, ma non protegge dalla perdita fisica del Raspberry o del suo disco. Questa limitazione deve essere riportata nella documentazione.

Non è richiesta una copia automatica cloud.

---

# 20. Configurazione tramite ambiente

Fornire un file `.env.example` privo di segreti reali.

Le variabili previste devono includere almeno:

```dotenv
# Applicazione
APP_ENV=production
APP_PORT=8000
TZ=Europe/Rome

# MySQL esistente
DB_HOST=
DB_PORT=3306
DB_NAME=
DB_USER=
DB_PASSWORD=

# Sicurezza
SECRET_KEY=

# Telegram
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Backup
BACKUP_RETENTION_DAYS=30
BACKUP_SCHEDULE=
BACKUP_DIR=
```

Questo è un esempio iniziale. L'IA sviluppatrice deve definire i nomi definitivi, documentarli e assicurarsi che tutti siano realmente utilizzati dall'applicazione.

I valori segreti non devono essere committati nel repository.

Non inserire token Telegram, password MySQL o chiavi di sessione nei log.

---

# 21. API backend

Il backend FastAPI deve fornire API REST coerenti, documentate e validate.

Le rotte esatte possono essere definite durante l'implementazione, mantenendo una struttura prevedibile.

Le aree API devono comprendere:

- autenticazione;
- piante;
- gruppi;
- tag;
- diario;
- fotografie;
- misurazioni;
- task;
- occorrenze;
- completamenti;
- skip;
- sospensioni;
- calendario;
- impostazioni non sensibili;
- stato del servizio e backup, se esposti nell'interfaccia.

Le operazioni di completamento, skip e modifica delle ricorrenze devono essere implementate nel backend, non simulate nel frontend.

Utilizzare codici HTTP coerenti e messaggi d'errore comprensibili.

Non esporre credenziali o configurazioni sensibili tramite API pubbliche.

---

# 22. Requisiti di sicurezza e affidabilità

- Autenticazione obbligatoria.
- Password conservate solo tramite hash robusto.
- Validazione degli input sul server.
- Query parametrizzate.
- Protezione delle API di modifica.
- Protezione adeguata delle sessioni.
- Segreti configurati tramite ambiente.
- Nessuna esposizione pubblica automatica.
- Nessuna informazione sensibile nei log.
- Limiti ragionevoli per upload e dimensione dei campi.
- Gestione degli errori di database e filesystem.
- Nessuna perdita di dati al riavvio.
- Nessun file immagine accessibile pubblicamente senza controllo, se ciò può esporre dati dell'applicazione.
- Nessuna operazione distruttiva automatica senza una procedura esplicita.
- Gestione corretta di data, ora e fuso orario.

Il servizio deve continuare a funzionare anche se Telegram non è raggiungibile.

---

# 23. Interfaccia e design

Lo stile deve essere minimalista, pulito e moderno.

Evitare:
- interfacce troppo dense;
- statistiche decorative nella dashboard;
- animazioni non necessarie;
- moduli lunghi per operazioni rapide;
- conferme ridondanti per azioni ordinarie;
- campi obbligatori non giustificati.

L'interfaccia deve essere responsive e adatta a uno smartphone utilizzato mentre si lavora sulle piante.

I pulsanti di completamento e skip devono essere facilmente raggiungibili e distinguibili.

Le immagini devono adattarsi allo schermo e poter essere aperte a schermo intero.

I grafici devono essere leggibili anche su schermi piccoli.

Prevedere stati vuoti con indicazioni utili, per esempio quando non esistono ancora misurazioni o task.

Usare etichette accessibili, contrasto adeguato, focus da tastiera e indicatori di stato non basati esclusivamente sul colore.

---

# 24. Test automatici obbligatori

L'IA sviluppatrice deve implementare test automatici per le regole più importanti.

## 24.1 Piante

- Creazione con il solo nome.
- Modifica dei campi facoltativi.
- Associazione di un gruppo.
- Associazione di più tag.
- Archiviazione senza perdita dei dati.
- Eliminazione definitiva con gestione degli allegati.

## 24.2 Diario e foto

- Creazione di una voce manuale.
- Creazione di una voce con categoria.
- Caricamento di una o più foto.
- Rifiuto di file non supportati.
- Eliminazione di una foto.
- Visualizzazione corretta degli eventi automatici.

## 24.3 Misurazioni

- Inserimento di una misurazione in mm.
- Inserimento di una misura con data passata.
- Modifica ed eliminazione.
- Ordinamento temporale.
- Dati corretti per i grafici.

## 24.4 Task

- Creazione di un task una tantum.
- Creazione di un task a intervallo.
- Creazione di un task a calendario.
- Completamento.
- Skip.
- Sospensione.
- Riattivazione.
- Modifica della ricorrenza.
- Correzione di un completamento.
- Gestione delle occorrenze arretrate.
- Assenza di duplicati in caso di richieste ripetute.

## 24.5 Notifiche

- Invio del promemoria il giorno prima.
- Invio del promemoria il giorno della scadenza.
- Rispetto dell'impostazione di ciascun task.
- Nessun invio per task sospesi o saltati.
- Nessun invio per piante archiviate.
- Nessun duplicato dopo un riavvio.
- Gestione degli errori Telegram.

## 24.6 Backup

- Creazione del backup.
- Inclusione del database e delle fotografie.
- Applicazione della retention di 30 giorni.
- Procedura di ripristino documentata.

---

# 25. Criteri di accettazione finali

Il progetto è considerato completo quando:

1. L'applicazione si avvia su Raspberry Pi 5 ARM64.
2. Non crea un nuovo container MySQL.
3. È possibile autenticarsi con password.
4. È possibile creare una pianta indicando soltanto il nome.
5. La dashboard mostra task operativi e ricerca delle piante, senza statistiche decorative.
6. Selezionando una pianta si apre il Diario.
7. La scheda dispone dei tab Diario e Modifica pianta.
8. Si possono gestire gruppi e più tag per pianta.
9. Si possono archiviare e recuperare le piante.
10. Si possono inserire aggiornamenti con foto dal telefono e dal computer.
11. Le foto si possono aprire a schermo intero ed eliminare.
12. Il diario registra i completamenti dei task.
13. È possibile aggiungere note e foto facoltative al completamento.
14. Si possono registrare altezza, larghezza e diametro del tronco.
15. Le misurazioni hanno data, valore e unità predefinita mm.
16. I grafici consentono di scegliere l'intervallo temporale.
17. I task a intervallo ripartono dal completamento effettivo.
18. I task a calendario mantengono il calendario originario.
19. Le scadenze arretrate restano visibili fino al completamento o allo skip.
20. Si possono saltare task dalla dashboard.
21. Si possono sospendere task per una durata o fino a una data.
22. Le modifiche ai task non alterano lo storico passato.
23. Il calendario mostra viste mensile e agenda.
24. Il calendario permette di consultare anche i task completati.
25. Cliccando su un task nel calendario si apre la pianta.
26. Telegram invia promemoria programmati senza duplicati.
27. I task sospesi, saltati e delle piante archiviate non generano notifiche.
28. Il backup viene eseguito settimanalmente.
29. I backup vengono conservati per 30 giorni.
30. Database, foto e configurazione persistono dopo la ricreazione dei container.
31. Il ripristino è documentato.
32. L'interfaccia è utilizzabile da smartphone e PC.
33. Le operazioni principali sono coperte da test automatici.

---

# 26. Consegne richieste all'IA sviluppatrice

Consegnare il progetto completo, comprendente:

- codice React + TypeScript;
- codice Python + FastAPI;
- configurazione Docker Compose dell'applicazione;
- Dockerfile compatibili con ARM64;
- file `.env.example`;
- migrazioni MySQL;
- test automatici;
- documentazione delle API;
- guida di installazione;
- guida di configurazione Telegram;
- guida di backup e ripristino;
- descrizione delle cartelle e dei volumi persistenti;
- elenco delle variabili d'ambiente;
- istruzioni di aggiornamento;
- documentazione delle decisioni tecniche e dei casi limite.

Prima di concludere lo sviluppo, verificare l'intero flusso con almeno:

1. una pianta;
2. un gruppo e più tag;
3. una voce di diario con fotografie;
4. una misurazione;
5. un task una tantum;
6. un task a intervallo;
7. un task a calendario;
8. un completamento;
9. uno skip;
10. una sospensione;
11. un promemoria Telegram;
12. un backup e un ripristino di prova.

Non dichiarare completato il progetto sulla base della sola compilazione del frontend o dell'avvio dei container: le funzionalità devono essere effettivamente collegate al backend e al database.

---

# 27. Decisioni ancora da definire durante lo sviluppo

Le seguenti decisioni non devono bloccare il progetto, ma vanno documentate prima del rilascio:

- scelta definitiva della libreria calendario;
- scelta definitiva della libreria grafici;
- modalità precisa di connessione alla rete Docker dell'istanza MySQL esistente;
- comportamento delle scadenze che cadono durante una sospensione;
- comportamento dei task a intervallo mai completati e poi saltati;
- dimensione massima e formati delle fotografie;
- orario settimanale del backup;
- gestione del giorno 29, 30 o 31 nelle ricorrenze mensili;
- procedura iniziale per creare il primo account;
- politica per il ricalcolo delle scadenze future dopo una correzione del completamento;
- eventuale limite massimo delle occorrenze future generate per il calendario.

Per ogni scelta, adottare la soluzione più semplice e affidabile che rispetti i requisiti. Documentare il comportamento e aggiungere test quando influisce sulle regole di business.

**Priorità generale:** affidabilità dei dati, correttezza delle ricorrenze, semplicità d'uso, compatibilità con Raspberry Pi 5 e facilità di manutenzione.
