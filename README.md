# Vietnamese Crimes NLP

An application for named entity recognition and event extraction from Vietnamese news. The
frontend is built with React/Vite, and the backend provides a FastAPI service powered by PhoBERT
models.

## Requirements

- Node.js and npm
- Python 3.10 or later
- Git to clone the repository

The commands below use PowerShell on Windows. Open a terminal in the repository root before
following the steps.

## 1. Install frontend dependencies

```powershell
cd client
npm install
```

## 2. Create a Python virtual environment and install backend dependencies

Open a new PowerShell terminal in the repository root, then run:

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-ner.txt
```

The `python -m venv .venv` command creates an isolated Python environment in `server/.venv`.
`Activate.ps1` activates it. When activation succeeds, the terminal prompt begins with `(.venv)`.
If PowerShell blocks the activation script, run the following command in that same terminal, then
activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If you close the terminal or open a new one, activate the environment again from the `server`
directory with `.\.venv\Scripts\Activate.ps1`.

## 3. Run the web frontend

Open a new terminal in the repository root:

```powershell
cd client
npm run dev
```

Vite prints the local URL in the terminal, usually
[http://localhost:5173](http://localhost:5173). Keep this terminal open while using the application.

## 4. Download and install the models

The models are available in the
[GitHub Models release](https://github.com/GiaHuy910/NLP---Vietnamese-Crimes-/releases/tag/models-v1).
Download `ner_model.zip` and `event_models.zip` from **Assets**, then extract both archives into
the repository's `server/models/` directory.

After extraction, check that the directory structure looks like this:

```text
server/
  models/
    config.json
    model.safetensors
    tokenizer_config.json
    vocab.txt
    bpe.codes
    added_tokens.json
    event_trigger/
      config.json
      model.safetensors
      ...
    event_argument/
      config.json
      model.safetensors
      ...
```

The NER model files must be directly inside `server/models/`, not nested in another `ner_model/`
directory. The `event_trigger/` and `event_argument/` directories must also be directly inside
`server/models/`. If your extraction tool creates an extra top-level folder, move its contents into
the locations shown above. The backend requires the NER model to perform entity recognition.

## 5. Run the backend API

Open a new terminal in the repository root, activate the Python virtual environment, and start the
server:

```powershell
cd server
.\.venv\Scripts\Activate.ps1
uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep this terminal open. The backend runs at [http://127.0.0.1:8000](http://127.0.0.1:8000), and
the interactive API documentation is available at
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The frontend running on port `5173`
connects to the backend on port `8000`.

## Daily startup

After installing dependencies and downloading the models once, open two terminals:

1. Frontend terminal: run `cd client`, then `npm run dev`.
2. Backend terminal: run `cd server`, activate `.venv`, then run the `uvicorn` command from step 5.

If the API reports that a model cannot be found, check the `server/models/` directory structure in
step 4. If the frontend cannot connect to the backend, make sure the backend is running on port
`8000`.
