# Changelog

🇬🇧 [English](CHANGELOG.md) · 🇮🇹 **Italiano**

## 1.0.0

Prima release pubblica. Rispetto alla versione presentata per il corso di Ingegneria del Software (dicembre 2023):

### Interfaccia
- Nuova interfaccia con sidebar, card dei parametri, statistiche del grafo e tema scuro e chiaro (pulsante ☀/☾ in
  alto accanto al titolo).
- Token GitHub inserito nell'app e mai salvato su disco: verifica con un click, quota residua reale letta dagli
  header di GitHub e orario di rinnovo.
- Card **Git** che indica se Git è installato, con link per scaricarlo e pulsante «Ricontrolla».
- Download in background con avanzamento nella barra di stato e pulsante **Annulla download**.
- Interfaccia multilingua (italiano e inglese): lingua scelta da quella di Windows e selettore per cambiarla al
  volo; ogni lingua è un file JSON in `src/locales`, per aggiungerne una non serve codice.

### Dati
- Si scarica solo l'intervallo scelto («Dal»–«Al», di default gli ultimi 3 mesi), senza più la data minima fissa;
  allargando l'intervallo si riscarica solo quando serve.
- Salvataggio e caricamento espliciti dei dati in file `.graphapp` (al posto della cache automatica), letti in
  modo sicuro; dopo il caricamento il calendario si limita al periodo disponibile nel file.
- Richieste parallele su 8 thread, con gestione dei limiti di GitHub (primario e secondario) e nuovi tentativi
  sugli errori di rete.
- Consumo di quota ridotto: commit letti da un clone git locale parziale (es. `apache/commons-io`, 3 mesi:
  1 richiesta invece di 107), commenti di issue e PR scaricati in blocco.

### Grafi ed esportazione
- Grafi grandi fluidi: disegno alleggerito oltre 150 nodi, nome dei nodi al passaggio del mouse, zoom e
  spostamento in ~0,07 s invece di ~2,4 s.
- **Esporta…**: grafo e dati grezzi per R, MATLAB e Python (CSV di nodi e archi, GraphML, `.mat`, modifiche e
  interazioni con data) e immagine del grafo in PNG (300 dpi), SVG o PDF; con più formati, un unico `.zip`. Il tipo di
  grafo nei nomi dei file e nei metadati è sempre in inglese (`collaboration`, `communication`, `composite`).

### Distribuzione
- Eseguibile per Windows (nessuna installazione di Python), allegato alla release.
- Requisiti: Python 3.10 o superiore per l'esecuzione da sorgente; dipendenze ridotte a quelle effettivamente
  usate e compatibili con le versioni recenti di Python e delle librerie.
