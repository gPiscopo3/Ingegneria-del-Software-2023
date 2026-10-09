# Progetto

Python 3.11, interfaccia PyQt6, test con pytest, lint con pylint.
Il codice sta in `src/` (`gui`, `logic`, `model`, `locales`).
I test stanno in `test/src/` e rispecchiano la struttura di `src/`: i test di `src/logic/` vanno in `test/src/logic/`.

# Comandi

Usa sempre l'interprete dell'ambiente virtuale, senza attivarlo:

- Test singolo: `.venv/Scripts/python -m pytest test/src/logic/<file>.py::<nome_test>`
- Test di un modulo: `.venv/Scripts/python -m pytest test/src/logic`
- Suite completa: `.venv/Scripts/python -m pytest`
- Copertura: `.venv/Scripts/python -m pytest --cov=src --cov-branch --cov-report=term-missing`
- Lint: `.venv/Scripts/python -m pylint src`

# Regole

- Dopo una modifica lancia i test del modulo toccato. La suite completa solo prima del commit.
- IMPORTANT: non modificare né cancellare test esistenti per farli passare. Se un test sembra sbagliato, fermati e spiegami perché.
- Nei test nuovi i valori attesi derivano dai requisiti, non dall'output attuale del codice. Ogni test deve avere asserzioni che falliscono se il comportamento cambia.
- I test non devono dipendere da hardware reale (porte seriali, USB) né dalla rete: usa mock o i dati in `data/examples/`.
- Non installare né aggiornare dipendenze senza chiedere.
- Un commit per modifica logica, su un branch dedicato. Non fare push.

# Ambiente

- In ambienti senza display (CI, WSL) i test della GUI richiedono la variabile `QT_QPA_PLATFORM=offscreen`.
- Non leggere `.venv/`, `__pycache__/` e `.pytest_cache/`.

# Lingua

Rispondi in italiano. Codice, commenti e messaggi di commit nella lingua già usata nel progetto.
