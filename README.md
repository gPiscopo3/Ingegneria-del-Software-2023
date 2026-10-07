# GraphApp — Collaboration Graph Project

[![Python application](https://github.com/gPiscopo3/Ingegneria-del-Software-2023/actions/workflows/python-app.yml/badge.svg)](https://github.com/gPiscopo3/Ingegneria-del-Software-2023/actions/workflows/python-app.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)
![GitHub REST API](https://img.shields.io/badge/GitHub%20REST%20API-2026--03--10-181717?logo=github)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**GraphApp** è un'applicazione desktop che analizza un repository GitHub e mostra, sotto forma di grafo,
**come collaborano e comunicano i suoi sviluppatori** in un intervallo di tempo scelto dall'utente.

Basta inserire owner e nome del repository: l'app scarica commit, issue, pull request, review e commenti
tramite le API REST di GitHub, li salva in una cache locale e costruisce il grafo con
[NetworkX](https://networkx.org/), visualizzandolo con [Matplotlib](https://matplotlib.org/) dentro
un'interfaccia [PyQt6](https://www.riverbankcomputing.com/software/pyqt/).

> Progetto realizzato per il corso di **Ingegneria del Software** (A.A. 2023).

![GraphApp – grafo composito, tema scuro](docs/screenshots/composito-scuro.png)

---

## Indice

- [Funzionalità](#funzionalità)
- [I tre tipi di grafo](#i-tre-tipi-di-grafo)
- [Screenshot](#screenshot)
- [Installazione](#installazione)
- [Token GitHub](#token-github)
- [Avvio e utilizzo](#avvio-e-utilizzo)
- [Architettura](#architettura)
- [Cache e rate limit](#cache-e-rate-limit)
- [Test e qualità del codice](#test-e-qualità-del-codice)
- [Limiti noti](#limiti-noti)
- [Licenza](#licenza)

---

## Funzionalità

- **Tre tipi di grafo**: collaborazioni, comunicazioni e composito (dettagli [qui sotto](#i-tre-tipi-di-grafo)).
- **Filtro temporale**: si sceglie l'intervallo (data di inizio e di fine) da analizzare; cambiandolo,
  il grafo si ricalcola sui dati già scaricati, senza nuove chiamate alle API.
- **Grafo leggibile**: layout force-directed, dimensione dei nodi proporzionale al numero di collegamenti,
  spessore degli archi proporzionale al peso, etichette con il numero di interazioni.
- **Strumenti di esplorazione**: zoom, spostamento e salvataggio del grafo come immagine (PNG, SVG, PDF)
  dalla toolbar integrata.
- **Interfaccia moderna**: sidebar con i parametri, statistiche del grafo (sviluppatori e collegamenti),
  **tema scuro e chiaro** commutabili al volo.
- **Token inserito nell'app**: il personal access token si incolla direttamente nell'interfaccia, si
  verifica con un click e resta solo in memoria; la quota di richieste API residua è sempre visibile.
- **Cache locale**: i dati di ogni repository vengono scaricati una sola volta e salvati su disco.
- **Gestione del rate limit**: in caso di limite raggiunto (primario o secondario) l'app attende il reset
  e riprova automaticamente.

## I tre tipi di grafo

| Tipo | Grafo | Nodi | Un arco A — B significa… | Peso dell'arco |
|------|-------|------|--------------------------|----------------|
| **Collaborazioni** | non diretto | sviluppatori che hanno fatto commit | A e B hanno modificato lo stesso file nell'intervallo | numero di file modificati da entrambi |
| **Comunicazioni** | diretto (A → B) | utenti attivi in issue e pull request | A ha risposto (commento, review, commit in PR) dopo un intervento di B nella stessa discussione | numero di risposte |
| **Composito** | non diretto | unione dei due | sovrapposizione dei due grafi, colorata per tipo | — |

Nel grafo composito i colori degli archi indicano il tipo di relazione:

- 🔵 **blu**: solo collaborazione
- 🔴 **rosso**: solo comunicazione
- 🟣 **viola**: la coppia di sviluppatori sia collabora sia comunica

## Screenshot

| Collaborazioni | Comunicazioni |
|:-:|:-:|
| ![Grafo delle collaborazioni](docs/screenshots/collaborazioni-scuro.png) | ![Grafo delle comunicazioni](docs/screenshots/comunicazioni-scuro.png) |

| Composito, tema scuro | Composito, tema chiaro |
|:-:|:-:|
| ![Grafo composito, tema scuro](docs/screenshots/composito-scuro.png) | ![Grafo composito, tema chiaro](docs/screenshots/composito-chiaro.png) |

## Installazione

Requisiti: **Python 3.9 o superiore** e una connessione a Internet per scaricare i dati da GitHub.

```bash
git clone https://github.com/gPiscopo3/Ingegneria-del-Software-2023.git
cd Ingegneria-del-Software-2023

# ambiente virtuale (consigliato)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Token GitHub

Le API di GitHub si possono usare anche senza autenticazione, ma con un limite di **60 richieste
all'ora**, insufficiente per quasi tutti i repository. Con un token personale il limite sale a
**5.000 richieste all'ora**.

1. Vai su **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens**
   ([link diretto](https://github.com/settings/personal-access-tokens/new)).
2. Crea un token con accesso in **sola lettura**: per analizzare repository pubblici non serve
   nessun permesso aggiuntivo (per quelli privati concedi la lettura di *Contents*, *Issues* e *Pull requests*).
3. Copia il token e incollalo nel campo **Autenticazione GitHub** dell'app, poi premi **Verifica**.

Il badge sotto il campo mostra l'esito:

| Badge | Significato |
|-------|-------------|
| ✓ Autenticato · 4.987/5.000 richieste | token valido, con la quota residua |
| ✕ Token non valido o scaduto | GitHub ha rifiutato il token: l'app non procede |
| Nessun token · limite di 60 richieste/ora | si usano le API senza autenticazione (l'app chiede conferma) |

> 🔒 **Il token non viene mai salvato su disco**: resta in memoria solo finché l'app è aperta.
> Se non lo verifichi a mano, l'app lo verifica automaticamente prima di generare il grafo.

## Avvio e utilizzo

Dalla cartella principale del progetto:

```bash
python -m src.main
```

1. Inserisci **owner** e **nome** del repository (es. `apache` / `commons-io`).
2. Incolla il tuo **token** e premi **Verifica**.
3. Scegli il **tipo di grafo**: sotto il menu compare una breve descrizione.
4. Imposta l'**intervallo temporale** (dal / al).
5. Premi **Genera grafo**.

Il primo caricamento di un repository può richiedere tempo (vengono scaricati tutti i commit di tutti i
branch, le issue e le pull request con i relativi commenti); i caricamenti successivi usano la cache
e sono immediati. Cambiando solo l'intervallo, o tornando a un tipo di grafo già generato, non viene
fatta alcuna nuova richiesta.
La barra di stato in basso mostra l'intervallo analizzato e la quota API residua.

Nella toolbar sopra il grafo trovi: ripristino della vista, zoom, spostamento e salvataggio come
immagine. Il pulsante in fondo alla sidebar passa dal tema scuro a quello chiaro.

## Architettura

```
src/
├── main.py                  # finestra principale (MainViewer): sidebar, area del grafo, gestione eventi
├── gui/
│   ├── graph.py             # costruzione dei grafi NetworkX e GraphWidget (Matplotlib in Qt)
│   ├── style.py             # temi scuro/chiaro: foglio di stile QSS, QPalette e colori dei grafi
│   └── widget_calendar.py   # selettore dell'intervallo temporale
├── logic/
│   ├── APICalls.py          # chiamate alle API REST di GitHub, paginazione, rate limit
│   ├── DataManagement.py    # costruzione di utenti/file dai dati grezzi e cache su disco (.pkl)
│   └── Filters.py           # filtro di collaborazioni e comunicazioni per intervallo di date
└── model/
    ├── User.py              # utente e relative comunicazioni (data → destinatari)
    └── File.py              # file e relative modifiche (data → autore)
test/                        # test pytest di logic e model
```

Flusso dei dati alla pressione di **Genera grafo**:

```mermaid
flowchart LR
    GUI["main.py<br/>MainViewer"] --> G["gui/graph.py<br/>create_graph…"]
    G --> DM["logic/DataManagement.py"]
    DM -->|cache presente| PKL[("src/*.pkl")]
    DM -->|cache assente| API["logic/APICalls.py"]
    API --> GH(("GitHub<br/>REST API"))
    DM --> F["logic/Filters.py<br/>filtro per date"]
    F --> NX["NetworkX<br/>Graph / DiGraph"]
    NX --> W["GraphWidget<br/>Matplotlib + Qt"]
```

### Endpoint GitHub utilizzati

Tutte le richieste usano la versione **`2026-03-10`** delle API REST (header `X-GitHub-Api-Version`).

| Dato | Endpoint |
|------|----------|
| Branch | `GET /repos/{owner}/{repo}/branches` |
| Commit di ogni branch | `GET /repos/{owner}/{repo}/commits?sha={sha}&since={data}` |
| File modificati da un commit | `GET /repos/{owner}/{repo}/commits/{sha}` |
| Issue | `GET /repos/{owner}/{repo}/issues?state=all&since={data}` |
| Commenti di una issue / PR | `GET /repos/{owner}/{repo}/issues/{n}/comments` |
| Pull request | `GET /repos/{owner}/{repo}/pulls?state=all` |
| Review, commenti di review, commit di una PR | `GET /repos/{owner}/{repo}/pulls/{n}/reviews`, `/comments`, `/commits` |
| Verifica del token e quota | `GET /rate_limit` (non consuma quota) |

## Cache e rate limit

- **Cache su disco**: al primo download i dati vengono salvati in `src/{owner}_{repo}.pkl`
  (comunicazioni) e `src/{owner}_{repo}_collabs.pkl` (collaborazioni). Le richieste successive per lo
  stesso repository leggono questi file. Per forzare un nuovo download basta **cancellarli**.
  Nel repository sono inclusi i dati di esempio di `apache/commons-io` e `tensorflow/tensorflow`,
  utilizzabili anche senza token.
- **Cache in memoria**: finché l'app resta aperta, cambiare intervallo o tipo di grafo sullo stesso
  repository non rilegge nemmeno la cache su disco.
- **Rate limit**: se GitHub risponde `403`/`429` per limite raggiunto, l'app attende il tempo indicato
  (`Retry-After` per i limiti secondari, `X-RateLimit-Reset` per quello orario) e riprova. Durante
  l'attesa l'interfaccia resta occupata: per i repository grandi usa sempre un token.

## Test e qualità del codice

```bash
# i test che chiamano le API leggono il token dalla variabile d'ambiente GH_TOKEN
# (solo per i test: l'applicazione non la usa)
export GH_TOKEN=<il tuo token>          # PowerShell: $env:GH_TOKEN="<il tuo token>"

pytest test                              # esecuzione dei test
pytest --cov=src --cov-report html test  # con report di copertura in htmlcov/

pylint --disable line-too-long --disable wrong-import-order --disable no-name-in-module ./src
```

La pipeline di **GitHub Actions** ([`python-app.yml`](.github/workflows/python-app.yml)) esegue test,
copertura e analisi statica con pylint a ogni push.

## Limiti noti

- Il caricamento iniziale di repository molto grandi richiede molte chiamate API (una per ogni commit),
  quindi molto tempo; l'interfaccia resta bloccata fino al termine.
- La cache non si aggiorna da sola: i dati successivi al primo download non vengono scaricati finché
  non si cancellano i file `.pkl`.
- I dati vengono scaricati a partire dal 15/11/2023, data minima selezionabile nel calendario.
- Gli account GitHub eliminati (autore `null`) vengono ignorati.

## Licenza

Distribuito con licenza **Apache 2.0**: vedi il file [LICENSE](LICENSE).

Autori: vedi i [contributor del progetto](https://github.com/gPiscopo3/Ingegneria-del-Software-2023/graphs/contributors).
