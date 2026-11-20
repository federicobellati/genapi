# GENAPI — local-link-bot

Applicazione Python 3.11, FastAPI e Uvicorn. Avvio applicativo: `python main.py`, in ascolto su `0.0.0.0:8000`.

Gli endpoint sono definiti esclusivamente in `endpoints.py`; `local_link_bot.py` recupera il documento e interroga il modello. Prompt e policy sono file locali predisposti dall'amministratore.

## API

- `GET /status` o `/status/`: `{"message":"pong"}`; non interroga il modello.
- `GET /policies`: elenco per il menu della futura pagina web, inizialmente solo `ismar`.
- `POST /local-link-bot`: riceve esclusivamente `url` e `policy`, restituisce direttamente il report come `text/markdown; charset=utf-8`, con nome di download `report.md`.
- `POST /alvise-graph/query`: riceve esclusivamente `question`, interroga tramite Hermes il corpus Graphify Alvise Benetazzo e restituisce `text/markdown; charset=utf-8`, con nome di download `answer.md`.
- `GET /docs`: documentazione interattiva di FastAPI, utile per le prime prove prima di sviluppare l'interfaccia separata.

Corpo della richiesta:

```json
{"url":"https://seas-erddap.ve.ismar.cnr.it/erddap/info/TRP_CLVUE10_WATER_TURB_2/index.html","policy":"ismar"}
```

Non sono accettati prompt o policy arbitrari nell'input. Sono consentiti URL HTTP/HTTPS di qualsiasi sito, senza limitarsi a ERDDAP. Per HTML viene rimosso il codice di presentazione: si conservano tutto il testo della pagina, le destinazioni dei link, i tag `meta` e i blocchi JSON/JSON-LD incorporati; l'identificazione dei metadati resta al modello. Non vengono seguiti i link presenti nel documento. I normali redirect HTTP dell'URL vengono seguiti.

Sono supportati HTML e documenti testuali come Markdown, JSON, XML e CSV. Questa versione non esegue JavaScript delle pagine e non estrae testo da PDF, DOCX o altri formati binari. In caso di dati insufficienti il prompt richiede di dichiarare la non verificabilità.

## Pagina web separata

La pagina può caricare il menu da `/policies`, inviare il JSON a `/local-link-bot`, leggere il report con `response.text()` e consentirne il download tramite un `Blob` Markdown. L'API ammette via CORS origini HTTP e HTTPS sotto `*.ve.ismar.cnr.it`.

L'accesso pubblico previsto è `http://genapi.ve.ismar.cnr.it` sulla porta 80; il reverse proxy deve inoltrare al container sulla porta 8000. DNS e reverse proxy saranno configurati dall'amministratore dopo la prima verifica del container. Non occorre conoscere nel codice Python il nome della rete Docker.

## Configurazione del modello

Valori predefiniti nel codice: API `http://192.168.248.224:8080/v1`, modello `qwen3.6-35b-a3b`, timeout di risposta 600 secondi e limite di generazione 8192 token. Se necessario sono sovrascrivibili con le variabili del processo `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_MAX_TOKENS`; nessuna modifica al `.env` esistente è necessaria per i valori forniti.

Ogni richiesta scarica una sola risorsa e invia una sola richiesta al modello con prompt, policy completa e contenuto recuperato. Il report viene restituito in memoria, senza salvataggio o cronologia. Limite del documento: 1 MB; documenti entro questo limite possono comunque superare il contesto disponibile del modello, nel qual caso viene restituito un errore.

Errori: 413 documento troppo grande o oltre il contesto del modello (con conteggio dei token segnalato dal server); 415 formato non testuale; 422 input non valido o documento vuoto; 502 errore della fonte o del modello, risposta non valida o troncata; 504 timeout. Anche il timeout del reverse proxy dovrà consentire il completamento dell'analisi.

La pagina ERDDAP di esempio contiene anche JSON-LD con 442 riferimenti a file, che vengono conservati: nella prova il prompt completo ripulito richiede 83.270 token, oltre i 65.536 configurati sul server LLM. Per questa pagina occorre aumentare il contesto del server o fornire una rappresentazione più piccola del documento. L'applicazione segnala l'errore senza tagliare silenziosamente i metadati o cambiare l'URL.

## Query al corpus Alvise Benetazzo

```json
{"question":"What is the Impact of surface waves on ocean circulation?"}
```

Inviare questo JSON a `/alvise-graph/query`. La pagina legge il risultato con `response.text()`. Domanda obbligatoria, da 1 a 4000 caratteri dopo la rimozione degli spazi iniziali/finali; i campi aggiuntivi sono rifiutati con 422. L'endpoint usa il CORS già configurato.

`alvise_graph.py` conserva lato server il prompt di attivazione `graphify query:` e le sei regole del corpus, con lettura dei Markdown sorgente dello stesso corpus autorizzata dall'utente. Il percorso `/opt/data/home/alvise_benetazzo_articles_MD/graphify-out/` è fisso e si riferisce al filesystem di Hermes: GENAPI non deve montare o leggere direttamente il grafo. Hermes deve interrogare prima questo grafo e può leggere i relativi `.md` sotto `/opt/data/home/alvise_benetazzo_articles_MD/`, anche fuori da `graphify-out/`, identificandoli tramite la provenienza registrata nel grafo. Restano esclusi memoria, altre sessioni, web e altri corpus. Ogni richiesta invia una sola domanda a Hermes, senza cronologia o sessioni fornite dal client; skill e strumenti sono eseguiti da Hermes. Modello configurato nel servizio invariato; reasoning richiesto disattivato per questa richiesta, senza modificare le impostazioni Hermes.

La risposta deve distinguere EXTRACTED/INFERRED, citare i file .md del corpus e usare `Not found in the Alvise Benettazzo corpus` per informazioni assenti. Le regole sono istruzioni all'agente: il prompt fisso e la validazione dell'input non costituiscono un isolamento dei suoi strumenti o del filesystem. L'isolamento effettivo dipende dalla configurazione Hermes; GENAPI non verifica automaticamente la provenienza di ciascuna affermazione.

Nella prima prova del 20/11/2026 Hermes ha eseguito anche una ricerca senza percorso, che includeva la memoria dell'agente: il requisito di isolamento non è convalidato. La successiva autorizzazione ai Markdown dello stesso corpus supera il precedente vincolo alla sola directory `graphify-out/`; leggere quei documenti non equivale a usare fonti estranee. Il prompt aggiornato non è stato sottoposto a una nuova prova live. Per garantire l'isolamento occorrono accessi realmente limitati in Hermes.

Impostare `HERMES_API_KEY` nell'ambiente del processo/container GENAPI, mai nella pagina web. Nessuna chiave è inclusa nel codice. Base predefinita `http://docker03.ve.ismar.cnr.it:8642/v1`, sovrascrivibile con `HERMES_BASE_URL`; timeout predefinito 900 secondi (15 minuti), sovrascrivibile con `HERMES_TIMEOUT`, per consentire le risposte di circa 11 minuti osservate nelle prove. Un valore in un file `.env` di Compose deve essere passato esplicitamente al servizio per essere disponibile al processo. La configurazione Docker esistente non è stata modificata.

Errori: 422 input non valido; 503 chiave Hermes assente; 502 errore Hermes o risposta vuota, malformata o incompleta; 504 timeout. Configurare anche il timeout del reverse proxy per richieste lunghe. Il timeout HTTP non garantisce l'annullamento del lavoro già avviato su Hermes; nessun tentativo automatico di ripetizione.

## Verifiche

Test automatici con `python -m unittest discover -s tests -v`, dopo l'installazione delle dipendenze applicative e di `httpx==0.28.1` (solo per i test).

Verifiche locali del 18/11/2026: dieci test automatici; avvio reale di Uvicorn sulla porta 8000 con risposta HTTP 200 da `/status/`; richiesta completa su `https://example.com` con policy integrale e modello Qwen, HTTP 200 e report Markdown di 7.662 caratteri in circa 54 secondi. La pagina breve serve a verificare il flusso tecnico e non descrive un dataset scientifico. Le prove sono state eseguite con Python 3.12 disponibile localmente; il container resta configurato per Python 3.11.9 nel `.env` originale. Docker non è disponibile in questo ambiente, quindi non è stata eseguita una build del container.

Nel Dockerfile sono state applicate esclusivamente le due aggiunte mostrate e approvate dall'utente: `ARG PYTHON_CONTAINER_PORT` prima di `EXPOSE` e `CMD ["python", "main.py"]` subito dopo. `docker-compose.yml`, `.env`, rete e porte restano invariati. L'immagine deve essere ricostruita sul server per includere il codice e il comando di avvio aggiornati.
