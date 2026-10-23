# Guide for Windows: finish and run the project

Follow the steps in order. Every step says how to check that it worked. All commands are for **Windows 10 or 11** and are typed in **PowerShell** (search "PowerShell" in the Start menu). Where the Command Prompt differs, it says so.

## 0. What is verified, and what is left for you

Verified in development (on Linux, offline, with a built-in stand-in language model and a basic text embedder): the whole pipeline (ingestion, RAG, GraphRAG, figure search, the LangGraph agent with routing and the web-fallback branch, citations, streaming), the backend API, the web interface in a real browser, the MCP server (tool list and one call) and the offline evaluation metrics. 18 automated tests pass.

I could not test these, so you must check them in the steps below: a real language model (Gemini), real embeddings (sentence-transformers), CLIP, Tavily web search, the DeepEval run with a real judge model, Docker, the Claude Desktop connection, and everything above **on Windows itself**.

## 1. Requirements

- Windows 10 or 11.
- **Python 3.12** from python.org (see step 2). Avoid the very newest Python version: PyTorch sometimes has no ready-made package for it.
- A Google AI Studio API key (free).
- Optional: a Tavily key for web search.
- About 2 GB of free disk space for PyTorch and the model downloads.
- An internet connection for the first run (models are downloaded once).

## 2. Install Python

1. Go to **python.org/downloads** and download **Python 3.12** for Windows.
2. Run the installer and **tick "Add python.exe to PATH"** on the first screen. This is the step people miss.
3. Click "Install Now".
4. **Close PowerShell and open a new one.** An old window does not see the new install.

Check:

```powershell
python --version
```

It must print `Python 3.12.x`. If it opens the Microsoft Store instead, either try `py --version` (and use `py` instead of `python` below), or turn off the shortcut: Settings, Apps, Advanced app settings, App execution aliases, switch off the two "python" entries.

## 3. Get the project and install the packages

Unzip `hybrid-rag-assistant.zip` somewhere simple, for example `C:\Projects\hybrid-rag-assistant`. Avoid very long folder names and folders synced by OneDrive.

```powershell
cd C:\Projects\hybrid-rag-assistant
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-ml.txt
```

Notes:

- After `activate`, your prompt starts with `(.venv)`. If PowerShell says "running scripts is disabled", run this once, then activate again:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

- In the **Command Prompt** (not PowerShell) the activate command is `.venv\Scripts\activate.bat`.
- `requirements-ml.txt` is large (PyTorch, about 2 GB) and takes several minutes. It gives real semantic search and CLIP. Without it the app still runs, but with weak search and caption-based image search.
- Every time you open a new PowerShell window, `cd` into the project folder and run the `activate` line again.

Check:

```powershell
python -m pytest -q
```

It should print `18 passed`. The tests use the offline stand-in model, so they need no key. If a test fails on Windows, send me the error text.

## 4. Configure the `.env` file

The app reads a file named exactly `.env` in the project folder (next to `requirements.txt`). Create it from the template:

```powershell
copy .env.example .env
```

Open it in Notepad or VS Code (`notepad .env`). Replace everything with the settings below. Paste your Google AI Studio key after `OPENAI_API_KEY=` with no spaces and no quotes.

```dotenv
# ---- Language model: Google Gemini through its OpenAI-compatible endpoint ----
LLM_PROVIDER=openai
LLM_MODEL=gemini-3.1-flash-lite
OPENAI_API_KEY=
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
ANTHROPIC_API_KEY=

# ---- Embeddings and CLIP (run locally) ----
EMBEDDING_PROVIDER=auto
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CLIP_MODE=auto
CLIP_MODEL=clip-ViT-B-32

# ---- Web search (off for now) ----
WEB_PROVIDER=none
TAVILY_API_KEY=
WEB_MAX_RESULTS=4
WEB_BLOCKED_DOMAINS=

# ---- Pipeline tuning ----
CHUNK_SIZE=800
CHUNK_OVERLAP=100
TOP_K=5
GRAPH_EXTRACTION=false
GRAPH_HOPS=1
MAX_VERIFY_LOOPS=1

# ---- Server ----
DATA_DIR=./data
MAX_UPLOAD_MB=50
USE_MOCK_CORE=false
```

Windows pitfalls with this file:

- **Notepad saves `.env.txt`.** In the Save dialog set "Save as type" to "All files". Using the `copy` command above avoids the problem. In File Explorer, turn on View, Show, File name extensions to check the real name.
- The file is hidden in some views because its name starts with a dot. VS Code shows it in the file list.
- Write `KEY=value` with no spaces around `=`.
- `.env` is only read when the server starts. Restart the server after every change.
- I have not tested the Gemini base URL or the model name `gemini-3.1-flash-lite` with this project. If you get a 404 error, check the model id in AI Studio and search Google's docs for "Gemini OpenAI compatibility" to confirm the URL.
- Free Gemini requests may be used by Google to improve its products, so do not upload confidential documents.

`GRAPH_EXTRACTION=false` is deliberate: building the knowledge graph makes one model call per passage and can hit the free rate limit. First get chat working. Then set it to `true` and upload your documents (see step 6).

Important: the search indexes depend on the embedding model and the CLIP mode. If you change `EMBEDDING_MODEL`, `EMBEDDING_PROVIDER` or `CLIP_MODE` later, stop the server, delete the index folder, and upload your documents again:

```powershell
Remove-Item -Recurse -Force data\index
```

## 5. Run

With the virtual environment active, in the project folder:

```powershell
python -m uvicorn backend.main:app --port 8000
```

(`run.sh` is for Linux and Mac; on Windows use the line above.) Wait until you see "Application startup complete". The first start takes 20 to 60 seconds, and longer the very first time because models are downloaded. Windows may show a firewall prompt: allow access for private networks. Open **http://localhost:8000** in your browser. Stop the server with Ctrl+C.

Tip: to avoid retyping, create a file `run.bat` in the project folder containing these lines, and double-click it:

```bat
@echo off
call .venv\Scripts\activate.bat
python -m uvicorn backend.main:app --port 8000
pause
```

Check, in the browser:

1. **Settings** (left menu): language model shows `openai`, embeddings show `sentence-transformers`, image search shows `clip`. If you see `fake`, `hash` or `caption`, then the `.env` was not read (wrong name, wrong folder, no restart) or `requirements-ml.txt` is not installed.
2. **Library**: drop the three PDFs from `contracts\sample_data` (or run `python scripts\seed_sample.py` in a second PowerShell window with the environment active). Status goes Queued, Indexing, Ready. Restart the server: they are still listed.
3. **Home**: ask "What dataset was BERT pretrained on?" Tokens stream in, citation numbers are clickable, a source chip opens the PDF at the right page, and "How I answered" shows the route.
4. Ask "Show me the diagram of the CLIP shared embedding space": a figure appears under the answer.
5. Ask something outside the documents with **Web search on** (needs step 7): the route shows `web_search` and the sources carry a "Web" badge with a link.
6. With Web search off, the same question gets an answer saying it could not find it in your documents.
7. **Knowledge graph** (needs `GRAPH_EXTRACTION=true`): entities and relations are drawn. Delete a document in the Library: it disappears from the graph and from search.

## 6. Use your real documents

1. Collect 30 to 100 PDFs on one topic (papers, course notes, manuals). Text-based PDFs only: scanned PDFs are reported as failed because OCR is not included.
2. Once chat works, set `GRAPH_EXTRACTION=true` in `.env` and restart. Graph building makes one model call per passage, so a 20-page paper costs roughly 30 to 60 calls. If you see rate-limit errors (429), wait a minute and re-upload that document, or upload fewer documents at a time. The document card shows the error, and the document stays usable for plain search.
3. Upload them in the Library.

## 7. Web search (optional, hybrid fallback)

1. Create a Tavily account at tavily.com and copy your key. Check its current free limits.
2. In `.env` set `WEB_PROVIDER=tavily` and `TAVILY_API_KEY=your-key`. No key? Run `pip install ddgs` and set `WEB_PROVIDER=ddgs`.
3. Restart the server. In the left menu, the Web search switch can now be turned on.

Web search only runs when the local documents do not contain a good answer, so test it with a question clearly outside your documents.

## 8. Evaluation (requirement A9)

1. Put your PDFs in a folder, for example `my_pdfs`. The file name without `.pdf` is the document id.
2. Write at least 40 questions in a new file such as `eval\my_dataset.json`, in the same format as `eval\dataset.json`: `id`, `category` (`factual`, `multi_hop`, `image`, `out_of_corpus`), `question`, `expected` (the reference answer) and `docs` (ids of the documents that hold the answer; an empty list for out-of-corpus questions). Cover all four categories so the comparison is meaningful.
3. Quick offline check with the sample documents (no key needed):

   ```powershell
   python -m eval.run_eval --ingest
   ```

4. Real run with the DeepEval metrics (faithfulness, answer relevancy, contextual precision and recall, hallucination, plus the custom citation-correctness metric):

   ```powershell
   python -m eval.run_eval --ingest --corpus my_pdfs --dataset eval\my_dataset.json --deepeval
   ```

   The judge is your configured model (Gemini). Each question needs many judge calls, so on the free tier use `--limit 10` first, and check your daily limit in AI Studio before a full run. Results go to `eval\results\latest.json` and `latest.csv` and appear in the web app under **Evaluation**. Until you run it, that page shows clearly marked placeholder numbers.

5. The three configurations compared are RAG only, GraphRAG only and the hybrid agent. Put the table and your discussion in the report.

## 9. MCP server (requirement A8)

Test it first from PowerShell: `python -m core.mcp_server` (it waits for a client; stop with Ctrl+C). It exposes `list_documents`, `search_documents`, `search_graph`, `search_images`, `web_search` and `ask_agent`.

To connect **Claude Desktop**, open its config file, which is normally at `%APPDATA%\Claude\claude_desktop_config.json` (paste that into the File Explorer address bar). In Claude Desktop you can also open Settings, Developer, Edit Config. Add the block below. Use forward slashes in the paths (Windows accepts them in JSON) and your real folder:

```json
{
  "mcpServers": {
    "lumen": {
      "command": "C:/Projects/hybrid-rag-assistant/.venv/Scripts/python.exe",
      "args": ["-m", "core.mcp_server"],
      "env": {
        "PYTHONPATH": "C:/Projects/hybrid-rag-assistant",
        "DATA_DIR": "C:/Projects/hybrid-rag-assistant/data"
      }
    }
  }
}
```

The `DATA_DIR` line matters: the relative value `./data` in `.env` depends on the folder a program is started from, and Claude Desktop starts it elsewhere. Restart Claude Desktop completely after saving. The server loads the indexes when it starts, so restart Claude Desktop after uploading new documents. I have not tested this connection on Windows. If the tools do not appear, check the logs from Claude Desktop's Developer settings, and as a second test use the MCP Inspector (`npx @modelcontextprotocol/inspector`, needs Node.js).

## 10. Docker (optional)

Install Docker Desktop (with the WSL 2 backend), start it, then in the project folder:

```powershell
docker compose up --build
```

The app is then at http://localhost:8000 and its data lives in the `lumen-data` volume. For a small image without real embeddings and CLIP, set `WITH_ML: "0"` in `docker-compose.yml`. I have not run the Docker build.

## 11. Work split for two people

- **Person A (AI core):** `core\` and `eval\`. Contracts are in `contracts\schemas.py`. Test with `python -m pytest tests/test_core.py`. Main tuning work: the prompts in `core\agent.py` and `core\graph.py`, and the thresholds in `.env`.
- **Person B (platform):** `backend\` and `frontend\`. Develop with no AI at all:

  ```powershell
  $env:USE_MOCK_CORE="true"
  python -m uvicorn backend.main:app --port 8000
  ```

  Test with `python -m pytest tests/test_backend.py`. (The `$env:` setting lasts only for that PowerShell window.)
- **Integration point:** `make_core()` in `backend\main.py`. With `USE_MOCK_CORE` false, the two sides are connected.
- Share the project with Git, one branch per module, and never commit `.env` (it is already in `.gitignore`).

## 12. Status of every requirement

| Req | Where | Status |
|---|---|---|
| A1 ingestion | `core\ingestion.py` | Done, tested. No OCR. |
| A2 RAG | `core\rag.py`, `core\vectorstore.py` | Done, tested. Simple stored vectors, fine up to about 100,000 passages. Reranking (could) not done. |
| A3 GraphRAG | `core\graph.py` | Done, tested offline. Quality depends on your model. |
| A4 CLIP | `core\images.py` | Text-to-image done (CLIP, with caption fallback). Image-to-image is in the code but not in the UI. Auto-captioning (could) not done. |
| A5 web search | `core\websearch.py` | Done (Tavily and ddgs). Needs your key to test live. |
| A6 LangGraph agent | `core\agent.py` | Done, tested. |
| A7 citations | `core\citations.py` | Done, tested. |
| A8 MCP | `core\mcp_server.py` | Done, tools verified in-process. Test with your client. |
| A9 DeepEval | `eval\run_eval.py` | Offline metrics tested. The DeepEval part is wired and its imports checked, but never run against a live judge: run step 8.4 and report any error to me. |
| B1 to B4 backend | `backend\` | Done, tested. |
| B5 to B7 interface | `frontend\` | Done, checked in a headless browser. |
| B8 figures | `frontend\` | Thumbnails, enlarge and captions done. Uploading an image as a query (could) not done. |
| B9 route panel | `frontend\` | Done ("How I answered"), plus a knowledge-graph page. |
| B10 dashboard | `frontend\` | Done, reads `eval\results\latest.json`. |
| B11 deployment | `Dockerfile`, `docker-compose.yml`, `scripts\seed_sample.py` | Written, Docker build not run. |

## 13. Known limits, so nothing surprises you in the demo

- No login: anyone who can reach the port sees all documents. Do not expose the app to the internet.
- One shared library for everyone, and one document is indexed at a time.
- The answer checker runs after the answer has streamed. If it finds a problem it replaces the text with a corrected answer.
- The router, grader and checker prompts are generic. If routing looks wrong on your documents, adjust the prompts in `core\agent.py`.
- No automatic retry on rate-limit errors yet: on a free tier some graph-building calls can fail.
- The folder is named `backend` and not `platform` as in the specification, because `platform` clashes with a Python standard module.

## 14. Troubleshooting on Windows

- **"Python was not found; run without arguments to install from the Microsoft Store"**: Python is not installed or not on PATH. Redo step 2, tick "Add python.exe to PATH", open a new window.
- **"running scripts is disabled on this system"**: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then activate again.
- **`pip install` fails while installing torch**: you probably have a very new Python. Install Python 3.12, delete the `.venv` folder, and redo step 3.
- **"Microsoft Visual C++ 14.0 is required"**: install the "Build Tools for Visual Studio" with the C++ workload, then retry. This is rare with Python 3.12.
- **Port 8000 already in use**: start on another port (`--port 8001`, then open http://localhost:8001), or find the program with `netstat -ano | findstr :8000`.
- **"Cannot reach the server" in the browser**: the server is still loading. Wait for "Application startup complete" and refresh.
- **Settings shows `fake`**: the `.env` was not read. Check the file name is exactly `.env`, that it is in the project folder, that you started the server from that folder, and that you restarted it.
- **Settings shows `hash` or `caption`**: `requirements-ml.txt` is not installed in the active environment (check the prompt starts with `(.venv)`), or the model download failed (check your connection).
- **Error 401 or 403 from the model**: the key is wrong or has spaces. **404**: wrong model id or base URL. **429**: free rate limit, wait a minute.
- **Answers always say "could not find"**: check the documents show Ready, then add `MIN_LOCAL_SCORE=0.15` to `.env` and restart.
- **A document shows Failed with "looks scanned"**: the PDF has no text layer; run OCR on it first.
- **Graph is empty**: `GRAPH_EXTRACTION` is false, or the model calls failed (the document card shows the error).
- **Antivirus slows or blocks the first start**: allow Python for this folder, or wait; loading the models is heavy.
