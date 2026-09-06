# Phantom

**Phantom — Privacy-preserving AI middleware.** LangGraph orchestration,
load-aware multi-provider LLM routing (Gemini/Groq/OpenRouter), ChromaDB
cross-session memory with PII protection.

Phantom is a privacy-first AI middleware system: every query is screened for
prompt injection, PII is redacted before anything leaves the machine, risky
actions require human approval (HITL) before they run, and conversation
memory persists across sessions in a local ChromaDB store — all orchestrated
as a LangGraph state machine with automatic failover across cloud LLM
providers.

Academic project — B.M.S. College of Engineering, Dept. of CSE. See
[CLAUDE.md](CLAUDE.md) for the full architecture spec, module ownership, and
research references.

---

## Architecture

```
User input
  → input_guard_node          prompt-injection screen (regex, fails closed to END)
  → parallel_preprocess_node  PII redaction + ChromaDB memory retrieval + intent
                               classification, run concurrently
  → llm_call_node             PhantomRouter — weighted multi-provider selection,
                               speed lane, exponential backoff, automatic failover
  → tool_node / hitl_check_node   file-system tools; high-risk calls pause here
                                    for human approval before executing
  → pii_restore_node          de-anonymise response, async write-back to ChromaDB
  → END
```

State is checkpointed to SQLite (`phantom_memory/checkpoints.db`) after every
node, so a conversation thread survives a process restart. See
`phantom_graph.py` for the compiled graph.

## Components

| Component | File | Purpose |
|---|---|---|
| LangGraph pipeline | `phantom_graph.py` | Node wiring, checkpointing, memory write-back |
| LLM router | `llm_router.py` | `PhantomRouter` — weighted provider selection, backoff, usage logging |
| Prompt injection guard | `utils/input_guard.py` | Pattern-based screen, runs before any LLM call |
| Context trimming | `utils/context_trimmer.py` | Trims message history to a provider's context limit |
| ChromaDB memory | `memory/chroma_manager.py`, `memory/retrieval_engine.py` | Session + persistent collections, cosine similarity + recency decay |
| PII engine | `sentinel/pii_engine.py`, `sentinel/session_pii_map.py` | Tiered redaction (regex → Presidio/spaCy → LLM fallback) with reversible placeholders |
| HITL risk scoring | `hitl/risk_scorer_3tier.py` | Gates high-risk file operations behind explicit approval |
| File tools | `tools/file_tools.py` | Search, move, copy, delete, scan, HTML/report generation |
| Chat UI | `phantom_streamlit.py` | Streamlit front end — glassmorphism theme, provider status, HITL approval panel |
| REST/WebSocket API | `api/server.py` | FastAPI — `/query`, `/resume`, `/stream`, `/status` |
| Desktop UI | `phantom_ui.py`, `ui/` | PyQt6 window + tray daemon variant |

## LLM Providers

`PhantomRouter` (`llm_router.py`) load-balances across cloud providers by
weight and remaining per-minute token budget, with a speed lane that prefers
Groq for small/streaming calls, a 15% reserve buffer per provider, and
exponential backoff + quarantine on repeated failures. Local Ollama is the
last-resort fallback.

| Provider | Role |
|---|---|
| Gemini | Highest-weight default for ordinary traffic |
| Groq | Speed lane — small/streaming calls |
| OpenRouter, NVIDIA, xAI | Secondary cloud capacity |
| Ollama | Local fallback when no cloud slot qualifies |

Configure API keys in `.env` (see `.env.example`). Call `router.status_all()`
or `GET /status` for live per-provider health and usage.

---

## Quick Start

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Configure API keys
Copy `.env.example` to `.env` and fill in the keys you have (not all
providers are required — the router falls back automatically):
```
cp .env.example .env
```

### 3. (Optional) Run Ollama for local fallback
```
ollama serve
ollama pull llama3:latest
```

### 4. Run the chat UI
```
streamlit run phantom_streamlit.py
```

### 5. Or run the API server
```
uvicorn api.server:app --host 127.0.0.1 --port 8747
```

### 6. Or run headless (CLI)
```
python phantom_cli.py
```

### 7. Run tests
```
pytest tests/ -v
```

---

## Project Structure

```
phantom/
├── phantom_graph.py       # LangGraph pipeline: nodes, edges, checkpointing
├── llm_router.py          # PhantomRouter — multi-provider routing + failover
├── phantom_node.py        # Router-as-LangGraph-node wrapper
├── phantom_streamlit.py   # Streamlit chat UI
├── phantom_ui.py          # PyQt6 desktop UI entry point
├── phantom_cli.py         # Headless CLI entry point
├── api/
│   └── server.py          # FastAPI REST + WebSocket endpoints
├── sentinel/               # Intent classification + tiered PII redaction
├── memory/                 # ChromaDB manager, retrieval, reranking, eviction
├── hitl/                   # Human-in-the-loop risk scoring + approval state
├── tools/                  # File-system tools exposed to the LLM
├── utils/                  # Config, injection guard, context trimming, logging
├── ui/                     # PyQt6 window, tray daemon, hotkeys
├── hud/                    # Voice HUD components
├── tests/                  # pytest suite
└── data/, phantom_memory/  # Local runtime data (gitignored — never committed)
```

---

## Privacy Design

- **PII-zero cloud boundary** — a tiered cascade (regex → Presidio/spaCy NER
  → LLM semantic check) redacts PII before any cloud API call; a
  session-local map allows reversible restoration in the response only.
- **Human-supervised actions** — file operations above a risk threshold pause
  the graph for explicit approval before executing.
- **Local-first memory** — ChromaDB runs as a local persistent store; nothing
  is sent to a third party for storage.
- **Prompt injection defense** — an input guard screens every query before
  it reaches preprocessing or any LLM call.

## Tech Stack

- **Orchestration**: LangGraph (StateGraph, SQLite checkpointing)
- **LLM routing**: LangChain provider clients (Gemini, Groq, OpenRouter,
  NVIDIA, xAI, Ollama) behind a custom weighted router
- **Memory**: ChromaDB + `sentence-transformers/all-MiniLM-L6-v2` embeddings
- **PII detection**: Regex + Presidio + spaCy, with an LLM fallback tier
- **UI**: Streamlit (chat) and PyQt6 (desktop HUD)
- **API**: FastAPI + WebSocket streaming
