# NyayaSearch AI

AI-assisted legal research and case-law retrieval for Indian Supreme Court judgments.

NyayaSearch AI helps a researcher describe a legal issue in ordinary language, retrieve the most relevant judgment passages from a local Supreme Court dataset, and optionally generate an evidence-grounded explanation. It is an academic research system, not a substitute for advice from a qualified legal professional.

## Problem statement

Keyword search is a poor fit for legal research. The same issue may be expressed as “stigmatic termination”, “probationer dismissal”, or “departmental inquiry”. A student or researcher needs a system that searches by meaning, shows the supporting passages, and makes it obvious which judgments the answer rests on.

## Proposed solution

The application embeds the provided, already-chunked Supreme Court dataset with a local Sentence Transformer model, stores vectors in persistent ChromaDB, retrieves diverse cases for a query, and (when a Gemini key is present) writes a grounded analysis that may use only those passages.

## Key features

- Semantic search over the local judgment corpus
- Evidence-grounded AI analysis with explicit sources
- Case record view with judgment chunks and similar cases
- Side-by-side case comparison
- Filters for year, date range, citation, and court
- Bookmarks and search history (guest session or signed-in account)
- Gemini fallback: retrieval still works if the LLM is unavailable
- Guest mode if authentication is not configured

## System architecture

User → Streamlit workspace → FastAPI → local embeddings → ChromaDB → diversified case hits → optional Gemini → UI with cases, passages, and sources.

Application data (users, history, bookmarks, feedback) is stored in SQLite by default, or in Supabase if credentials are provided. The vector corpus is never stored in Supabase.

## Dataset

The knowledge source is the project `dataset/` directory.

| Item | Actual content |
| --- | --- |
| Format | JSON files, one judgment per file, year folders `1950`–`2025` |
| Volume | About 26,688 judgment files |
| Record shape | Array of chunks |
| Fields | `chunk_id`, `case_name`, `court`, `judges`, `date`, `citation`, `case_number`, `ipc`, `articles`, `metadata`, `text` |
| Court | Supreme Court of India (string variants normalised) |
| Date / year | Often `Unknown` / `null` in the file; year is taken from the folder and, where possible, from the filename (`_on_6_March_2000`) |

The original dataset is not rewritten. Missing metadata is shown as “Information not available in the dataset.”

## Technology stack

Python, FastAPI, Streamlit, Sentence Transformers (`all-MiniLM-L6-v2` by default), ChromaDB, Google Gemini (optional), SQLite or Supabase, Pydantic, pytest.

## Installation

From the project root (Windows PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The first install downloads PyTorch and the embedding model weights. Allow time on a typical laptop.

## Environment setup

```powershell
copy .env.example .env
```

| Variable | Required | Purpose |
| --- | --- | --- |
| `EMBEDDING_MODEL` | No | Local Sentence Transformer id |
| `CHROMA_PERSIST_DIRECTORY` | No | Persistent vector store path |
| `DATASET_DIR` | No | Defaults to `dataset` |
| `GEMINI_API_KEY` | No | Enables AI analysis |
| `GEMINI_MODEL` | No | Defaults to `gemini-2.0-flash` |
| `SUPABASE_URL` / `SUPABASE_KEY` | No | Optional hosted auth and app data |
| `NYAYA_API_URL` | No | Frontend API base, default `http://127.0.0.1:8000` |

Semantic search does not require Gemini or Supabase.

## Dataset indexing

Indexing is a separate step. The API does not rebuild embeddings on startup.

Full corpus (hours on CPU, resumable):

```powershell
python scripts/index_dataset.py
```

Recommended first demonstration index (covers the service-law example in 2000 and recent years):

```powershell
python scripts/index_dataset.py --years 2000,2010,2020,2021,2022,2023,2024,2025
```

Quicker smoke index (``--max-files`` is split evenly across the listed years):

```powershell
python scripts/index_dataset.py --years 2000,2025 --max-files 80
```

For the departmental-inquiry demonstration question, prefer indexing all of year 2000 (the relevant precedents sit late in alphabetical order):

```powershell
python scripts/index_dataset.py --years 2000
python scripts/index_dataset.py --years 2024,2025 --max-files 100
```

Re-run the same command to resume. Already indexed files are skipped unless `--rebuild` is passed. Progress is written to `data/index_state.json`.

## Running the backend

```powershell
python -m backend.main
```

Health check: `http://127.0.0.1:8000/health`

## Running the frontend

In a second terminal, with the virtual environment active:

```powershell
streamlit run frontend/app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Dataset and index status |
| GET | `/api/meta` | Years and collection stats |
| POST | `/api/search` | Semantic case retrieval |
| POST | `/api/ask` | Retrieval plus grounded analysis |
| GET | `/api/cases/{case_id}` | Judgment record |
| GET | `/api/cases/{case_id}/similar` | Similar judgments |
| POST | `/api/cases/compare` | Two-case comparison |
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Sign in |
| GET | `/api/history` | Saved searches |
| GET/POST/DELETE | `/api/bookmarks` | Bookmarks |
| POST | `/api/feedback` | Optional feedback |

## Testing

```powershell
pytest -q
```

Tests cover dataset loading, validation, Chroma insert/query, diversification, RAG fallback, API routes, and local account storage. They do not invent retrieval-accuracy percentages.

Sample evaluation questions live in `tests/evaluation_questions.py`. After indexing, try them from the Search page.

## Screenshots

Capture the Home, Search results, Case, and Compare pages during a local demonstration and add them here if required by the report.

## Limitations

- Some source records lack citation, date, or judge names.
- A full 26k-file index is large; CPU indexing takes substantial time.
- Embedding quality is limited by the MiniLM model chosen for laptop use.
- Gemini may refuse or omit analysis when the key, quota, or network is unavailable.
- High Court and tribunal law are outside this dataset.
- The product is not legal advice.

## Future scope

- Cross-encoder reranking on a GPU machine
- Citation graph / cited-in links if a later dataset provides them
- Full-corpus incremental index on a lab server
- Export of research memos with source passages
- Role-based institutional accounts on Supabase

## Local demonstration

1. Create the virtual environment and install requirements.
2. Copy `.env.example` to `.env`. Add `GEMINI_API_KEY` only if you have a free-tier key.
3. Run `python scripts/index_dataset.py --years 2000,2025 --max-files 80` for a first demo, or a larger year set for a stronger search.
4. Start the API, then Streamlit.
5. Ask: “Can a government employee be dismissed without a departmental inquiry?”
6. Open a result, bookmark it, and compare two case IDs.

## Free-tier deployment notes

The supported path is local demonstration. If a hosted demo is needed later:

- Keep Chroma and embeddings on a machine with disk (the vector store is local).
- Optionally point auth/history to a free Supabase project using `database/supabase/schema.sql`.
- Streamlit Community Cloud can host the UI if the API and Chroma instance are reachable; this is optional and not required for evaluation.

## Legal disclaimer

This system provides AI-assisted legal information retrieval for educational and research purposes. It is not a substitute for advice from a qualified legal professional.
