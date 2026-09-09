# CLAUDE.md â€” Project PHANTOM
## Master Context File for Claude Code

> Place this file at the **root of the PHANTOM repository** as `CLAUDE.md`.
> Claude Code reads this automatically on every session. Keep it updated as the project evolves.

---

## 0. HOW TO USE THIS FILE

This file gives Claude Code complete context about Project PHANTOM so it can assist with implementation, debugging, and architecture decisions without needing repeated explanations. Every section is intentionally detailed. Do not summarise or shorten it.

---

## 1. PROJECT IDENTITY

| Field | Value |
|---|---|
| Project Name | PHANTOM â€” Hybrid Edge Cloud Learning and Intelligent Exchange |
| Type | AI Operating System (AIOS) â€” Major Project, Phase 1 complete |
| Institution | B.M.S. College of Engineering (BMSCE), Dept. of CSE, Bengaluru |
| Academic Year | 2025â€“2026 |
| Guide | Sindhoor N, Assistant Professor, Dept. of CSE |
| Phase | Phase 1 complete (architecture + research). Phase 2 = full implementation |

### Team

| Name | USN | Module Ownership |
|---|---|---|
| Tanmay Vasishta | 1WA23CS012 | Sentinel Node, PII Redaction Engine, Memory-Augmented Re-prompting, LangChain Task Orchestrator, HITL Coordination, Overall Architecture |
| Varshitha B | 1WA23CS035 | Voice HUD (PyQt6), Input Layer, ASR pipeline |
| Vedika S S | 1WA23CS037 | Python OS Middleware, Workflow Engine, Rollback |
| Yukta C | 1WA23CS055 | ChromaDB Memory Manager, RAG retrieval, Session/Persistent memory |

---

## 2. SYSTEM OVERVIEW

PHANTOM is a **privacy-first hybrid local-cloud AI Operating System** that runs on consumer hardware (minimum 16 GB RAM laptop). It accepts natural language voice/text commands, sanitises all PII locally, routes tasks intelligently between a local LLM and cloud, and requires explicit human approval before irreversible OS actions.

### Core Design Principles
1. **Local-first**: Every query is processed locally before any cloud routing decision.
2. **PII-zero cloud boundary**: Nothing with PII ever leaves the machine.
3. **Human-supervised**: Any action with risk_score > 40 requires explicit user approval.
4. **Offline-capable**: Core functions work without internet (Gemini calls gracefully degrade).
5. **Consumer hardware**: Runs on 16 GB RAM, no GPU required (GPU optional for speed).

### Six Research Gaps PHANTOM Fills
1. No local PII guardrail before cloud routing in any existing system
2. No mandatory HITL checkpoint before OS-level actions
3. Hardware exclusion â€” most capable AI requires expensive cloud subscriptions
4. No offline-first persistent contextual memory
5. Unfair privacy trade-off (intelligence vs sovereignty)
6. Dangerous AI autonomy in multi-step agents (AutoGPT-style)

### SDG Alignment
- **SDG 9** â€” Industry, Innovation and Infrastructure (decentralised AI on edge)
- **SDG 16** â€” Peace, Justice and Strong Institutions (digital privacy, ethical AI)

---

## 3. FIVE-LAYER PIPELINE ARCHITECTURE

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  LAYER 1: Input & Intent Recognition                                     â”‚
â”‚  [Voice HUD â€” PyQt6 async] â†’ Whisper ASR â†’ Text Normalisation           â”‚
â”‚  Owner: Varshitha                                                         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  LAYER 2: Privacy & Context                                               â”‚
â”‚  [Sentinel Node â€” LLaMA 3.2 3B] â†’ [PII Redaction Engine]               â”‚
â”‚  â†’ [Memory-Augmented Re-prompting â€” ChromaDB RAG]                        â”‚
â”‚  Owner: Tanmay (Sentinel + PII + Re-prompting), Yukta (ChromaDB)         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  LAYER 3: Dynamic Workload Router                                         â”‚
â”‚  [LangChain Task Orchestrator] â†’ routing decision + risk scoring         â”‚
â”‚  Owner: Tanmay                                                            â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  LAYER 4: Dual-Path Execution                                             â”‚
â”‚  LOCAL â†’ [Python OS Middleware] (Vedika)                                  â”‚
â”‚  CLOUD  â†’ [Gemini 1.5 Flash Oracle] (Tanmay coordinates)                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚  LAYER 5: Safety & Visualisation                                          â”‚
â”‚  [HITL Dashboard â€” PyQt6] â†’ Approve / Reject / Modify                   â”‚
â”‚  â†’ [PII Restorer] â†’ [Async Memory Write-back]                            â”‚
â”‚  Owner: Tanmay                                                            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## 4. TECH STACK

### Runtime & Language
- **Python 3.10+** â€” all AI pipelines, middleware, orchestration
- **Node.js** â€” not used in production (only build tooling)

### AI / ML
| Component | Library / Model | Purpose |
|---|---|---|
| Local LLM | LLaMA 3.2 3B (4-bit quantized) via Ollama | Sentinel Node intent classification |
| Cloud LLM | Google Gemini 1.5 Flash API | Complex reasoning on sanitised queries |
| ASR | OpenAI Whisper (tiny/base, local) | Voice-to-text transcription |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | ChromaDB vector embeddings (384-dim) |
| Re-ranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Re-rank ChromaDB top-5 results |
| NER | spaCy `en_core_web_lg` + Microsoft Presidio | PII entity detection |
| Orchestration | LangChain (ReAct agent pattern) | Task routing and tool management |
| Vector DB | ChromaDB | Offline persistent memory store |

### UI
- **PyQt6** â€” Voice HUD, HITL Dashboard (QThread for async)

### Python Packages (key)
```
ollama
langchain langchain-community langchain-google-genai
chromadb
sentence-transformers
presidio-analyzer presidio-anonymizer
spacy  # + python -m spacy download en_core_web_lg
google-generativeai
openai-whisper
pyqt6
SpeechRecognition
pyspellchecker
torch  # for cross-encoder
transformers
```

### Environment
- OS: Ubuntu 22.04 LTS / Windows 11 / macOS
- Local dev machine: `tanmay` user, `TanmayN13` machine, WSL2 Ubuntu
- Ollama installed and running as background service

---

## 5. RECOMMENDED PROJECT STRUCTURE

```
phantom/
â”œâ”€â”€ CLAUDE.md                          â† this file
â”œâ”€â”€ README.md
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ .env                               â† GEMINI_API_KEY (never commit)
â”œâ”€â”€ .gitignore
â”‚
â”œâ”€â”€ main.py                            â† entry point, starts all services
â”‚
â”œâ”€â”€ sentinel/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ sentinel_node.py               â† Tanmay: intent classification via Ollama
â”‚   â”œâ”€â”€ pii_engine.py                  â† Tanmay: tiered PII redaction
â”‚   â”œâ”€â”€ session_pii_map.py             â† Tanmay: SESSION_PII_MAP + PII Restorer
â”‚   â””â”€â”€ intent_types.py                â† Enum: FILE_OP, SYSTEM_CMD, etc.
â”‚
â”œâ”€â”€ memory/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ chroma_manager.py              â† Yukta: ChromaDB collections management
â”‚   â”œâ”€â”€ retrieval_engine.py            â† Yukta: cosine + recency decay scoring
â”‚   â”œâ”€â”€ reranker.py                    â† Tanmay: cross-encoder re-ranking
â”‚   â”œâ”€â”€ reprompting.py                 â† Tanmay: prompt construction + token budget
â”‚   â””â”€â”€ eviction_policy.py             â† Yukta: LRU + relevance hybrid eviction
â”‚
â”œâ”€â”€ orchestrator/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ task_orchestrator.py           â† Tanmay: LangChain ReAct routing engine
â”‚   â”œâ”€â”€ risk_scorer.py                 â† Tanmay: risk_score formula
â”‚   â”œâ”€â”€ routing_rules.py               â† Tanmay: decision tree logic
â”‚   â””â”€â”€ gemini_oracle.py               â† Tanmay: Gemini API wrapper + PII assertion
â”‚
â”œâ”€â”€ middleware/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ os_middleware.py               â† Vedika: sandboxed command execution
â”‚   â”œâ”€â”€ command_mapper.py              â† Vedika: intent â†’ OS command translation
â”‚   â”œâ”€â”€ risk_classifier.py             â† Vedika: command-level risk scoring
â”‚   â”œâ”€â”€ rollback_stack.py              â† Vedika: undo mechanism
â”‚   â””â”€â”€ blocked_commands.py            â† Vedika: static + dynamic blocklist
â”‚
â”œâ”€â”€ hitl/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ hitl_controller.py             â† Tanmay: approval state machine
â”‚   â””â”€â”€ approval_states.py             â† Tanmay: PENDING, APPROVED, REJECTED, MODIFIED
â”‚
â”œâ”€â”€ hud/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ voice_hud.py                   â† Varshitha: main PyQt6 HUD window
â”‚   â”œâ”€â”€ asr_pipeline.py                â† Varshitha: Whisper + normalisation
â”‚   â”œâ”€â”€ state_machine.py               â† Varshitha: IDLEâ†’LISTENINGâ†’PROCESSINGâ†’...
â”‚   â””â”€â”€ hitl_widget.py                 â† Varshitha: approval dialog widget
â”‚
â”œâ”€â”€ utils/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ logger.py
â”‚   â””â”€â”€ config.py                      â† loads .env, model paths, thresholds
â”‚
â””â”€â”€ tests/
    â”œâ”€â”€ test_pii_engine.py
    â”œâ”€â”€ test_sentinel.py
    â”œâ”€â”€ test_routing.py
    â””â”€â”€ test_memory.py
```

---

## 6. MODULE SPECIFICATIONS

### 6.1 Sentinel Node (`sentinel/sentinel_node.py`) â€” TANMAY

**Purpose**: Two-pass intent classification + initial PII detection using local LLaMA 3.2 3B.

**Intent types** (define as Enum in `intent_types.py`):
```python
class IntentType(Enum):
    FILE_OP = "file_op"           # file/directory operations
    SYSTEM_CMD = "system_cmd"     # terminal/system commands
    CALENDAR_OP = "calendar_op"   # schedule/reminder
    MEMORY_LOOKUP = "memory_lookup"  # retrieve past context
    WEB_QUERY = "web_query"       # search / browse
    GENERAL_QA = "general_qa"     # knowledge questions
    UNKNOWN = "unknown"           # fallback
```

**Pass 1 â€” Intent Classification**:
```python
def classify_intent(query: str) -> dict:
    """
    Returns:
    {
        "intent": IntentType,
        "confidence": float,   # 0.0â€“1.0
        "sub_intent": str,     # e.g. "delete", "create", "rename"
        "entities": list[str], # detected nouns/objects
        "raw": str             # Llama's JSON output
    }
    """
    SYSTEM_PROMPT = """You are an intent classifier for a local AI assistant.
    Classify the user query into EXACTLY ONE intent from:
    [FILE_OP, SYSTEM_CMD, CALENDAR_OP, MEMORY_LOOKUP, WEB_QUERY, GENERAL_QA, UNKNOWN]
    
    Also identify:
    - sub_intent: the specific action (delete, create, rename, search, etc.)
    - confidence: your confidence as a float 0.0-1.0
    - entities: list of objects/targets mentioned
    
    Respond ONLY with valid JSON. No preamble. No markdown.
    Format: {"intent": "...", "sub_intent": "...", "confidence": 0.0, "entities": [...]}
    """
    # Call Ollama with llama3.2:3b model
    # Parse JSON response
    # If confidence < 0.65: trigger clarification loop
```

**Confidence gate** (ORIGINAL DESIGN):
- If `confidence < 0.65`: do NOT route. Return clarification request to HUD.
- HUD shows: `"Did you mean: [paraphrased interpretation]? [Yes / No / Rephrase]"`
- Wait for user confirmation before any further processing.

**Pass 2 â€” Basic PII Pre-screen**:
- Run spaCy NER on query to find PERSON, ORG, GPE entities.
- Flag high-confidence entities for the PII Engine.
- Pass intent context to PII Engine (knowing intent=PAYMENT_OP makes "4111" more likely a card number).

**Key interface**:
```python
class SentinelNode:
    def __init__(self, model_name="llama3.2:3b", confidence_threshold=0.65):
        ...
    
    def process(self, query: str) -> SentinelResult:
        """Main entry point. Returns SentinelResult or ClarificationRequest."""
    
    def request_clarification(self, query: str, interpretation: str) -> ClarificationRequest:
        """Called when confidence < threshold."""
```

---

### 6.2 PII Redaction Engine (`sentinel/pii_engine.py`) â€” TANMAY

**Purpose**: Tiered PII detection and redaction. Three-tier cascade. Output must be zero-PII guaranteed.

**Architecture** (ORIGINAL DESIGN â€” Tiered Cascade):

```
Tier 1: Regex (FAST â€” always runs first)
    â†“ (if missed entities detected by confidence scoring)
Tier 2: Presidio + spaCy NER (ACCURATE)
    â†“ (if Tier 2 confidence still low on some spans)
Tier 3: LLaMA 3.2 3B semantic check (SAFETY NET â€” expensive, rare)
    â†“
Merge all results â†’ deduplicate â†’ apply redaction â†’ build SESSION_PII_MAP
```

**Tier 1 â€” Regex patterns for Indian context**:
```python
REGEX_PATTERNS = {
    "AADHAAR": r"\b[2-9]{1}[0-9]{3}\s[0-9]{4}\s[0-9]{4}\b",
    "PAN": r"[A-Z]{5}[0-9]{4}[A-Z]{1}",
    "PHONE_IN": r"(\+91[\-\s]?)?[0]?(91)?[789]\d{9}",
    "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "CREDIT_CARD": r"\b(?:\d{4}[\s\-]?){3}\d{4}\b",
    "IFSC": r"[A-Z]{4}0[A-Z0-9]{6}",
    "BANK_ACCOUNT": r"\b\d{9,18}\b",
}
```

**Tier 2 â€” Presidio configuration**:
```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine

# Recognisers to load:
# EmailRecognizer, PhoneRecognizer, CreditCardRecognizer,
# PersonRecognizer, LocationRecognizer, NRP recogniser (for Indian IDs)
```

**Tier 3 â€” LLaMA semantic check** (only called when Tiers 1+2 combined confidence < 0.80):
```python
SEMANTIC_PII_PROMPT = """Analyse this text for ANY personally identifiable information including:
indirect references ("my sister's address"), financial references ("the card I use for Netflix"),
medical information, or any data that could identify a specific person.

List ALL PII found as JSON:
{"pii_found": [{"text": "...", "type": "...", "start": 0, "end": 0}]}
If none found: {"pii_found": []}
"""
```

**SESSION_PII_MAP** (ORIGINAL DESIGN â€” Presidio does NOT do this):
```python
class SessionPIIMap:
    """
    Stores original PII values mapped to placeholder tokens.
    Lives in RAM only. Never persisted. Cleared on session end.
    
    {
        "[PII_PERSON_1]": "Rajesh Kumar",
        "[PII_EMAIL_1]": "rajesh@gmail.com",
        "[PII_AADHAAR_1]": "2345 6789 0123"
    }
    """
    def __init__(self):
        self._map: dict[str, str] = {}
        self._counters: dict[str, int] = {}
    
    def add(self, entity_type: str, original_value: str) -> str:
        """Returns placeholder token like [PII_PERSON_1]"""
    
    def restore(self, text: str) -> str:
        """Replaces placeholders with original values in response text."""
    
    def clear(self):
        """Called at session end."""
```

**PII Restorer** (ORIGINAL DESIGN â€” bidirectional PII control):
- After Gemini responds, run `SESSION_PII_MAP.restore(response)` before showing to user.
- Also scan response for any leaked PII patterns (Gemini hallucinated real-sounding PII).
- Alert if response contains placeholders that don't match the map (indicates a bug).

---

### 6.3 ChromaDB Memory Manager (`memory/chroma_manager.py`) â€” YUKTA

**Purpose**: Offline persistent vector memory. Two-collection design.

**Collections**:
```python
# Collection 1: Session memory (cleared each session)
SESSION_COLLECTION = "phantom_session_memory"

# Collection 2: Persistent memory (survives restarts)
PERSISTENT_COLLECTION = "phantom_persistent_memory"
```

**Schema** (metadata per document):
```python
{
    "id": "uuid4",
    "text": "interaction_summary",      # privacy-safe summary
    "embedding": [384-dim vector],
    "metadata": {
        "timestamp": "ISO8601",
        "intent_type": "FILE_OP",
        "outcome": "success|failure|rejected",
        "user_approved": True,          # only True entries go to persistent
        "retrieval_count": 0,           # incremented on every retrieval
        "days_since_stored": 0.0        # computed at retrieval time
    }
}
```

**Embedding model**:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim, ~90MB, fast on CPU
```

**Retrieval** (ORIGINAL DESIGN â€” Recency-weighted scoring):
```python
def retrieve_relevant(query: str, top_k: int = 5) -> list[dict]:
    """
    1. Embed query â†’ 384-dim vector
    2. ChromaDB cosine similarity search â†’ top-k=5
    3. Apply recency decay:
       final_score = cosine_sim * exp(-Î» * days_old)
       where Î» = 0.1
    4. Filter: final_score > 0.65
    5. Return top-3 after filtering
    """
    Î» = 0.1
    # ...
```

**Eviction policy** (ORIGINAL DESIGN â€” LRU + relevance hybrid):
```python
def evict_if_needed(collection_name: str, max_entries: int = 1000):
    """
    Eviction score = (recency_rank * 0.4) + (retrieval_frequency * 0.6)
    Remove entries with lowest score when collection > max_entries.
    """
```

**Write-back** (ORIGINAL DESIGN â€” outcome-gated):
```python
def write_back(interaction_summary: str, outcome: str, hitl_approved: bool):
    """
    - Always writes to session_memory.
    - Writes to persistent_memory ONLY IF hitl_approved=True.
    - Runs async (QThread or asyncio) so it doesn't block the UI.
    """
```

**Summarisation before storage**:
- Use LLaMA 3.2 3B to summarise the interaction into a privacy-safe 2-3 sentence summary.
- The summary must NOT contain PII (run PII check before storing).
- Prompt: `"Summarise this interaction in 2-3 sentences without including any personal details, names, or identifiers. Focus on what task was performed and what the outcome was."`

---

### 6.4 Memory-Augmented Re-prompting (`memory/reprompting.py`) â€” TANMAY

**Purpose**: Constructs enriched prompts by injecting relevant memory context.

**Cross-encoder re-ranking** (ORIGINAL DESIGN â€” added on top of ChromaDB):
```python
from sentence_transformers import CrossEncoder
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def rerank(query: str, candidates: list[str]) -> list[tuple[float, str]]:
    """
    Takes ChromaDB top-5 results, re-scores against actual query.
    Returns sorted (score, text) pairs. Keep top-2 only.
    """
    pairs = [(query, candidate) for candidate in candidates]
    scores = reranker.predict(pairs)
    return sorted(zip(scores, candidates), reverse=True)[:2]
```

**Prompt construction** (with token budget management):
```python
SYSTEM_PROMPT = """You are PHANTOM, a privacy-first AI assistant for local system management.
You have access to local OS commands and cloud reasoning.
Use the context below ONLY if directly relevant to the current task.
Never reveal PII. Never execute irreversible actions without flagging them."""

def build_enriched_prompt(
    query: str,
    intent: IntentType,
    memory_snippets: list[str],
    max_tokens: int = 2048
) -> str:
    """
    Token budget management:
    - If total prompt > max_tokens: truncate older snippets first.
    - NEVER truncate the current query.
    - If no memory relevant (all scores < 0.65): use query directly.
    """
```

---

### 6.5 LangChain Task Orchestrator (`orchestrator/task_orchestrator.py`) â€” TANMAY

**Purpose**: Routes enriched prompts to correct execution path. Calculates risk scores. Triggers HITL.

**Routing decision tree** (RULE-FIRST, LLM-fallback):
```python
def route(intent: IntentType, confidence: float, enriched_prompt: str) -> RouteDecision:
    """
    Returns RouteDecision(target, hitl_required, risk_score)
    
    LOCAL route: FILE_OP, SYSTEM_CMD, CALENDAR_OP with confidence >= 0.80
    CLOUD route:  GENERAL_QA, WEB_QUERY, UNKNOWN, or any intent with confidence < 0.80
    MEMORY route: MEMORY_LOOKUP (direct ChromaDB, no LLM needed)
    """
```

**Risk scoring formula** (ORIGINAL DESIGN):
```python
RISK_WEIGHTS = {
    "delete":   50,
    "remove":   50,
    "format":   80,
    "wipe":     80,
    "install":  40,
    "download": 35,
    "send":     30,
    "email":    30,
    "password": 70,
    "sudo":     90,
    "chmod":    60,
    "rm":       55,
}
HITL_THRESHOLD = 40

def calculate_risk_score(sub_intent: str, entities: list[str], command: str) -> int:
    """
    Sum weights for all matching keywords in sub_intent + command string.
    Also +20 if command touches paths outside ~/Documents, ~/Downloads, ~/Desktop.
    """
```

**LangChain ReAct agent tools**:
```python
from langchain.tools import Tool

tools = [
    Tool(
        name="ExecuteOSCommand",
        func=os_middleware.execute,
        description="Execute safe, approved local OS commands (file operations, directory management). Use for FILE_OP and SYSTEM_CMD intents."
    ),
    Tool(
        name="QueryGemini",
        func=gemini_oracle.query,
        description="Send a SANITISED query to Gemini for complex reasoning, knowledge questions, or tasks beyond local capability."
    ),
    Tool(
        name="SearchMemory",
        func=chroma_manager.search,
        description="Search ChromaDB for relevant past interactions. Use for MEMORY_LOOKUP intent."
    ),
]
```

---

### 6.6 Gemini Oracle (`orchestrator/gemini_oracle.py`) â€” TANMAY

**Purpose**: Cloud reasoning via Gemini 1.5 Flash. Strict PII guarantee before every API call.

**Critical pre-call assertion** (ORIGINAL DESIGN â€” must never be removed):
```python
def query(sanitised_prompt: str) -> str:
    # SAFETY GATE: Assert zero PII before any network call
    if re.search(r'\[PII_', sanitised_prompt):
        # Placeholder present is OK (it means PII was already redacted)
        pass
    
    # Check for raw PII that slipped through (should never happen)
    raw_pii_check = presidio_analyzer.analyze(sanitised_prompt, language='en')
    if raw_pii_check and any(r.score > 0.85 for r in raw_pii_check):
        raise PIILeakageError("Raw PII detected in cloud-bound payload. Aborting.")
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        sanitised_prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=1024,
            temperature=0.3,  # Low temp for factual/command tasks
        )
    )
    return response.text
```

---

### 6.7 Python OS Middleware (`middleware/os_middleware.py`) â€” VEDIKA

**Purpose**: Translates intent+entities into safe OS commands and executes them in a sandbox.

**Blocked commands** (static list, expand as needed):
```python
BLOCKED_PATTERNS = [
    "rm -rf /", "rm -rf ~", "mkfs", "dd if=/dev/zero",
    "chmod 777 /", "chown root", ":(){:|:&};:",  # fork bomb
    "curl | bash", "wget | bash", "curl | sh",
    "> /dev/sda", "shred /dev",
]
```

**Execution** (sandboxed):
```python
import subprocess, resource

def execute(command: str, timeout: int = 10) -> ExecutionResult:
    """
    1. Check against BLOCKED_PATTERNS
    2. Check risk_classifier score
    3. If safe: run with resource limits
    4. Capture stdout/stderr
    5. Record in execution_context_tracker
    6. Push to rollback_stack
    """
    def limit_resources():
        resource.setrlimit(resource.RLIMIT_CPU, (5, 10))      # 5s soft, 10s hard
        resource.setrlimit(resource.RLIMIT_AS, (512*1024*1024, 512*1024*1024))  # 512MB RAM
    
    result = subprocess.run(
        command, shell=True,
        capture_output=True, text=True,
        timeout=timeout,
        cwd=os.path.expanduser("~"),
        preexec_fn=limit_resources
    )
    return ExecutionResult(
        status="success" if result.returncode == 0 else "error",
        stdout=result.stdout[:5000],
        stderr=result.stderr,
        returncode=result.returncode,
        command=command
    )
```

**Rollback stack** (ORIGINAL DESIGN):
```python
class RollbackStack:
    """
    Tracks inverse operations for each executed command.
    Examples:
        mkdir ~/test        â†’ inverse: rmdir ~/test
        cp a.txt b.txt      â†’ inverse: rm b.txt
        mv a.txt ~/docs/    â†’ inverse: mv ~/docs/a.txt .
        
    On HITL rejection mid-sequence: pop and execute inverse operations.
    """
    def push(self, command: str, inverse: str): ...
    def pop_and_execute(self): ...
    def clear(self): ...  # called on HITL approval (no rollback needed)
```

**Intent-to-command mapping** (ORIGINAL DESIGN):
```python
def map_intent_to_command(intent: IntentType, sub_intent: str, entities: list[str]) -> str:
    """
    Examples:
    FILE_OP/delete + ["old PDFs", "Downloads"] 
        â†’ "find ~/Downloads -name '*.pdf' -mtime +30 -delete"
    
    FILE_OP/list + ["Documents"]
        â†’ "ls -lah ~/Documents"
    
    FILE_OP/create + ["notes.txt", "Desktop"]
        â†’ "touch ~/Desktop/notes.txt"
    """
```

---

### 6.8 HITL Controller (`hitl/hitl_controller.py`) â€” TANMAY

**Purpose**: Approval state machine. Manages approve/reject/modify flow with timeout logic.

**States**:
```python
class HITLState(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    TIMEOUT_REJECTED = "timeout_rejected"
    AUTO_APPROVED = "auto_approved"
```

**Timeout policy** (ORIGINAL DESIGN):
```python
def get_timeout_policy(risk_score: int) -> dict:
    if risk_score < 40:
        return {"auto_approve": True, "timeout_seconds": 10}
    elif risk_score <= 70:
        return {"auto_approve": False, "timeout_seconds": 60, "on_timeout": HITLState.TIMEOUT_REJECTED}
    else:
        return {"auto_approve": False, "timeout_seconds": None}  # no timeout, must manually confirm
```

**Dashboard display** (data passed to PyQt6 widget):
```python
@dataclass
class HITLDisplayData:
    proposed_action: str        # human-readable description
    risk_score: int             # 0-100
    risk_level: str             # "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    risk_color: str             # "#22c55e" / "#f59e0b" / "#ef4444" / "#7f1d1d"
    memory_context: list[str]   # relevant past interactions shown to user
    command_preview: str        # exact command that will run
    timeout_seconds: int | None
```

**Post-decision**:
```python
def on_decision(state: HITLState, modified_command: str | None = None):
    if state == HITLState.APPROVED:
        chroma_manager.write_back(summary, "approved", hitl_approved=True)  # async
        os_middleware.execute(command)
        rollback_stack.clear()
    elif state in (HITLState.REJECTED, HITLState.TIMEOUT_REJECTED):
        chroma_manager.write_back(summary, "rejected", hitl_approved=False)
        rollback_stack.pop_and_execute()  # undo any partial steps
        hud.show("Action cancelled.")
    elif state == HITLState.MODIFIED:
        # Re-route modified_command through task_orchestrator (full pipeline again)
        task_orchestrator.route_command(modified_command)
```

---

### 6.9 Voice HUD (`hud/voice_hud.py`) â€” VARSHITHA

**Purpose**: Asynchronous PyQt6 interface for voice + text input and system state display.

**State machine** (ORIGINAL DESIGN):
```
IDLE â†’ LISTENING (mic activated) â†’ PROCESSING (Whisper ASR running)
     â†’ AWAITING_SENTINEL (Sentinel Node processing)
     â†’ AWAITING_HITL (HITL approval dialog shown)
     â†’ DISPLAYING (response shown)
     â†’ back to IDLE
```

**Key components**:
- `AudioCapture` (QThread): non-blocking microphone capture
- `WhisperWorker` (QThread): ASR in background thread
- `TextNormaliser`: lowercase â†’ filler word removal â†’ punctuation â†’ spell check
- `PromptIntentAnnotator` (ORIGINAL DESIGN): attaches metadata packet to query
  ```python
  @dataclass
  class AnnotatedQuery:
      raw_text: str
      input_modality: str    # "voice" | "text"
      language_confidence: float
      system_state: dict     # {"open_files": [...], "last_action": "...", "cwd": "..."}
  ```
- Live status panel: shows pipeline stage, routing decision, memory context hits, pending HITL
- `HITLWidget`: embedded approve/reject/modify dialog with countdown timer

**ASR pre-processing** (ORIGINAL DESIGN â€” Indian accent robustness):
```python
def preprocess_audio(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    1. Bandpass filter: 300â€“3400 Hz (voice frequency range)
    2. Noise gate: suppress frames below -40 dB
    3. Amplitude normalisation: RMS to -20 dBFS
    Output: cleaned PCM array ready for Whisper
    """
```

---

## 7. DATA FLOW â€” COMPLETE SEQUENCE

```
1. User speaks or types
        â†“
2. [HUD] AudioCapture (QThread) â†’ WhisperWorker â†’ raw transcript
        â†“
3. [HUD] TextNormaliser â†’ PromptIntentAnnotator â†’ AnnotatedQuery
        â†“
4. [SENTINEL] Pass 1: LLaMA 3.2 3B intent classification
   â†’ if confidence < 0.65: return ClarificationRequest to HUD (GOTO 1)
   â†’ if confidence >= 0.65: continue
        â†“
5. [PII ENGINE] Tier 1 (Regex) â†’ Tier 2 (Presidio+spaCy) â†’ Tier 3 (LLaMA, if needed)
   â†’ Build SESSION_PII_MAP
   â†’ Output: sanitised_query (guaranteed zero-PII)
        â†“
6. [MEMORY] ChromaDB cosine search â†’ top-5 results
   â†’ Cross-encoder re-rank â†’ top-2 snippets
   â†’ Recency decay scoring â†’ filter < 0.65
        â†“
7. [RE-PROMPTING] Build enriched_prompt:
   system_instructions + memory_context + sanitised_query
   â†’ Token budget check (max 2048 tokens)
        â†“
8. [ORCHESTRATOR] Routing decision:
   LOCAL (FILE_OP/SYSTEM_CMD with confâ‰¥0.80) â†’ GOTO 9a
   CLOUD (GENERAL_QA/UNKNOWN or conf<0.80)   â†’ GOTO 9b
   MEMORY (MEMORY_LOOKUP)                     â†’ GOTO 9c
        â†“
   Risk score calculated â†’ if risk_score > 40: flag HITL_REQUIRED
        â†“
9a. [OS MIDDLEWARE] Blocked check â†’ resource-capped subprocess â†’ ExecutionResult
    â†’ RollbackStack.push(command, inverse)
    â†’ ExecutionContextTracker.record(diff)
9b. [GEMINI ORACLE] PII assertion â†’ API call â†’ AI response â†’ PII Restorer
9c. [CHROMADB] Direct semantic search â†’ return result
        â†“
10. if HITL_REQUIRED:
    [HITL CONTROLLER] â†’ HITLDisplayData â†’ [HUD] shows approval dialog
    â†’ User: APPROVE / REJECT / MODIFY
    â†’ if APPROVED: execute + write-back to persistent_memory (async)
    â†’ if REJECTED: rollback + write-back to session_memory only
    â†’ if MODIFIED: re-route from step 8
        â†“
11. [PII RESTORER] Substitute SESSION_PII_MAP placeholders in response
        â†“
12. [HUD] Display final response to user
        â†“
13. [MEMORY] Async write-back to ChromaDB (summarise â†’ embed â†’ store)
```

---

## 8. KEY ALGORITHMS â€” IMPLEMENTATION REFERENCE

### 8.1 Recency Decay Formula (Yukta)
```python
import math

def recency_score(cosine_sim: float, days_old: float, lambda_: float = 0.1) -> float:
    return cosine_sim * math.exp(-lambda_ * days_old)

# Threshold: only include results with recency_score > 0.65
```

### 8.2 Risk Score Formula (Tanmay)
```python
def calculate_risk_score(sub_intent: str, entities: list, command: str) -> int:
    score = 0
    text = f"{sub_intent} {command} {' '.join(entities)}".lower()
    for keyword, weight in RISK_WEIGHTS.items():
        if keyword in text:
            score += weight
    # Extra penalty for paths outside safe directories
    safe_dirs = ["~/documents", "~/downloads", "~/desktop", "~/pictures"]
    if not any(d in command.lower() for d in safe_dirs):
        score += 20
    return min(score, 100)  # cap at 100
```

### 8.3 Eviction Score Formula (Yukta)
```python
def eviction_score(recency_rank: int, retrieval_frequency: int,
                   total_entries: int) -> float:
    # Normalise ranks to 0-1
    norm_recency = 1 - (recency_rank / total_entries)
    norm_freq = retrieval_frequency / max(retrieval_frequency_all)
    return (norm_recency * 0.4) + (norm_freq * 0.6)
    # Lower score = evict first
```

### 8.4 Prompt Token Budget (Tanmay)
```python
import tiktoken

def build_prompt_within_budget(system: str, snippets: list[str], 
                                query: str, max_tokens: int = 2048) -> str:
    enc = tiktoken.get_encoding("cl100k_base")
    query_tokens = len(enc.encode(query))
    system_tokens = len(enc.encode(system))
    budget = max_tokens - query_tokens - system_tokens - 100  # 100 token buffer
    
    context_parts = []
    for snippet in snippets:  # snippets already sorted by relevance (best first)
        snippet_tokens = len(enc.encode(snippet))
        if budget - snippet_tokens > 0:
            context_parts.append(snippet)
            budget -= snippet_tokens
    
    context = "\n".join([f"[Past context]: {s}" for s in context_parts])
    return f"{system}\n\n{context}\n\nCURRENT TASK: {query}"
```

---

## 9. RESEARCH PAPERS REFERENCE

### Cluster A â€” PII Sentinel Node (Tanmay's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [1] BASE | Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing | Ding, Mallick, Wang et al. | 2024 | 2404.14618 | Routes queries between small local + large cloud model based on difficulty. 40% fewer cloud calls. |
| [2] | PRvL: Quantifying LLM Capabilities for PII Redaction | Anonymous | 2025 | 2508.05545 | No single PII method works across all entity types. Justifies tiered cascade. |
| [3] | RouteLLM: Learning to Route LLMs with Preference Data | Ong et al. | 2024 | 2406.18665 | Learned routing achieves 2x cost reduction. Validates PHANTOM routing architecture. |
| [4] | Agentic RAG: A Survey | Xiong et al. | 2025 | 2501.09136 | Autonomous agents in RAG pipelines with dynamic retrieval and write-back. |
| [5] | PBa-LLM: Privacy- and Bias-aware NLP using NER | PeÃ±a et al. | 2025 | 2507.02966 | NER-driven anonymisation at LLM input layer. Justifies Sentinel Node NER design. |

### Cluster B â€” Memory Management (Yukta's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [6] BASE | MemGPT: Towards LLMs as Operating Systems | Packer et al. | 2023 | 2310.08560 | Hierarchical memory tiers (session vs archival) inspired by OS memory management. |
| [7] | MemoryBank: Enhancing LLMs with Long-Term Memory | Zhong et al. | 2023/2024 | 2305.10250 | Ebbinghaus Forgetting Curve applied to memory decay. Justifies recency formula. |
| [8] | Conversational Agents with Time-Sensitive Long-term Memory | Alonso et al. | 2024 | 2406.00057 | Pure cosine retrieval fails on time-based queries. Motivates hybrid scoring. |
| [9] | RAG for LLMs: A Survey | Gao et al. | 2023 | 2312.10997 | Defines Naive/Advanced/Modular RAG. PHANTOM = Advanced RAG. |
| [10] | Agentic RAG: A Survey | Xiong et al. | 2025 | 2501.09136 | Bidirectional memory in agents. Justifies write-back architecture. |

### Cluster C â€” OS Middleware (Vedika's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [11] BASE | OS-Copilot: Towards Generalist Computer Agents | Wu et al. | 2024 | â€” | Generalist OS agent with sandboxed execution and HITL. PHANTOM extends with rollback. |
| [12] | Toolformer | Schick et al. | 2023 | 2302.04761 | LLMs decide when to invoke tools. Underpins intentâ†’command mapping. |
| [13] | ReAct: Synergizing Reasoning and Acting | Yao et al. | 2023 | 2210.03629 | Reason-Act-Observe loop. Models PHANTOM middleware workflow. |
| [14] | ToolLLM | Qin et al. | 2023 | 2307.16789 | Structured API selection. Informs command template selection. |
| [15] | AgentBench | Liu et al. | 2023 | 2308.03688 | Benchmarks LLM agents on real OS tasks. Identifies failure modes PHANTOM solves. |

### Cluster D â€” Voice & Interaction (Varshitha's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [16] BASE | OS-Copilot (same as [11]) | Wu et al. | 2024 | â€” | OS interaction model. How HUD connects to execution layer. |
| [17] | Toolformer (same as [12]) | Schick et al. | 2023 | 2302.04761 | Tool invocation chains triggered from HUD input. |
| [18] | ReAct (same as [13]) | Yao et al. | 2023 | 2210.03629 | HUD feedback loop: user sees reasoning + observations per action step. |
| [19] | ToolLLM (same as [14]) | Qin et al. | 2023 | 2307.16789 | HUD intents matched to validated command templates. |
| [20] | AgentBench (same as [15]) | Liu et al. | 2023 | 2308.03688 | Failure modes HUD + HITL design solves. |

---

## 10. ORIGINAL CONTRIBUTIONS â€” DO NOT CONFUSE WITH EXISTING TOOLS

These are the parts Tanmay designed from scratch. When Claude Code touches these, do not simplify them away or replace them with off-the-shelf equivalents without discussion.

| Contribution | Owner | What It Does | What Existing Tool It Extends |
|---|---|---|---|
| Two-Pass Sequential Architecture | Tanmay | Pass 1 intent enriches context for Pass 2 PII detection | Presidio + spaCy (normally run independently) |
| SESSION_PII_MAP with Reversibility | Tanmay | Stores original PII values for local restoration in responses | Presidio (throws away originals) |
| Tiered Redaction Cascade | Tanmay | Regex â†’ NER â†’ Semantic LLM fallback with confidence thresholds | Presidio + spaCy (normally one-shot) |
| Confidence-Gated Clarification Loop | Tanmay | confidence < 0.65 â†’ ask user before routing | Ollama/LLaMA (no built-in gate) |
| Risk-Scored HITL Trigger | Tanmay | Weighted formula determines if HITL fires | LangChain (provides agent loop only) |
| Cross-Encoder Re-ranking | Tanmay | Re-ranks ChromaDB top-5 before prompt injection | ChromaDB (returns cosine only) |
| PII Restorer on Response Path | Tanmay | Bidirectional PII control: sanitise in, restore out | Presidio (input only) |
| Recency-Weighted Retrieval Score | Yukta | cosine_sim Ã— exp(âˆ’Î» Ã— days_old) | ChromaDB (cosine only) |
| Interaction Summarisation Strategy | Yukta | Privacy-safe summarisation before ChromaDB storage | ChromaDB (stores raw text) |
| Session vs Persistent Memory Separation | Yukta | Two collections, outcome-gated promotion | MemGPT (single archival store) |
| LRU + Relevance Hybrid Eviction | Yukta | (recency_rank Ã— 0.4) + (retrieval_freq Ã— 0.6) | ChromaDB (no built-in eviction) |
| Outcome-Gated Promotion Policy | Yukta | Only HITL-approved interactions enter persistent memory | MemGPT/MemoryBank (store everything) |
| Dual-Mode Async Input State Machine | Varshitha | Voice + text simultaneously, non-blocking | PyQt6 (no built-in AI state machine) |
| Prompt Intent Annotator | Varshitha | Metadata packet: modality + system state + language confidence | Whisper (transcript only) |
| Indian Accent Robustness Pipeline | Varshitha | Bandpass + noise gate + normalisation before Whisper | Whisper (raw audio) |
| Dynamic Intent-to-Command Mapping | Vedika | NL intent + entities â†’ safe OS command string | subprocess (executes commands only) |
| Execution Context Tracker | Vedika | Diffs filesystem state after each command | subprocess (no tracking) |
| Partial Rollback Mechanism | Vedika | Inverse operation stack, pop on HITL rejection | No existing tool does this |
| Command Risk Classifier | Vedika | Numeric risk score per command | Static blocklists only |

---

## 11. CONFIGURATION

### `.env` file (never commit to git)
```env
GEMINI_API_KEY=your_key_here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
CHROMA_PERSIST_DIR=./data/chromadb
SESSION_COLLECTION=phantom_session_memory
PERSISTENT_COLLECTION=phantom_persistent_memory
RISK_THRESHOLD_HITL=40
CONFIDENCE_THRESHOLD_CLARIFY=0.65
MEMORY_SCORE_THRESHOLD=0.65
MEMORY_RECENCY_LAMBDA=0.1
MAX_MEMORY_ENTRIES=1000
MAX_PROMPT_TOKENS=2048
WHISPER_MODEL=tiny
LOG_LEVEL=INFO
```

### `utils/config.py`
```python
from dotenv import load_dotenv
import os

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")
RISK_THRESHOLD_HITL = int(os.getenv("RISK_THRESHOLD_HITL", "40"))
CONFIDENCE_THRESHOLD_CLARIFY = float(os.getenv("CONFIDENCE_THRESHOLD_CLARIFY", "0.65"))
MEMORY_SCORE_THRESHOLD = float(os.getenv("MEMORY_SCORE_THRESHOLD", "0.65"))
MEMORY_RECENCY_LAMBDA = float(os.getenv("MEMORY_RECENCY_LAMBDA", "0.1"))
MAX_MEMORY_ENTRIES = int(os.getenv("MAX_MEMORY_ENTRIES", "1000"))
MAX_PROMPT_TOKENS = int(os.getenv("MAX_PROMPT_TOKENS", "2048"))
```

---

## 12. HARDWARE REQUIREMENTS

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| CPU | Intel i5 8th Gen+ / AMD Ryzen 5+ / Apple M-series | Intel i7 / AMD Ryzen 7 / Apple M2 |
| Storage | 256 GB SSD | 512 GB SSD |
| GPU | None required | NVIDIA RTX (any VRAM â‰¥ 6 GB) |
| Network | 10 Mbps | 50+ Mbps |
| Microphone | Any standard | Noise-cancelling preferred |

**Laptop compatibility notes**:
- LLaMA 3.2 3B at 4-bit quantization = ~2 GB RAM. Leaves 14 GB for OS + everything else on a 16 GB machine. Fine.
- If using LLaMA 3 8B instead: ~5.5 GB RAM. Tight on 16 GB. Use only if GPU available.
- ChromaDB: ~200 MB RAM
- sentence-transformers (MiniLM): ~90 MB RAM
- spaCy + Presidio: ~300 MB RAM
- PyQt6 HUD: ~50 MB RAM
- Whisper tiny: ~150 MB RAM
- **Total peak RAM (without GPU)**: ~3.5 GB Python + 2 GB model = ~5.5 GB. Comfortable on 16 GB.
- **Ollama startup time** on CPU: 10â€“15 seconds cold load. Start as background service at boot.

---

## 13. PHASE 2 IMPLEMENTATION PRIORITY ORDER

Build in this order (each step unlocks the next):

1. **`utils/config.py`** â€” environment setup, all thresholds loaded
2. **`sentinel/pii_engine.py`** â€” most testable, most critical, most exam-ready
3. **`sentinel/session_pii_map.py`** â€” tiny but foundational
4. **`sentinel/sentinel_node.py`** â€” depends on pii_engine
5. **`memory/chroma_manager.py`** â€” Yukta's core, needed by re-prompting
6. **`memory/retrieval_engine.py`** + **`memory/reranker.py`** â€” Yukta + Tanmay
7. **`memory/reprompting.py`** â€” Tanmay, depends on reranker
8. **`orchestrator/risk_scorer.py`** â€” Tanmay, standalone
9. **`orchestrator/routing_rules.py`** â€” Tanmay, standalone
10. **`middleware/blocked_commands.py`** + **`middleware/risk_classifier.py`** â€” Vedika
11. **`middleware/rollback_stack.py`** â€” Vedika
12. **`middleware/command_mapper.py`** + **`middleware/os_middleware.py`** â€” Vedika
13. **`orchestrator/gemini_oracle.py`** â€” Tanmay, needs pii_engine
14. **`orchestrator/task_orchestrator.py`** â€” Tanmay, needs everything above
15. **`hitl/hitl_controller.py`** â€” Tanmay, needs orchestrator
16. **`hud/asr_pipeline.py`** â€” Varshitha
17. **`hud/state_machine.py`** â€” Varshitha
18. **`hud/voice_hud.py`** â€” Varshitha, needs ASR + state machine
19. **`hud/hitl_widget.py`** â€” Varshitha, needs hitl_controller
20. **`main.py`** â€” wires everything together

---

## 14. TESTING PRIORITIES

### PII Engine Tests (`tests/test_pii_engine.py`)
Test with at least 50 Indian-context sentences containing:
- Aadhaar numbers (valid format: `2345 6789 0123`)
- PAN numbers (`ABCDE1234F`)
- Indian mobile numbers (`+91 98765 43210`, `9876543210`)
- Email addresses
- Names in various positions ("My name is Rajesh", "Send it to Kumar")
- Indirect PII ("my sister's address", "the card I use for Swiggy")
- Mixed English/Hindi transliteration ("mera naam Arjun hai")

### Sentinel Node Tests (`tests/test_sentinel.py`)
- 30 diverse queries across all 7 intent types
- Edge cases: ambiguous queries, multi-intent queries, very short queries (1-2 words)
- Confidence threshold gate: ensure queries below 0.65 trigger clarification

### Routing Tests (`tests/test_routing.py`)
- Verify every intent type routes to correct target
- Verify risk_score threshold triggers HITL at exactly > 40
- Test all RISK_WEIGHTS keywords

### Memory Tests (`tests/test_memory.py`)
- Write 10 interactions â†’ retrieve with known query â†’ verify top-3 returned
- Test recency decay: old interactions should score lower
- Test eviction: add 1001 entries â†’ verify lowest-score evicted

---

## 15. KNOWN CONSTRAINTS & DECISIONS

- **Do not use LLaMA 3 8B for the Sentinel Node** â€” too heavy for 16 GB RAM alongside other services. Use LLaMA 3.2 3B. Reserve 8B for future enhancement only if GPU is available.
- **Do not use `WidthType.PERCENTAGE`** in any docx output â€” breaks in Google Docs.
- **Gemini model**: use `gemini-1.5-flash`, NOT `gemini-1.5-pro`. Flash is fast enough for this use case and stays within free tier for development.
- **Whisper model**: use `tiny` for development, `base` for final demo if latency allows. Do not use `small` or larger â€” too slow on CPU.
- **ChromaDB**: use local persistent client (`chromadb.PersistentClient`), not the HTTP client. No server needed.
- **PyQt6 not PyQt5**: the report specifies PyQt6. If a library only supports PyQt5, use a compatibility shim.
- **No threading.Thread**: use QThread for all background work so PyQt6 event loop stays clean.
- **All regex patterns use raw strings**: `r"\b..."` not `"\b..."`.
- **SESSION_PII_MAP is cleared at the start of every new query**, not at session end, to prevent stale mappings from bleeding across unrelated queries.

---

## 16. PLAGIARISM ASSESSMENT

Closest existing project: **Open Interpreter** (~35-40% conceptual similarity). Key differences that make PHANTOM distinct:
- Open Interpreter has NO dedicated PII redaction layer
- Open Interpreter has NO hybrid local-cloud routing (local only)
- Open Interpreter has NO persistent offline memory (ChromaDB)
- Open Interpreter's "confirmation" is a simple y/n â€” not PHANTOM's risk-scored HITL with timeout policy
- Open Interpreter has NO SESSION_PII_MAP reversibility

PHANTOM's unique combination: PII-first + hybrid routing + offline memory + HITL risk scoring = no direct clone exists.

---

## 17. QUICK COMMANDS

```bash
# Install all Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# Start Ollama (keep running in background)
ollama serve &
ollama pull llama3.2:3b

# Run PHANTOM
python main.py

# Run tests
pytest tests/ -v

# Test PII engine specifically
python -m pytest tests/test_pii_engine.py -v

# Test Sentinel Node
python -m pytest tests/test_sentinel.py -v

# Check ChromaDB contents
python -c "
import chromadb
client = chromadb.PersistentClient('./data/chromadb')
col = client.get_collection('phantom_persistent_memory')
print(f'Persistent memory entries: {col.count()}')
"
```

---

## 18. NOTES FOR CLAUDE CODE

- When implementing any module, **check section 6** for the exact interface specification before writing code.
- When touching PII-related code, **never simplify or remove the three-tier cascade**. It is a core contribution.
- When touching memory code, **preserve the session vs persistent separation**. Do not merge into one collection.
- When touching the HITL controller, **preserve all three timeout tiers** (auto, 60s, no timeout).
- When touching the orchestrator, **keep the risk_score formula exactly as specified** in section 8.2.
- When generating test data for PII tests, **include Indian-specific identifiers** (Aadhaar, PAN, Indian phone formats).
- When in doubt about a design decision, **refer back to this file** before inventing a solution. The architecture is fully specified.
- The **SESSION_PII_MAP must never be logged, serialised, or written to disk** in any form.
- All **Gemini API calls must be preceded by the PII assertion check** in `gemini_oracle.py`. Never bypass it.

---

## 19. MISSING FROM INITIAL DESIGN â€” ADDITIONS (PATCHED)

### 19.1 Query Intent Cache (NEW MODULE â€” `orchestrator/intent_cache.py`) â€” TANMAY

This module was explicitly recommended during architecture review but was missing from the initial spec. It sits **between the Sentinel Node and the Task Orchestrator**.

**Purpose**: Cache recent intentâ†’route decisions. If the same intent pattern was seen recently with a known safe outcome, skip 2 full LLM calls (Sentinel re-classification + Orchestrator routing LLM). Significant latency reduction for repetitive OS tasks (e.g. "list my downloads" asked multiple times per session).

**Implementation**:
```python
import hashlib
import time
from collections import OrderedDict

class IntentCache:
    """
    Key   = (intent_type, hash(normalised_query_structure))
    Value = (route_target, risk_score, cached_at_timestamp)
    TTL   = 300 seconds (5 minutes) â€” stale after that
    Size  = max 50 entries (LRU eviction)
    """
    def __init__(self, ttl: int = 300, max_size: int = 50):
        self._cache = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size
    
    def _make_key(self, intent: str, query: str) -> str:
        # Normalise: lowercase, strip entities, keep structure
        normalised = ' '.join(sorted(query.lower().split()))
        return f"{intent}:{hashlib.md5(normalised.encode()).hexdigest()[:8]}"
    
    def get(self, intent: str, query: str) -> dict | None:
        key = self._make_key(intent, query)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['cached_at'] < self.ttl:
                self._cache.move_to_end(key)  # LRU update
                return entry
            else:
                del self._cache[key]  # expired
        return None
    
    def set(self, intent: str, query: str, route_target: str, risk_score: int):
        key = self._make_key(intent, query)
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # evict oldest
        self._cache[key] = {
            'route_target': route_target,
            'risk_score': risk_score,
            'cached_at': time.time()
        }
    
    def invalidate(self, intent: str = None):
        """Call this after any HITL rejection â€” cached decisions may be wrong."""
        if intent:
            keys_to_del = [k for k in self._cache if k.startswith(intent)]
            for k in keys_to_del:
                del self._cache[k]
        else:
            self._cache.clear()
```

**Where it plugs in** (in `task_orchestrator.py`):
```python
# Before routing:
cached = intent_cache.get(intent, query)
if cached and cached['risk_score'] <= RISK_THRESHOLD_HITL:
    # Safe cached route â€” skip LLM routing call
    return RouteDecision(cached['route_target'], hitl_required=False, from_cache=True)

# After routing decision is made:
intent_cache.set(intent, query, route_target, risk_score)
```

**Add to project structure** under `orchestrator/intent_cache.py`.

---

### 19.2 Sequence Diagram â€” Known Bugs to Fix Before Phase 2 Presentation

These are the **5 architectural errors** identified in the existing PHANTOM sequence diagram during the design audit. Fix these in the diagram before any presentation or submission.

**Bug 1 â€” Memory-Augmented Re-prompting is missing from the sequence**
- Current diagram: `SentinelNode â†’ sanitised_query â†’ TaskOrchestrator` (direct jump)
- Correct flow: `SentinelNode â†’ sanitised_query â†’ MemoryManager (retrieve) â†’ MemoryManager returns context â†’ Re-prompting Module â†’ enriched_prompt â†’ TaskOrchestrator`
- Fix: Add MemoryManager and Re-prompting as explicit lifelines. Add `Retrieve Relevant Memory` call from SentinelNode to MemoryManager, `Memory Context` return arrow, `Enriched Query` arrow from Re-prompting to TaskOrchestrator.

**Bug 2 â€” No failure path in the sequence diagram**
- Current diagram: Only shows the happy path (Gemini responds â†’ result returned)
- Required: Add an `alt` fragment for cloud failure:
  ```
  alt [Cloud Execution â€” Gemini Available]
      Send Sanitised Query â†’ GeminiService
      AI Response â† GeminiService
  [Cloud Execution â€” Gemini Unavailable]
      Fallback to local Llama
      Local AI Response
  end
  ```
- When Gemini API is down or times out (10s timeout): re-route to local Llama with a degraded prompt. Log the failure. Show user: "Cloud unavailable â€” using local model (response may be less detailed)."

**Bug 3 â€” ChromaDB write-back path is missing from the sequence**
- Current diagram: After displaying response, the sequence ends. No write-back shown.
- Required: After `Display Response`, add an async dashed arrow: `PHANTOMHUD â†’ MemoryManager: async write-back (outcome summary)`
- This is a dashed arrow (memory context flow) not a solid arrow (data flow), per the HLD legend.

**Bug 4 â€” Final Decision arrow goes to wrong component**
- Current diagram: `ApprovalManager â†’ OSMiddleware: Final Decision`
- Correct: `ApprovalManager â†’ TaskOrchestrator: Final Decision` â€” the orchestrator then decides whether to call OSMiddleware or abort.
- The orchestrator must receive the HITL decision because it may need to re-route a modified command, not just pass it to OSMiddleware.

**Bug 5 â€” Response-side PII check is missing**
- Current diagram: `GeminiService â†’ TaskOrchestrator: AI Response` goes directly back with no processing.
- Required: Add a `PIIRedactionEngine: restore + validate` step between receiving the AI Response and returning it to PHANTOMHUD.
- This is where `SESSION_PII_MAP.restore(response)` runs and the response is scanned for leaked PII.

---

### 19.3 Gemini API Fallback Strategy

**When Gemini is unavailable** (connection error, rate limit, timeout > 10s):

```python
# In gemini_oracle.py
def query(sanitised_prompt: str) -> tuple[str, bool]:
    """
    Returns: (response_text, used_cloud: bool)
    """
    try:
        response = model.generate_content(
            sanitised_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=1024,
                temperature=0.3,
            ),
            request_options={"timeout": 10}  # 10s hard timeout
        )
        return response.text, True
    
    except Exception as e:
        # Log failure
        logger.warning(f"Gemini unavailable: {e}. Falling back to local Llama.")
        
        # Fallback: use local Llama with degraded prompt
        fallback_response = ollama.generate(
            model=OLLAMA_MODEL,
            prompt=f"[OFFLINE MODE â€” Limited capability]\n\n{sanitised_prompt}",
            options={"temperature": 0.3, "num_predict": 512}
        )
        return fallback_response['response'], False
```

**HUD display when fallback occurs**:
```
"âš  Cloud unavailable â€” using local model. Response may be less detailed."
```

**Memory write-back when fallback**:
- Tag the interaction `{"cloud_used": False, "fallback": True}` in ChromaDB metadata.
- Do not promote fallback responses to persistent memory (lower quality).

---

### 19.4 Varshitha's Correct Research Papers (Cluster D â€” Voice & Interaction Systems)

The CLAUDE.md Cluster D section incorrectly lists the same papers as Cluster C. Cluster D is Varshitha's voice/HUD section and should reference the following papers (from the original document's reference list [16]â€“[20]):

| Ref | Paper | Authors | Year | arXiv / Venue | Key Insight | Relevance to PHANTOM |
|---|---|---|---|---|---|---|
| [16] BASE | OS-Copilot: Towards Generalist Computer Agents with Self-Improvement | Wu et al. | 2024 | arXiv preprint | Generalist OS agent with HUD-level interaction design, self-improving from feedback. | Base design for how the PHANTOM HUD connects to and triggers the execution layer. |
| [17] | WhisperX: Time-Accurate Speech Transcription with Forced Alignment | Bain et al. | 2023 | arXiv:2303.00747 | Extends Whisper with forced phoneme alignment for time-accurate word-level transcription. | Justifies Whisper as the ASR backbone. WhisperX's alignment technique informs PHANTOM's accent robustness pipeline. |
| [18] | Speech-to-Text Pipeline in Real Time on Edge | Vaidya et al. | 2023 | IEEE Conference | Real-time STT on edge devices with latency constraints similar to consumer laptops. | Validates feasibility of running Whisper tiny/base locally on consumer hardware within the 2-second latency target. |
| [19] | Efficient On-Device Wake Word Detection Using Tiny Transformers | Anonymous | 2024 | arXiv preprint | Ultra-lightweight transformer for always-on wake word detection without cloud dependency. | Informs the future enhancement of PHANTOM HUD with wake word activation ("Hey PHANTOM") before full ASR pipeline. |
| [20] | Attention Is All You Need | Vaswani et al. | 2017 | NeurIPS 2017 | Introduces the Transformer architecture â€” foundational to Whisper, LLaMA, and all Transformer-based models in PHANTOM. | Foundational reference for the entire model stack: Whisper ASR, LLaMA Sentinel Node, Gemini Cloud Oracle. |

**Varshitha's base paper is [16] OS-Copilot** â€” it describes the HUD-level interaction and how a generalist agent interfaces with the OS, which maps to how PHANTOM's Voice HUD triggers the full pipeline.

---

### 19.5 Corrected Complete Data Flow (Revised with All Fixes Applied)

This replaces Section 7 as the authoritative sequence. Differences from Section 7 are marked with â–¶

```
1. User speaks or types
        â†“
2. [HUD] AudioCapture (QThread) â†’ WhisperWorker â†’ raw transcript
   â–¶ Pre-processing: bandpass filter (300â€“3400 Hz) + noise gate + normalisation
        â†“
3. [HUD] TextNormaliser â†’ PromptIntentAnnotator â†’ AnnotatedQuery
   (Annotated with: modality, language confidence, system state)
        â†“
â–¶ 3b. [INTENT CACHE] Check cache for (intent, query_hash)
   â†’ Cache HIT + risk_score â‰¤ 40: skip steps 4-8, use cached route (GOTO 9)
   â†’ Cache MISS: continue to step 4
        â†“
4. [SENTINEL] Pass 1: LLaMA 3.2 3B intent classification
   â†’ if confidence < 0.65: return ClarificationRequest to HUD (GOTO 1)
   â†’ if confidence >= 0.65: continue
        â†“
5. [PII ENGINE] Tier 1 (Regex) â†’ Tier 2 (Presidio+spaCy) â†’ Tier 3 (LLaMA, if needed)
   â†’ Build SESSION_PII_MAP (RAM only, never logged or persisted)
   â†’ Output: sanitised_query (guaranteed zero-PII)
        â†“
6. [MEMORY] ChromaDB cosine search â†’ top-5 results
   â†’ Cross-encoder re-rank â†’ top-2 snippets (Tanmay's addition)
   â†’ Recency decay scoring: final_score = cosine_sim Ã— exp(âˆ’0.1 Ã— days_old)
   â†’ Filter results with score < 0.65
        â†“
7. [RE-PROMPTING] Build enriched_prompt:
   system_instructions + memory_context + sanitised_query
   â†’ Token budget check (max 2048 tokens, truncate old snippets first)
        â†“
8. [ORCHESTRATOR] Routing decision + risk score
   LOCAL (FILE_OP/SYSTEM_CMD confâ‰¥0.80)  â†’ GOTO 9a
   CLOUD (GENERAL_QA/UNKNOWN or conf<0.80) â†’ GOTO 9b
   MEMORY (MEMORY_LOOKUP)                  â†’ GOTO 9c
   â†’ risk_score calculated â†’ if > 40: HITL_REQUIRED = True
   â–¶ Store route in IntentCache
        â†“
9a. [OS MIDDLEWARE]
    â†’ Blocked pattern check â†’ Resource-capped subprocess (CPU 5s, RAM 512MB)
    â†’ ExecutionResult captured
    â†’ RollbackStack.push(command, inverse_command)
    â†’ ExecutionContextTracker.record(filesystem_diff)
    
9b. [GEMINI ORACLE]
    â†’ PII assertion (assert no raw PII in payload â€” abort if detected)
    â†’ API call with 10s timeout
    â–¶ If Gemini unavailable: fallback to local Llama, tag as degraded
    â†’ AI response received
    
9c. [CHROMADB] Direct semantic search â†’ return result (skip to step 11)
        â†“
â–¶ 10. [PII RESTORER] (MISSING FROM ORIGINAL DIAGRAM â€” NOW EXPLICIT)
    â†’ SESSION_PII_MAP.restore(response): replace placeholders with original values
    â†’ Scan response for leaked raw PII (Gemini hallucination check)
    â†’ Alert if placeholder mismatch detected
        â†“
11. if HITL_REQUIRED:
    [HITL CONTROLLER] â†’ HITLDisplayData â†’ [HUD] shows approval dialog
    Panel 1: Proposed action (human-readable)
    Panel 2: Risk level + colour (green/amber/red/dark red)
    Panel 3: Memory context (relevant past interactions)
    Panel 4: Approve / Reject / Modify buttons + countdown
    
    â†’ APPROVED:
      â–¶ [TASK ORCHESTRATOR receives Final Decision] (not OSMiddleware directly)
      â†’ Execute (if not already executed in 9a) or confirm result
      â†’ RollbackStack.clear()
      â†’ Async write-back to ChromaDB persistent_memory
    
    â†’ REJECTED:
      â†’ RollbackStack.pop_and_execute() (undo partial steps)
      â†’ Async write-back to ChromaDB session_memory only (not persistent)
      â†’ IntentCache.invalidate(intent) (rejected routes should not be cached)
      â†’ HUD: "Action cancelled."
    
    â†’ MODIFIED:
      â†’ Re-route modified_command from step 8 (full pipeline again)
        â†“
12. [HUD] Display final response to user
        â†“
â–¶ 13. [MEMORY] Async write-back (QThread â€” non-blocking)
    â†’ Summarise interaction using LLaMA (privacy-safe, no PII)
    â†’ Run PII check on summary before storage
    â†’ Store in session_memory always
    â†’ Store in persistent_memory ONLY IF hitl_approved=True AND not degraded (fallback)
    â†’ Increment retrieval_count for any memories that were used
```

---

### 19.6 Complete `requirements.txt`

```txt
# Core Python version: 3.10+

# LLM & AI
ollama>=0.1.9
langchain>=0.2.0
langchain-community>=0.2.0
langchain-google-genai>=1.0.0
google-generativeai>=0.7.0

# Embeddings & Re-ranking
sentence-transformers>=2.7.0
torch>=2.0.0
transformers>=4.40.0

# PII Detection
presidio-analyzer>=2.2.0
presidio-anonymizer>=2.2.0
spacy>=3.7.0
# After install: python -m spacy download en_core_web_lg

# Vector Database
chromadb>=0.5.0

# ASR & Audio
openai-whisper>=20231117
SpeechRecognition>=3.10.0
pyaudio>=0.2.14
numpy>=1.26.0
scipy>=1.13.0    # for bandpass filter

# UI
PyQt6>=6.7.0

# Orchestration
tiktoken>=0.7.0   # token counting for prompt budget

# Utilities
python-dotenv>=1.0.0
pyspellchecker>=0.8.1
uuid>=1.30
dataclasses-json>=0.6.4

# Testing
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

**Post-install commands**:
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg
ollama pull llama3.2:3b
```

---

### 19.7 Updated Project Structure (Adds Missing Modules)

The following additions to Section 5's folder structure were missed:

```
orchestrator/
â”œâ”€â”€ intent_cache.py          â† NEW: Query Intent Cache (Section 19.1)
â”‚
sentinel/
â”œâ”€â”€ pii_restorer.py          â† NEW: Explicit PII Restorer module (Section 19.2 Bug 5)
â”‚
utils/
â”œâ”€â”€ requirements.txt         â† at project root (Section 19.6)
â”œâ”€â”€ fallback_handler.py      â† NEW: Gemini fallback logic (Section 19.3)
```

**`sentinel/pii_restorer.py`** (split out from `session_pii_map.py` for clarity):
```python
class PIIRestorer:
    """
    Runs on every response before it reaches the HUD.
    1. Substitutes SESSION_PII_MAP placeholders back into response text.
    2. Scans restored response for any leaked raw PII (Gemini hallucination).
    3. Raises alert if placeholder present in response that isn't in SESSION_PII_MAP
       (indicates a bug in the redaction pipeline).
    """
    def __init__(self, session_pii_map: SessionPIIMap, presidio_analyzer):
        self.map = session_pii_map
        self.analyzer = presidio_analyzer
    
    def restore_and_validate(self, response_text: str) -> tuple[str, list[str]]:
        """
        Returns: (restored_text, list_of_warnings)
        warnings will be non-empty if:
        - Unknown placeholder found in response
        - Raw PII detected in response after restoration
        """
        restored = self.map.restore(response_text)
        warnings = []
        
        # Check for unknown placeholders
        import re
        unknown = re.findall(r'\[PII_[A-Z]+_\d+\]', restored)
        for u in unknown:
            if u not in self.map._map.values():
                warnings.append(f"Unknown placeholder in response: {u}")
        
        # Scan for leaked raw PII
        pii_hits = self.analyzer.analyze(restored, language='en')
        high_conf = [h for h in pii_hits if h.score > 0.85]
        if high_conf:
            warnings.append(f"Possible PII in response: {[h.entity_type for h in high_conf]}")
        
        return restored, warnings
```


---

## 20. FULL PROJECT ASSESSMENT â€” GAPS AND IMPROVEMENTS (May 2025)

This section documents every gap, missing feature, and improvement identified after a complete audit of PHANTOM against the 2025-2026 state of the art in local AI agent systems. All items here are **additions to what is already specified in Sections 1â€“19**. Claude Code must implement everything in this section during Phase 2.

---

### 20.1 CRITICAL GAPS â€” Will cause crashes or major missing functionality if not fixed

---

#### GAP 1: No Streaming Responses (HIGHEST PRIORITY UX FIX)

**Problem**: Currently Ollama and Gemini calls are fully blocking. The HUD shows a spinner for 5â€“15 seconds with no feedback. This is the single worst UX issue in the project.

**Fix**: Stream tokens from both Ollama and Gemini directly to the HUD using Qt signals.

**Implementation â€” `hud/streaming_worker.py`** (Varshitha):
```python
from PyQt6.QtCore import QThread, pyqtSignal
import ollama

class OllamaStreamWorker(QThread):
    token_received = pyqtSignal(str)      # emitted for each token
    stream_complete = pyqtSignal(str)     # emitted with full response when done
    stream_error = pyqtSignal(str)        # emitted on error

    def __init__(self, prompt: str, model: str):
        super().__init__()
        self.prompt = prompt
        self.model = model

    def run(self):
        full_response = ""
        try:
            for chunk in ollama.generate(model=self.model, prompt=self.prompt, stream=True):
                token = chunk['response']
                full_response += token
                self.token_received.emit(token)
            self.stream_complete.emit(full_response)
        except Exception as e:
            self.stream_error.emit(str(e))
```

**HUD connection** (in `voice_hud.py`):
```python
self.stream_worker = OllamaStreamWorker(enriched_prompt, OLLAMA_MODEL)
self.stream_worker.token_received.connect(self.append_token_to_display)
self.stream_worker.stream_complete.connect(self.on_response_complete)
self.stream_worker.start()

def append_token_to_display(self, token: str):
    # Appends token to response QTextEdit without clearing it
    self.response_display.moveCursor(QTextCursor.MoveOperation.End)
    self.response_display.insertPlainText(token)
```

**Gemini streaming** (in `orchestrator/gemini_oracle.py`):
```python
def stream_query(self, sanitised_prompt: str, callback):
    """callback(token: str) called for each streamed token."""
    response = model.generate_content(sanitised_prompt, stream=True)
    full = ""
    for chunk in response:
        if chunk.text:
            full += chunk.text
            callback(chunk.text)
    return full
```

**Add to requirements.txt**: no new package needed â€” ollama SDK already supports streaming.

---

#### GAP 2: No Conversation Buffer (Multi-Turn Context)

**Problem**: If user says "delete that file" in a follow-up query, the system has no reference to what "that file" means. RAG retrieval gets past interactions but not the current conversation thread.

**New module â€” `memory/conversation_buffer.py`** (Yukta):
```python
from collections import deque
from dataclasses import dataclass

@dataclass
class ConversationTurn:
    role: str          # "user" | "assistant"
    content: str       # sanitised content only (no PII)
    intent: str        # intent type of that turn
    timestamp: float

class ConversationBuffer:
    """
    Stores last N turns of the current session conversation.
    Cleared on session end (not persisted â€” session-scoped only).
    Used for pronoun/reference resolution and multi-turn coherence.
    Max 10 turns to keep prompt size manageable.
    """
    def __init__(self, max_turns: int = 10):
        self._buffer: deque[ConversationTurn] = deque(maxlen=max_turns)

    def add(self, role: str, content: str, intent: str = ""):
        import time
        self._buffer.append(ConversationTurn(role, content, intent, time.time()))

    def get_recent(self, n: int = 5) -> list[ConversationTurn]:
        return list(self._buffer)[-n:]

    def format_for_prompt(self) -> str:
        """Returns last 5 turns formatted for injection into prompt."""
        turns = self.get_recent(5)
        return "\n".join([f"{t.role.upper()}: {t.content}" for t in turns])

    def resolve_reference(self, query: str) -> str:
        """
        Simple reference resolution:
        'delete that' â†’ look in last 3 user turns for file/path mentions.
        Returns enriched query if reference resolved, else original query.
        """
        pronouns = ["that", "it", "this", "those", "them", "the file", "the folder"]
        if any(p in query.lower() for p in pronouns):
            for turn in reversed(self.get_recent(3)):
                if turn.role == "user":
                    # Extract last mentioned filesystem path or object
                    import re
                    paths = re.findall(r'[~/][^\s]+|[\w]+\.\w{2,4}', turn.content)
                    if paths:
                        return query + f" (referring to: {paths[-1]})"
        return query

    def clear(self):
        self._buffer.clear()
```

**Where it plugs in**: In `orchestrator/task_orchestrator.py`, before building the enriched prompt, pass `conversation_buffer.format_for_prompt()` as an additional context block. Add reference resolution at the start of Sentinel processing.

---

#### GAP 3: No Pydantic Validation for Sentinel Output â€” Will Crash on Bad JSON

**Problem**: LLaMA 3.2 3B sometimes returns malformed JSON. Currently `json.loads()` will throw an exception and crash the pipeline.

**Fix â€” Use Ollama's native structured output + Pydantic validation with retry**:

In `sentinel/sentinel_node.py`:
```python
from pydantic import BaseModel, Field, validator
from typing import Optional
import json

class SentinelResult(BaseModel):
    intent: str = Field(..., description="One of: FILE_OP, SYSTEM_CMD, CALENDAR_OP, MEMORY_LOOKUP, WEB_QUERY, GENERAL_QA, UNKNOWN")
    sub_intent: str = Field(default="", description="Specific action: delete, create, list, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)

    @validator('intent')
    def validate_intent(cls, v):
        valid = {"FILE_OP","SYSTEM_CMD","CALENDAR_OP","MEMORY_LOOKUP","WEB_QUERY","GENERAL_QA","UNKNOWN"}
        if v.upper() not in valid:
            return "UNKNOWN"
        return v.upper()

    @validator('confidence')
    def validate_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


def classify_intent_with_retry(query: str, max_retries: int = 3) -> SentinelResult:
    """Calls Ollama with structured output mode. Retries up to 3 times on bad response."""
    for attempt in range(max_retries):
        try:
            response = ollama.generate(
                model=OLLAMA_MODEL,
                prompt=f"{SYSTEM_PROMPT}\n\nQuery: {query}",
                format=SentinelResult.model_json_schema(),  # Ollama native structured output
                options={"temperature": 0.1}
            )
            return SentinelResult.model_validate_json(response['response'])
        except Exception as e:
            if attempt == max_retries - 1:
                # Final fallback: return UNKNOWN with low confidence
                return SentinelResult(intent="UNKNOWN", confidence=0.3, entities=[])
            continue
```

**Add to requirements.txt**: `pydantic>=2.7.0` (already likely included via LangChain).

---

#### GAP 4: No Health Check System â€” Crashes Silently on Missing Services

**New module â€” `utils/health_check.py`**:
```python
import subprocess, sys, os
import chromadb
import ollama
import google.generativeai as genai
from utils.config import GEMINI_API_KEY, OLLAMA_MODEL, CHROMA_PERSIST_DIR

class HealthCheckResult:
    def __init__(self):
        self.checks = {}
        self.all_ok = True

    def add(self, name: str, ok: bool, message: str):
        self.checks[name] = {"ok": ok, "message": message}
        if not ok:
            self.all_ok = False

    def report(self) -> str:
        lines = ["PHANTOM Health Check:"]
        for name, result in self.checks.items():
            icon = "âœ“" if result["ok"] else "âœ—"
            lines.append(f"  {icon} {name}: {result['message']}")
        lines.append("" )
        lines.append("All systems ready." if self.all_ok else "FIX ERRORS ABOVE BEFORE STARTING PHANTOM.")
        return "\n".join(lines)

def run_health_check() -> HealthCheckResult:
    result = HealthCheckResult()

    # 1. Ollama running
    try:
        models = ollama.list()
        model_names = [m['name'] for m in models.get('models', [])]
        if any(OLLAMA_MODEL.split(':')[0] in m for m in model_names):
            result.add("Ollama + LLaMA model", True, f"{OLLAMA_MODEL} loaded")
        else:
            result.add("Ollama + LLaMA model", False,
                       f"{OLLAMA_MODEL} not found. Run: ollama pull {OLLAMA_MODEL}")
    except Exception as e:
        result.add("Ollama", False, f"Not running. Start with: ollama serve")

    # 2. spaCy model
    try:
        import spacy
        spacy.load("en_core_web_lg")
        result.add("spaCy en_core_web_lg", True, "Model loaded")
    except Exception:
        result.add("spaCy en_core_web_lg", False,
                   "Run: python -m spacy download en_core_web_lg")

    # 3. ChromaDB
    try:
        client = chromadb.PersistentClient(CHROMA_PERSIST_DIR)
        result.add("ChromaDB", True, f"Accessible at {CHROMA_PERSIST_DIR}")
    except Exception as e:
        result.add("ChromaDB", False, str(e))

    # 4. Gemini API key
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "your_key_here":
            result.add("Gemini API", False, "No API key set in .env")
        else:
            genai.configure(api_key=GEMINI_API_KEY)
            result.add("Gemini API", True, "Key configured (not verified)")
    except Exception as e:
        result.add("Gemini API", False, str(e))

    # 5. Microphone (for HUD mode)
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        if p.get_device_count() > 0:
            result.add("Microphone", True, f"{p.get_device_count()} audio device(s)")
        else:
            result.add("Microphone", False, "No audio devices found")
        p.terminate()
    except Exception:
        result.add("Microphone", False, "PyAudio not installed or no mic")

    # 6. Whisper
    try:
        import whisper
        result.add("Whisper", True, "Package available")
    except Exception:
        result.add("Whisper", False, "pip install openai-whisper")

    return result

if __name__ == "__main__":
    r = run_health_check()
    print(r.report())
    sys.exit(0 if r.all_ok else 1)
```

**Add to `main.py`** as the very first thing before starting HUD:
```python
from utils.health_check import run_health_check
health = run_health_check()
print(health.report())
if not health.all_ok:
    sys.exit(1)
```

**Quick command**: `python -m utils.health_check`

---

#### GAP 5: No Gemini Rate Limiter â€” Will Fail Under Testing Load

**Free tier limit**: 15 requests per minute, 1 million tokens per minute.

**New module â€” `orchestrator/rate_limiter.py`**:
```python
import time
from collections import deque
import threading

class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for Gemini API.
    Default: 15 requests per 60 seconds (free tier).
    """
    def __init__(self, max_calls: int = 15, period_seconds: float = 60.0):
        self.max_calls = max_calls
        self.period = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def wait_if_needed(self):
        """Blocks until a request slot is available. Call before every Gemini API call."""
        with self._lock:
            now = time.time()
            # Remove calls older than the period
            while self._calls and now - self._calls[0] > self.period:
                self._calls.popleft()

            if len(self._calls) >= self.max_calls:
                sleep_time = self.period - (now - self._calls[0]) + 0.1
                time.sleep(sleep_time)
                # Clean up again after sleep
                now = time.time()
                while self._calls and now - self._calls[0] > self.period:
                    self._calls.popleft()

            self._calls.append(time.time())

# Singleton â€” import and use everywhere
gemini_rate_limiter = TokenBucketRateLimiter(max_calls=12, period_seconds=60.0)
# Using 12 not 15 to leave 3 requests buffer
```

**Usage in `gemini_oracle.py`**:
```python
from orchestrator.rate_limiter import gemini_rate_limiter

def query(self, sanitised_prompt: str) -> str:
    gemini_rate_limiter.wait_if_needed()  # Blocks if at rate limit
    # ... rest of the API call
```

---

#### GAP 6: No PHANTOM CLI Mode â€” Impossible to Test Without GUI

**New file â€” `phantom_cli.py`** (run from project root):
```python
#!/usr/bin/env python3
"""
PHANTOM CLI Mode â€” headless pipeline for testing without PyQt6 GUI.
Usage: python phantom_cli.py
       python phantom_cli.py --query "list my downloads"
       python phantom_cli.py --test   (runs built-in test suite)
"""
import argparse
import sys
from utils.health_check import run_health_check
from sentinel.sentinel_node import SentinelNode
from sentinel.pii_engine import PIIRedactionEngine
from sentinel.session_pii_map import SessionPIIMap
from memory.chroma_manager import ChromaManager
from memory.reprompting import ReprompingModule
from orchestrator.task_orchestrator import TaskOrchestrator
from utils.config import *

def run_query(query: str, verbose: bool = True) -> dict:
    """Run a single query through the full pipeline and return result dict."""
    pii_map = SessionPIIMap()
    sentinel = SentinelNode()
    pii_engine = PIIRedactionEngine(pii_map)
    chroma = ChromaManager()
    reprompt = ReprompingModule(chroma)
    orchestrator = TaskOrchestrator()

    if verbose: print(f"\n[PHANTOM CLI] Query: {query}")

    # Pipeline
    sentinel_result = sentinel.process(query)
    if verbose: print(f"[SENTINEL] Intent: {sentinel_result.intent} (conf: {sentinel_result.confidence:.2f})")

    sanitised, n_pii = pii_engine.redact(query, sentinel_result)
    if verbose: print(f"[PII] Redacted {n_pii} entities. Sanitised: {sanitised}")

    enriched = reprompt.build(sanitised, sentinel_result)
    route = orchestrator.route(sentinel_result, enriched)
    if verbose: print(f"[ROUTE] â†’ {route.target} | Risk: {route.risk_score}")

    response = orchestrator.execute(route, enriched)
    restored = pii_map.restore(response)
    if verbose: print(f"[RESPONSE] {restored}")

    return {"query": query, "intent": sentinel_result.intent, "response": restored, "n_pii": n_pii}

def interactive_mode():
    print("PHANTOM CLI â€” type 'exit' to quit, 'stats' for session stats")
    session_stats = {"total": 0, "local": 0, "cloud": 0, "pii_total": 0}
    while True:
        try:
            query = input("\n> ").strip()
            if not query: continue
            if query.lower() == "exit": break
            if query.lower() == "stats":
                print(f"Session: {session_stats['total']} queries | Local: {session_stats['local']} | Cloud: {session_stats['cloud']} | PII redacted: {session_stats['pii_total']}")
                continue
            result = run_query(query)
            session_stats["total"] += 1
            session_stats["pii_total"] += result["n_pii"]
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PHANTOM CLI")
    parser.add_argument("--query", "-q", help="Run single query")
    parser.add_argument("--skip-health", action="store_true", help="Skip health check")
    args = parser.parse_args()

    if not args.skip_health:
        health = run_health_check()
        if not health.all_ok:
            print(health.report())
            sys.exit(1)

    if args.query:
        run_query(args.query)
    else:
        interactive_mode()
```

---

#### GAP 7: No Custom Exception Hierarchy â€” Error Handling Will Be Messy

**New file â€” `utils/exceptions.py`**:
```python
class PHANTOMBaseError(Exception):
    """Base class for all PHANTOM exceptions."""
    pass

class PIILeakageError(PHANTOMBaseError):
    """Raised when raw PII is detected in a cloud-bound payload."""
    pass

class SentinelError(PHANTOMBaseError):
    """Raised when Sentinel Node fails to classify after max retries."""
    pass

class MemoryWriteError(PHANTOMBaseError):
    """Raised when ChromaDB write-back fails."""
    pass

class RouteError(PHANTOMBaseError):
    """Raised when task orchestrator cannot determine a valid route."""
    pass

class HITLTimeoutError(PHANTOMBaseError):
    """Raised when HITL approval times out on a medium-risk action."""
    pass

class CommandBlockedError(PHANTOMBaseError):
    """Raised when OS middleware detects a blocked command pattern."""
    pass

class GeminiRateLimitError(PHANTOMBaseError):
    """Raised when Gemini rate limit is exhausted and fallback is unavailable."""
    pass

class OllamaUnavailableError(PHANTOMBaseError):
    """Raised when Ollama service is not running."""
    pass

class ChromaDBCorruptionError(PHANTOMBaseError):
    """Raised when ChromaDB data cannot be loaded (possible corruption)."""
    pass
```

---

#### GAP 8: Whisper Not Pre-Warmed â€” First Voice Command Unusably Slow

**Fix in `hud/asr_pipeline.py`** (Varshitha):
```python
class ASRPipeline:
    def __init__(self, model_size: str = "tiny"):
        self._model = None
        self._model_size = model_size
        # Pre-warm: load model immediately on init (do this at app startup, not first use)
        self._load_model()

    def _load_model(self):
        import whisper
        self._model = whisper.load_model(self._model_size)
        # Warm up with a silent audio to trigger any JIT compilation
        import numpy as np
        silence = np.zeros(16000, dtype=np.float32)  # 1 second of silence
        self._model.transcribe(silence, language="en", fp16=False)

    def transcribe(self, audio_array: np.ndarray) -> dict:
        """Returns {"text": "...", "language": "en", "segments": [...]}"""
        return self._model.transcribe(
            audio_array,
            language="en",
            fp16=False,            # CPU mode â€” no fp16
            initial_prompt="PHANTOM AI assistant. User is giving a command in English or Hinglish."
        )
```

The `initial_prompt` improves accuracy for Indian-accented English by priming Whisper's attention.

---

#### GAP 9: No ChromaDB WAL Mode â€” Risk of Data Corruption on Power Loss

**Fix in `memory/chroma_manager.py`** (Yukta):
```python
import chromadb
from chromadb.config import Settings

def create_chroma_client(persist_dir: str) -> chromadb.ClientAPI:
    """Create ChromaDB client with WAL mode enabled for corruption prevention."""
    return chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(
            anonymized_telemetry=False,    # privacy: disable telemetry
            allow_reset=True,              # allow reset for testing
        )
    )
    # WAL mode is enabled by default in SQLite (ChromaDB's backend) from version 0.4+
    # Verify: the .chromadb directory should contain phantom.sqlite3-wal
```

**Backup strategy** (add to `memory/chroma_manager.py`):
```python
import shutil, datetime

def backup_chromadb(persist_dir: str, backup_dir: str = "./data/backups"):
    """
    Creates a timestamped backup of the ChromaDB directory.
    Run at session start (before any writes) as a safety measure.
    """
    import os
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"chromadb_backup_{timestamp}")
    shutil.copytree(persist_dir, dest, dirs_exist_ok=True)
    # Keep only last 5 backups
    backups = sorted(os.listdir(backup_dir))
    for old in backups[:-5]:
        shutil.rmtree(os.path.join(backup_dir, old), ignore_errors=True)
```

---

#### GAP 10: No Pydantic Models â€” Using @dataclass Throughout

Replace all `@dataclass` in the codebase with Pydantic `BaseModel` for automatic validation, JSON serialisation, and schema generation. This is critical for Ollama structured output support.

**Key models to define in `utils/models.py`** (new file):
```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class IntentType(str, Enum):
    FILE_OP = "FILE_OP"
    SYSTEM_CMD = "SYSTEM_CMD"
    CALENDAR_OP = "CALENDAR_OP"
    MEMORY_LOOKUP = "MEMORY_LOOKUP"
    WEB_QUERY = "WEB_QUERY"
    GENERAL_QA = "GENERAL_QA"
    UNKNOWN = "UNKNOWN"

class SentinelResult(BaseModel):
    intent: IntentType
    sub_intent: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    entities: list[str] = []

class PIIEntity(BaseModel):
    placeholder: str       # "[PII_PERSON_1]"
    entity_type: str       # "PERSON"
    tier_detected: int     # 1, 2, or 3
    presidio_score: float  # 0.0â€“1.0

class RouteDecision(BaseModel):
    target: str            # "local" | "cloud" | "memory"
    risk_score: int        # 0â€“100
    hitl_required: bool
    from_cache: bool = False
    enriched_prompt: str = ""

class ExecutionResult(BaseModel):
    status: str            # "success" | "error" | "blocked"
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    command: str = ""
    filesystem_diff: dict = {}

class HITLDisplayData(BaseModel):
    proposed_action: str
    risk_score: int
    risk_level: str        # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    risk_color: str        # hex color
    memory_context: list[str] = []
    command_preview: str = ""
    timeout_seconds: Optional[int] = None

class AnnotatedQuery(BaseModel):
    raw_text: str
    sanitised_text: str = ""
    input_modality: str    # "voice" | "text"
    language: str = "en"
    language_confidence: float = 1.0
    system_state: dict = {}
```

---

### 20.2 IMPROVEMENTS â€” Significantly Enhance PHANTOM's Value and Demo Impact

---

#### IMPROVEMENT 1: Privacy Metrics Dashboard (KILLER DEMO FEATURE)

This is the most visually impactful addition for any judge or panel. Shows exactly what PHANTOM is protecting in real time.

**New module â€” `utils/privacy_metrics.py`**:
```python
from dataclasses import dataclass, field
import threading

@dataclass
class SessionPrivacyMetrics:
    """Thread-safe session privacy counters."""
    total_queries: int = 0
    local_queries: int = 0
    cloud_queries: int = 0
    pii_entities_redacted: int = 0
    fallback_queries: int = 0         # times Gemini was unavailable
    hitl_approved: int = 0
    hitl_rejected: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def privacy_score(self) -> float:
        """Percentage of queries handled locally."""
        if self.total_queries == 0: return 100.0
        return round((self.local_queries / self.total_queries) * 100, 1)

    def record_query(self, route: str, n_pii: int, fallback: bool = False):
        with self._lock:
            self.total_queries += 1
            self.pii_entities_redacted += n_pii
            if route == "local":
                self.local_queries += 1
            elif route == "cloud":
                self.cloud_queries += 1
            if fallback:
                self.fallback_queries += 1

    def record_hitl(self, approved: bool):
        with self._lock:
            if approved: self.hitl_approved += 1
            else: self.hitl_rejected += 1

    def to_display_dict(self) -> dict:
        return {
            "Privacy Score": f"{self.privacy_score}%",
            "Total Queries": self.total_queries,
            "Local (Private)": self.local_queries,
            "Cloud (Sanitised)": self.cloud_queries,
            "PII Entities Protected": self.pii_entities_redacted,
            "HITL Approved": self.hitl_approved,
            "HITL Rejected": self.hitl_rejected,
        }

# Global singleton
session_metrics = SessionPrivacyMetrics()
```

**HUD Privacy Panel** (in `voice_hud.py` sidebar):
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ðŸ”’ Privacy Score: 87%      â”‚
â”‚  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€  â”‚
â”‚  Queries: 15 total          â”‚
â”‚  Local:   13  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–“â–‘â–‘   â”‚
â”‚  Cloud:    2  â–ˆâ–ˆâ–‘â–‘â–‘â–‘â–‘â–‘â–‘â–‘    â”‚
â”‚  PII protected: 34 entities â”‚
â”‚  HITL: 3 approved, 1 reject â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

Update this panel after every query using a QTimer or direct signal.

---

#### IMPROVEMENT 2: Structured Privacy-Respecting Audit Log

Logs WHAT happened (intent, route, outcome, risk) without logging the actual query content or any PII. Safe to review for debugging. Safe to show to panel.

**New module â€” `utils/audit_logger.py`**:
```python
import logging
import datetime
import json
import os

class PrivacyAuditLogger:
    """
    Logs system behaviour WITHOUT logging query content or PII.
    Output format: JSONL (one JSON object per line)
    """
    def __init__(self, log_path: str = "./data/phantom_audit.jsonl"):
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._log_path = log_path

    def log_event(self, event_type: str, **kwargs):
        """
        Allowed kwargs: intent, route, risk_score, outcome, hitl_required,
                        hitl_decision, n_pii_redacted, used_cloud, fallback,
                        execution_time_ms, error_type
        NEVER pass: query_text, sanitised_text, response_text, entities
        """
        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "event": event_type,
            **{k: v for k, v in kwargs.items() if k not in
               ("query_text", "sanitised_text", "response_text", "entities", "command")}
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

# Usage:
# audit.log_event("QUERY_PROCESSED", intent="FILE_OP", route="local",
#                 risk_score=35, outcome="success", n_pii_redacted=2,
#                 used_cloud=False, execution_time_ms=1240)
```

---

#### IMPROVEMENT 3: Command Dry-Run Preview for All OS Commands

Currently only HITL-flagged commands (risk > 40) show any preview. Every OS command should show the user what it will do in human-readable form before executing.

**Add to `middleware/os_middleware.py`** (Vedika):
```python
def dry_run_description(command: str, intent: str, entities: list[str]) -> str:
    """
    Generates a human-readable description of what a command will do.
    Does NOT execute the command. Used for both dry-run preview and HITL display.
    """
    descriptions = {
        "find.*-delete": lambda m: f"Delete files matching the pattern. Preview: {_count_matching_files(command)}",
        "rm ": lambda m: f"Permanently delete: {' '.join(entities)}",
        "mv ": lambda m: f"Move {entities[0]} to {entities[1] if len(entities)>1 else 'destination'}",
        "cp ": lambda m: f"Copy {entities[0]} to {entities[1] if len(entities)>1 else 'destination'}",
        "mkdir": lambda m: f"Create directory: {' '.join(entities)}",
        "ls ": lambda m: f"List contents of: {' '.join(entities)}",
        "touch": lambda m: f"Create empty file: {' '.join(entities)}",
    }
    import re
    for pattern, describer in descriptions.items():
        if re.search(pattern, command):
            try:
                return describer(None)
            except Exception:
                break
    return f"Execute: {command[:60]}{'...' if len(command)>60 else ''}"

def _count_matching_files(command: str) -> str:
    """Count files that WOULD be matched without deleting them."""
    import subprocess, re
    safe_cmd = re.sub(r'-delete', '', command)  # Remove -delete flag
    result = subprocess.run(safe_cmd, shell=True, capture_output=True, text=True, timeout=5)
    lines = [l for l in result.stdout.strip().split('\n') if l]
    return f"{len(lines)} files would be affected"
```

**HITLDisplayData now always populated** regardless of risk_score:
- LOW risk (< 40): shows dry-run description in HUD status bar, auto-proceeds after 3 seconds
- HIGH risk (> 40): shows HITL dialog with dry-run description + countdown

---

#### IMPROVEMENT 4: Session Summary on Exit

When user closes PHANTOM, display a summary card before the window closes.

**In `voice_hud.py`** (Varshitha) â€” override `closeEvent`:
```python
def closeEvent(self, event):
    from utils.privacy_metrics import session_metrics
    summary = session_metrics.to_display_dict()
    msg = "\n".join([f"{k}: {v}" for k, v in summary.items()])
    dialog = QMessageBox(self)
    dialog.setWindowTitle("PHANTOM Session Summary")
    dialog.setText(f"Session complete.\n\n{msg}\n\nThank you for using PHANTOM.")
    dialog.setIcon(QMessageBox.Icon.Information)
    dialog.exec()
    event.accept()
```

---

#### IMPROVEMENT 5: Command History (Up-Arrow Navigation in HUD)

**In `voice_hud.py`** (Varshitha):
```python
from collections import deque

class CommandHistory:
    def __init__(self, max_size: int = 20):
        self._history: deque[str] = deque(maxlen=max_size)
        self._position: int = -1

    def add(self, command: str):
        if command.strip():
            self._history.append(command)
            self._position = -1

    def navigate_up(self) -> str | None:
        if not self._history: return None
        self._position = min(self._position + 1, len(self._history) - 1)
        return list(reversed(self._history))[self._position]

    def navigate_down(self) -> str | None:
        if self._position <= 0:
            self._position = -1
            return ""
        self._position -= 1
        return list(reversed(self._history))[self._position]
```

Wire to the text input field's `keyPressEvent` to intercept Up/Down arrow keys.

---

#### IMPROVEMENT 6: Flexible Model Configuration with Fallback Chain

**In `utils/config.py`** â€” add model preference chain:
```python
# Model preference order â€” system tries each in order, uses first available
SENTINEL_MODEL_PREFERENCE = [
    "llama3.2:3b",       # Best balance â€” default
    "phi3.5",            # Microsoft Phi-3.5 Mini â€” fast, surprisingly capable
    "gemma2:2b",         # Google Gemma 2B â€” very lightweight
    "qwen2.5:3b",        # Alibaba Qwen 2.5 â€” good at structured tasks
]

def get_best_available_model() -> str:
    """Returns the first model in preference chain that is installed in Ollama."""
    try:
        available = [m['name'] for m in ollama.list().get('models', [])]
        for preferred in SENTINEL_MODEL_PREFERENCE:
            if any(preferred.split(':')[0] in a for a in available):
                return preferred
    except Exception:
        pass
    return SENTINEL_MODEL_PREFERENCE[0]  # Return default even if check fails
```

---

#### IMPROVEMENT 7: PII Detection Sensitivity Levels

**In `utils/config.py`** â€” add:
```python
# Options: "LOW" | "MEDIUM" | "HIGH"
# LOW    = Tier 1 (Regex) only. Fast, catches structured PII only.
# MEDIUM = Tier 1 + Tier 2 (Presidio+spaCy). Default. Good balance.
# HIGH   = All three tiers including Semantic LLM. Slowest, most thorough.
PII_SENSITIVITY = os.getenv("PII_SENSITIVITY", "MEDIUM")
```

**In `sentinel/pii_engine.py`** â€” use this to short-circuit the cascade:
```python
def redact(self, query: str, sentinel_result) -> tuple[str, int]:
    results = []
    results.extend(self._tier1_regex(query))
    if PII_SENSITIVITY in ("MEDIUM", "HIGH"):
        results.extend(self._tier2_presidio(query, sentinel_result))
    if PII_SENSITIVITY == "HIGH" and self._low_confidence(results):
        results.extend(self._tier3_llm_semantic(query))
    return self._apply_redaction(query, results)
```

---

#### IMPROVEMENT 8: Whisper Language Detection for Hinglish

**In `hud/asr_pipeline.py`** (Varshitha):
```python
def transcribe(self, audio_array: np.ndarray) -> dict:
    result = self._model.transcribe(
        audio_array,
        fp16=False,
        # Do NOT hardcode language â€” let Whisper detect it
        # This handles English, Hindi, and Hinglish automatically
        initial_prompt="PHANTOM AI assistant for local system management."
    )
    # result["language"] will be "en", "hi", or detected language
    # result["text"] will be transcribed in detected language
    return {
        "text": result["text"],
        "language": result.get("language", "en"),
        "language_confidence": result.get("language_probability", 1.0),
        "segments": result.get("segments", [])
    }
```

Add `language` and `language_confidence` to `AnnotatedQuery` Pydantic model. Pass to Sentinel Node â€” for non-English, add instruction to handle transliterated text.

---

### 20.3 UPDATED PROJECT STRUCTURE (adds all new modules)

Add these files to Section 5's folder structure:

```
phantom/
â”œâ”€â”€ phantom_cli.py                           â† NEW: Headless CLI mode (GAP 6)
â”‚
â”œâ”€â”€ utils/
â”‚   â”œâ”€â”€ exceptions.py                      â† NEW: Custom exception hierarchy (GAP 7)
â”‚   â”œâ”€â”€ models.py                          â† NEW: All Pydantic data models (GAP 10)
â”‚   â”œâ”€â”€ privacy_metrics.py                 â† NEW: Session privacy counters (IMPROVEMENT 1)
â”‚   â”œâ”€â”€ audit_logger.py                    â† NEW: Privacy-respecting audit log (IMPROVEMENT 2)
â”‚   â””â”€â”€ health_check.py                    â† NEW: Service health checker (GAP 4)
â”‚
â”œâ”€â”€ orchestrator/
â”‚   â””â”€â”€ rate_limiter.py                    â† NEW: Gemini rate limiter (GAP 5)
â”‚
â”œâ”€â”€ memory/
â”‚   â””â”€â”€ conversation_buffer.py             â† NEW: Multi-turn context (GAP 2)
â”‚
â”œâ”€â”€ hud/
â”‚   â””â”€â”€ streaming_worker.py                â† NEW: Qt streaming workers (GAP 1)
â”‚
â””â”€â”€ data/
    â”œâ”€â”€ chromadb/                          â† ChromaDB persistence
    â”œâ”€â”€ backups/                           â† ChromaDB backups (GAP 9)
    â””â”€â”€ phantom_audit.jsonl                  â† Audit log (IMPROVEMENT 2)
```

---

### 20.4 UPDATED IMPLEMENTATION PRIORITY ORDER

Replace Section 13 with this corrected order that includes all new modules:

```
Phase 2 build order:

FOUNDATION (do these first â€” everything depends on them):
1.  utils/exceptions.py                 â€” custom exception hierarchy
2.  utils/models.py                     â€” all Pydantic data models
3.  utils/config.py                     â€” environment + model selection
4.  utils/health_check.py               â€” run this to verify environment
5.  utils/privacy_metrics.py            â€” session counters singleton
6.  utils/audit_logger.py               â€” audit log singleton

SENTINEL + PII (core logic):
7.  sentinel/session_pii_map.py         â€” SESSION_PII_MAP + PIIRestorer
8.  sentinel/pii_engine.py              â€” tiered PII cascade
9.  sentinel/sentinel_node.py           â€” Ollama structured output + retry
10. sentinel/pii_restorer.py            â€” response-side PII check

MEMORY (Yukta):
11. memory/conversation_buffer.py       â€” multi-turn context
12. memory/chroma_manager.py            â€” ChromaDB two-collection setup
13. memory/retrieval_engine.py          â€” cosine + recency scoring
14. memory/reranker.py                  â€” cross-encoder re-ranking
15. memory/reprompting.py               â€” prompt construction + token budget
16. memory/eviction_policy.py           â€” LRU + relevance eviction

ORCHESTRATION (Tanmay):
17. orchestrator/intent_cache.py        â€” query intent cache
18. orchestrator/rate_limiter.py        â€” Gemini rate limiter
19. orchestrator/risk_scorer.py         â€” risk score formula
20. orchestrator/routing_rules.py       â€” decision tree
21. orchestrator/gemini_oracle.py       â€” streaming + fallback
22. orchestrator/task_orchestrator.py   â€” LangChain ReAct agent

MIDDLEWARE (Vedika):
23. middleware/blocked_commands.py      â€” blocklist
24. middleware/risk_classifier.py       â€” command risk scoring
25. middleware/rollback_stack.py        â€” undo mechanism
26. middleware/command_mapper.py        â€” NL â†’ OS command
27. middleware/os_middleware.py         â€” sandboxed execution + dry-run

HITL (Tanmay):
28. hitl/approval_states.py            â€” state enum
29. hitl/hitl_controller.py            â€” approval state machine

HUD (Varshitha):
30. hud/asr_pipeline.py                â€” Whisper pre-warmed + language detection
31. hud/streaming_worker.py            â€” Qt token streaming workers
32. hud/state_machine.py               â€” HUD state machine
33. hud/hitl_widget.py                 â€” approval dialog
34. hud/voice_hud.py                   â€” main window + privacy panel + command history

INTEGRATION:
35. phantom_cli.py                        â€” headless test mode
36. main.py                             â€” health check â†’ start HUD
```

---

### 20.5 UPDATED QUICK COMMANDS

```bash
# Health check (always run this first)
python -m utils.health_check

# CLI mode (no GUI â€” for testing)
python phantom_cli.py
python phantom_cli.py --query "list my downloads"

# GUI mode (full system)
python main.py

# Run specific module tests
python -m pytest tests/test_pii_engine.py -v
python -m pytest tests/test_sentinel.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/ -v --tb=short

# View audit log
cat data/phantom_audit.jsonl | python -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"

# View privacy metrics (from CLI mode 'stats' command)
python phantom_cli.py  # then type 'stats'

# Backup ChromaDB manually
python -c "from memory.chroma_manager import backup_chromadb; backup_chromadb('./data/chromadb')"

# Check Ollama models available
ollama list

# Pull model if missing
ollama pull llama3.2:3b

# Check rate limiter status (in Python)
python -c "from orchestrator.rate_limiter import gemini_rate_limiter; print(f'Calls in window: {len(gemini_rate_limiter._calls)}')"
```


## 6. LATEST ARCHITECTURE UPDATES (Token Pre-flight, Async UI, ChromaDB)

### API Rotation & Token Pre-flight
- **Rate Limit Resilience:** Groq API limits (HTTP 429) are now caught cleanly in llm_call_node. The pipeline will seamlessly rotate through backup keys (GROQ_API_KEY_2, etc.) and instantly fail over to OpenRouter or Gemini without crashing the active stream.
- **Token Limits:** Added a 	iktoken pre-flight check to llm_call_node. If context size exceeds 7000 tokens (near Groq's 8000 TPM limit), it automatically reroutes the prompt to a high-context provider (Gemini).

### UI Architecture & Streaming
- PhantomWorker (QThread) offloads LangGraph execution to prevent blocking the PyQt6 GUI.
- **HITL Integration in GUI:** High-risk tools (e.g., delete_files) pause the graph. The worker thread emits hitl_requested and waits on a queue. The main GUI thread intercepts this, shows a QMessageBox, and pushes the user's decision back into the queue for seamless approval flow.

### Memory Systems & ChromaDB
- **ChromaDB Thread Lock Fix:** ChromaManager was rewritten to correctly handle multi-threaded instantiation. un_health_check and main.py both securely import the instantiated singleton _get_chroma() from phantom_graph.py rather than spawning conflicting settings.
- **Active Memory:** A new write_memory tool allows the agent to selectively save specific user facts into persistent ChromaDB, reducing token overhead.

## 7. FULL CODEBASE AUDIT (September 2026)

A ground-up audit of every Python file, live-verified against real API calls
(no mocks). Full methodology: map every file's real dependencies, verify the
graph/router/memory architecture against this spec, run 10 live tests against
the actual pipeline, fix everything found, then re-verify.

### Critical fix — cross-session memory was silently broken
Five ChromaDB collections existed on disk. Config pointed at `helix_session_memory` /
`helix_persistent_memory`, which had been created *before* the code started
passing `hnsw:space: cosine` to `get_or_create_collection()` — that call only
applies the metric at creation time, so those two collections were permanently
pinned to ChromaDB's default, L2. `cosine_distance_to_similarity()` assumed
cosine distance (`1 - distance`) unconditionally; applied to an L2 distance
this silently inverts the scale, e.g. a genuine match at `distance=1.34` scored
`-0.34` and was discarded as noise below `MEMORY_SCORE_THRESHOLD`. Net effect:
retrieval always returned nothing, in every session, and nothing in the logs
signalled it.

Fix: `ChromaManager.distance_space()` reads each collection's *real* configured
metric live rather than assuming one; `cosine_distance_to_similarity()` takes
that metric and applies the correct formula per space (`1 - d/2` for L2,
`-d` for inner product, `1 - d` for cosine). `SESSION_COLLECTION` /
`PERSISTENT_COLLECTION` in `utils/config.py` were repointed at the (already
cosine) `phantom_session_memory` / `phantom_persistent_memory` collections,
and all 81 existing rows were migrated across (re-embedded, not copied blind)
so no memory was lost. Verified live: a fact stored in one thread is now
recalled by a completely separate thread and process.

### Critical fix — the last-resort LLM fallback was dead
`phantom_graph.py`'s Groq → OpenRouter → Gemini failover chain called
`gemini-2.0-flash`, which returns 404 ("no longer available") — verified
live against the real API. A Groq outage plus an OpenRouter rate limit meant
total failure with no working fallback left. Changed to `gemini-3.6-flash`
(the model `llm_router.py` already uses and had verified working). This
exposed a second, previously-latent bug on the same path: Gemini's
`.content` is a list of structured parts, not a string, and it was being
assigned straight into `llm_response` — fixed by routing it through
`llm_router.safe_content()` before use, same as the router's own normalization.
Also fixed: `provider_used` was hardcoded to the *intended* provider and
never updated when a failover actually fired, mislabeling both the UI badge
and the usage log after any failover.

### Fixed — `memory_hits` was permanently reported as 0
`run_memory_retrieve()` computed the retrieved-chunk count and discarded it;
`parallel_preprocess_node()` never returned a `memory_hits` key at all. Now
threaded through both, confirmed non-zero in a live full-pipeline trace.

### Removed — two dead/duplicate routing systems
`llm_call_node` has never called `PhantomRouter` — it has its own inline
model selection, key rotation, and failover chain (this was already true and
is a known architectural gap, not something this audit changed: `PhantomNode`,
the LangGraph wrapper around `PhantomRouter`, is imported by nobody).
`select_model_for_task()` took a `complexity` score from
`providers.hybrid_router.compute_complexity()` and then ignored it entirely,
always returning `"groq"` — that one discarded call was the only thing
keeping the entire `providers/` package (11 files, including the DeepSeek
provider removed from the router config in an earlier pass) in the live
import graph. Removed the call and the parameter.

### Removed — legacy `core/` and `providers/` packages (21 files)
`core/` was the pre-LangGraph HELIX-era router/oracle/sentinel stack, already
half-deleted (`core/oracle/cloud.py` was gone, leaving its only entry point,
`launch_hud.py`, crashing on import with `ModuleNotFoundError`). Nothing in
the live pipeline imported from `core/` or `providers/`; both were removed
along with `launch_hud.py` and the two test files that only exercised
`core/` (`tests/test_chains.py`, `tests/test_fastpath.py`). Confirmed via
full regression (every remaining module still imports, the graph still
compiles with the same 6 nodes, `/status` still returns 200) both before and
after deletion.

### Live test results (all verified against real provider APIs, real ChromaDB, separate OS processes where relevant)
| Test | Result |
|---|---|
| Router selection (bulk→Gemini, stream→Groq) | PASS |
| Gemini content normalization | PASS |
| Injection guard through the full graph (blocked input writes zero usage-log lines) | PASS |
| Cross-session memory recall | PASS (was FAIL before the fix above) |
| Persistent checkpointing across two separate OS processes | PASS |
| Context trimming to a provider's context limit | PASS |
| Async concurrency (4 concurrent `ainvoke()`, genuinely parallel) | PASS |
| Usage logging (correct entries, blocked calls logged as zero) | PASS |
| `/status` endpoint over real HTTP | PASS |
| Full pipeline, traced node by node | PASS |

### Known gap, not fixed by this audit
`phantom_node.py` (the `PhantomRouter`-backed LangGraph node, with
`utils/context_trimmer.py` wired into it) is dead code — nothing imports it.
The live path's own context management and provider failover in
`llm_call_node` work, are tested, and are separate from `PhantomRouter`
entirely. Wiring `PhantomRouter` into `llm_call_node` would remove the
duplication but is an architectural change, not a surgical fix, so it was
left for a deliberate decision rather than folded into this audit.

## 8. LAYERED MEMORY + GUARDIAN RISK GATE (September 2026)

Three interlocking features. Flat ChromaDB memory became a three-layer
hierarchy, the binary injection guard became a three-tier risk gate, and the
graph was rewired so both feed the same turn.

### Feature 1 — Layered memory (`memory/layered_memory.py`, `memory/consolidator.py`)

| Layer | Collection | Holds | TTL | Caps | Priority |
|---|---|---|---|---|---|
| L1 working | `phantom_working_memory` | raw turns verbatim (surrogate text only) | 2 h hard, deleted at retrieval | 10/session, oldest evicted | highest, 3 retrieved |
| L2 episodic | `phantom_episodic_memory` | LLM session summaries, every 5 turns | 7 d soft, marked + filtered | 20/session | medium, 2 retrieved |
| L3 durable | `phantom_durable_memory` | extracted user facts | never | 100 global, no session scoping | lowest priority, highest permanence, 2 retrieved |

`retrieve_layered_context()` runs all three concurrently (`asyncio.gather` over
`run_in_executor`, since the Chroma calls are sync and CPU-bound) and assembles
`[DURABLE FACTS] / [SESSION HISTORY] / [RECENT TURNS]` — recent turns newest
last — as a single `SystemMessage` at position 0. Measured 26–56 ms end to end.

`consolidator.py` runs on a daemon thread and never blocks the response:
L1 write → durable-fact scan → L2 summarisation every 5th turn → L1 eviction.

**L3 is scanned against the user's utterance alone, never the combined turn.**
Scanning `"user → assistant"` lets the model's own reply write permanent user
facts: `"who are you → I am an AI model. I never store your personal data."`
extracts identity *"I am an AI model"* and preference *"I never store your
personal data"*, both attributed to the user, in the one layer that never
expires and is injected into every future session. `consolidate()` therefore
takes `user_text` separately from `turn_text`; L1 keeps the full turn verbatim,
L3 sees only what the user typed.

**L2 falls back to recency when nothing clears the 0.25 similarity bar.** The
`where` filter already scopes L2 to the current session, so similarity is only
ranking within one conversation, not guarding against cross-session bleed —
and `"what have we been talking about?"` is precisely the query that scores
worst against a content summary (measured 0.205) while needing the layer most.

### Migration (`migrate_from_legacy`)

Session docs → L1 if inside the 2 h window, else L2. Persistent docs are
scanned for durable patterns: extracted clauses → L3, anything with no fact in
it → L2 as history. **Migrating persistent docs verbatim into L3 is wrong** —
that collection holds whole transcripts (`"Hello there → Hello! How can I
assist you today?"`), and 41 of them buried a genuine `"I'm a CS student at
BMSCE"` fact out of the top-2 retrieval slots. Originals are renamed
`*_legacy` rather than deleted; the presence of a `*_legacy` collection is what
makes a second run skip instead of re-importing.

### Feature 2 — Guardian (`utils/risk_scorer.py`, `utils/guardian.py`)

Tier 1 is pure Python, no network, measured **0.04 ms**: injection +0.9,
destructive command +0.8, destructive *intent* +0.4, path outside home +0.6,
credentials +0.5, length +0.2, shouting +0.1, system-internals probe +0.3,
known-safe −0.3, clamped to [0, 1]. Tier 2 (Groq, ~300 ms) reviews only the
0.3–0.7 band. Tier 3 is `interrupt()` for human approval above 0.7.

Two non-obvious details, both found by testing rather than reading:

- `DESTRUCTIVE_COMMANDS` must not end in `\b`. `rm -rf` is `rm -r` followed by
  `f`, so a trailing word boundary never matches and the whole signal silently
  never fires — `rm -rf C:\Users\...` scored 0.00 until this was fixed.
- The known-safe bonus applies **only when no other signal fired**. As a
  blanket discount, `"what is my api key password"` buys back 0.3 and slips
  under the review threshold purely for opening with "what is".

### Fixed — averaging diluted the Guardian's verdict

`assess()` originally averaged Tier 1 and Tier 2, as first specified. Because
escalation needed `>= 0.7`, Tier 2 had to reach `1.4 − tier1` to force human
approval — at Tier 1 = 0.3 that is 1.1, mathematically impossible. Observed
live: `"delete the old log files in my downloads folder"` scored Tier 1 0.4,
and the Guardian LLM independently returned 0.9 ("potentially destructive…
could lead to data loss") — a correct, real escalation signal. Averaged with
Tier 1 that became 0.65, under the bar, and the action would have proceeded
with no human in the loop.

Fixed to `combined = max(tier1.score, tier2.score)`: an escalation costs the
user one approval click; a missed escalation lets an unapproved action run.
For a safety gate the asymmetry favors the more cautious of the two opinions,
not their mean.

### Feature 3 — Wiring

Graph is now `START → mode_classifier → guardian_node → parallel_preprocess →
llm → save → END`. `guardian_node` replaces `input_guard_node`, skips
controlled mode entirely, and adds `risk_score`, `guardian_tier`,
`guardian_reason` to `AgentState`. `parallel_preprocess_node` injects the
layered context and reports `memory_layers_used`; `pii_restore_node` fires
`consolidate_async` (dispatch measured 0.7–1.2 ms) and increments `turn_count`.

## 9. LLM ROTATION, PROVIDER-NAME LEAKAGE, CONTROLLED-MODE DUPLICATE SCAN (September 2026)

### Rotation never triggered on a stall, only on a fast error

`llm_call_node` has its own inline fallback cascade (backup Groq keys →
openrouter → gemini) and has never called `PhantomRouter` — confirmed
again this session; `_invoke_with_rotation` and `agentic_weight` do not
exist anywhere in this codebase. The cascade itself was correct. The bug
was that it only runs on an **exception**, and none of the four LLM
clients (`ChatGroq`, `ChatGoogleGenerativeAI`, `ChatOpenAI`, `ChatOllama`)
had a request-level timeout — a client that stalls rather than erroring
fast never raises, so nothing ever rotates, and the only backstop was
`run_query()`'s own 60s ceiling, which doesn't retry.

Fixed with two layers, because one alone isn't trustworthy: `request_timeout`/
`timeout` set on every cloud client, **plus** a calling-side
executor-enforced timeout around every cascade attempt. Verified live —
`ChatGroq`'s `request_timeout` is genuinely honored (a 0.001s setting
raised in 1.855s); `ChatGoogleGenerativeAI`'s `timeout=` is **not**
reliably honored for a stalled connection (the same 0.001s setting took
34.183s, stuck in the TLS handshake phase specifically). Since Gemini is
the last link in the chain, trusting its own field alone would leave the
exact failure mode this was meant to fix unfixed for that one provider.

Two more things found while measuring the cascade end-to-end, not by
inspection:
- When every provider genuinely fails, the code used to re-raise the
  *original* raw exception (e.g. `groq.AuthenticationError: Invalid API
  Key`), propagating as an unhandled graph node exception that would
  surface raw provider text straight to the user. Now returns a clean
  generic message through the normal return path.
- `_get_fallback_llm("openrouter")` / `("gemini")` took **13.4s / 5.1s just
  to construct** — one-time Python import cost for `langchain_openai` /
  `langchain_google_genai`, paid on first use. Those are only reached from
  the fallback path, which normally never runs — so the first real Groq
  outage was also the first time those packages had ever been imported,
  adding ~18s of pure import latency on top of the actual retry, at
  exactly the moment the user is already waiting on a failure. Now
  pre-constructed during `prewarm_pipeline()`.

Verified: Groq forced to fail with an invalid key on a warm process →
cascades through a real live OpenRouter 429 → succeeds via Gemini,
correct answer, 18.71s total.

### Provider names must never reach the user

Removed from every UI surface, not just the "via Groq" badge asked about:
v1's badge always showed the literal `provider_used` (including `"via
Timeout"` on failure) — now always `"via Phantom ⬡"`. Both v1's
`_on_error` and v2's `_on_failed` interpolated the raw exception string
from the worker thread directly into user-visible text; `str(exc)` has no
guarantee of staying provider-name-free (confirmed: a raw
`groq.AuthenticationError` was one exception away from reaching exactly
this code path before the source-level fix above landed), so both are now
fixed generic messages regardless of what the exception says. The worst
one was live, not latent: `agent_v2/pipeline.py`'s `cloud["error"]`
flowed straight into `result.restored_response` — the actual answer text
shown to the user, not a debug label.

### Controlled-mode duplicate scan

Added a narrowly-anchored pattern to `CONTROLLED_PATTERNS` (matched
against the whole input, like every other pattern there — not a bare
substring, so "find duplicate handling logic in my code" isn't hijacked
into a filesystem scan) and wired `deterministic_action_node` to handle
it: the first real action in what was previously a pure
acknowledgement-only stub.

Deliberately excludes "remove/delete duplicate" — controlled mode skips
`guardian_node` entirely (see `route_after_mode`), so a destructive action
routed through it would run with zero risk-scoring and zero HITL, exactly
what `delete_all_duplicates` being in `HIGH_RISK_TOOLS` exists to prevent.
Deletion stays on the normal smart-mode path where that gate runs.

Deliberately reuses `find_duplicates()` from §8's fix rather than
reimplementing scanning with a naive full-file-hash approach — that would
regress to the >180s runtime the content-hash-plus-budget design was
built to fix on this same real Downloads folder (two 467MB files alone).
The original ask's "<5s" target isn't achievable here without cutting
real completeness; verified 13–20s through the live app, which is what
honest, bounded coverage of this folder costs.

## 10. DRAGGABLE OVERLAYS + REAL CONTROLLED-MODE ACTIONS (September 2026)

### Drag handle (`utils/drag_handle.py`)

A ⠿ grip at the left of the input bar on both agents. Hold 300ms to pick
the window up, drag, release to drop. Position is saved into each agent's
existing `WindowSettings` file (v1 `phantom_memory/settings.json`, v2
`agent_v2/data/settings.json` — already separate, so the two agents keep
independent placement) and restored next launch, clamped to the current
screen and snapping within 20px of an edge.

Drag is gated behind the handle *and* a hold, not the whole bar: a click
anywhere else must still reach the input field, and drag-on-press would
make a mis-aimed click nudge the window.

Two things that only showed up when run, not when read:

- **`show_window()` re-positions on every summon**, not just at
  construction. Without routing that call through the saved position, a
  dragged window snapped back to centre the next time the hotkey was
  pressed — the drag appeared to work, then silently undid itself.
- **Clamping must use `sizeHint()`, not `size()`.** Before the first
  `show()` a QWidget still reports Qt's 640x480 placeholder while this
  window is really 680x84 (both measured). Taking `max(size(), sizeHint())`
  picked the placeholder's 480 height and clamped against a box ~400px
  taller than the window is, so dragging down hit an invisible floor well
  above the screen bottom. Both overlays lay out under
  `SizeConstraint.SetFixedSize`, which pins the window to its sizeHint, so
  sizeHint is authoritative in both states.

Shared rather than inlined per window (the spec asked for inline "to keep
it simple") — the same ~90 lines of press/timer/clamp state would otherwise
exist twice and drift, the same reasoning `window_settings.py` documents
for itself.

### Controlled mode now actually does things (`utils/system_actions.py`)

It was a stub: `"open chrome"` / `"volume up"` matched a pattern, skipped
the LLM, and returned `"Running: <command>"` having done nothing.
Implemented for real: radios (Bluetooth/Wi-Fi on/off/state), volume
(up/down/mute/set N%), brightness (up/down/set), app launch/close, screen
lock. Unrecognised input returns `None` so the caller falls back to its old
reply instead of claiming success.

**Radios use the WinRT Radio API driven from PowerShell**
(`scripts/radio_control.ps1`), not `Enable-PnpDevice`/`Disable-PnpDevice`
on the adapter. The PnP route is the obvious one and needs an elevated
shell; an assistant launched from the tray doesn't have that. WinRT works
as the logged-in user — verified live without elevation.

**Everything here is read-only or one-click reversible, by design.**
Controlled mode skips `guardian_node` entirely, so nothing routed here is
risk-scored or HITL-approved. Consequences taken seriously:
- App close uses `taskkill` **without `/F`** — a forced kill discards
  unsaved work irreversibly with no approval step in front of it; a plain
  close request lets the app prompt.
- `"remove/delete duplicate"` is still **not** routed here. Deletion stays
  on the smart path where the HITL gate runs (`delete_all_duplicates`
  remains in `HIGH_RISK_TOOLS`).

Two bugs found by running it:

- `set_brightness` called `WmiSetBrightness` as a **static class method**,
  which fails with `Type mismatch for parameter "Brightness"` even on
  hardware that supports it. It is an instance method — fetched with
  `Get-CimInstance` and invoked with `-InputObject`, it sets the panel
  immediately. The old failure message blamed "external monitor / no
  software brightness control", which was a guess and wrong here: reading
  brightness worked fine on the same display.
- The classifier accepted `"is bluetooth"` but the dispatcher's regex did
  not, so it routed to controlled mode and fell through to the raw
  `"Running: is bluetooth"` stub. **When those two patterns disagree the
  stub is what the user sees** — they now cover the same phrasings, and a
  leading "is"/"what's" reports state rather than switching the radio on.

Not exercised deliberately: Bluetooth **off** (3 Bluetooth LE HID devices
are connected on this machine and could be the user's mouse or keyboard),
Wi-Fi off (drops the network), and screen lock (would lock the live
session). All three are implemented and reachable by the user.

## 11. LLM_CALL_NODE WIRED TO PHANTOMROUTER; TWO MORE PROVIDER-LEAK SITES (September 2026)

Two bugs reported together: a raw provider/timeout string still reaching the
UI, and the second query in a session failing because Groq's per-minute quota
was already spent. Both traced back to the same root already named in §7 and
§9 as a known, deliberate gap — `llm_call_node` never called `PhantomRouter` —
and this phase finally closed it.

### BUG 1 — two more leak sites, neither caught by the obvious grep

The reported string ("Request timed out after 60s. Groq API key may be
missing or overloaded. Try again.") wasn't in `llm_call_node` at all — it was
`run_query()`'s own 60s outer-timeout branch, and `resume_query()`'s HITL-
resume exception branch had the same problem independently. Both flow through
the *normal* response path (`final_response`, not an exception), so §9's
`_on_error`/`_on_failed` generic-message fix — which only wraps the exception
path — never touched them. Both now return the same fixed string used
everywhere else: `"Something went wrong. Please try again."`. A repo-wide
sweep for `Groq|timed out after 60|API key may be|overloaded` (beyond just the
two files already touched) turned up nothing else live — every remaining hit
is a comment or a config sample.

### BUG 2 — the wiring, and where the user's own fix spec was wrong

`llm_call_node` now calls `get_router()` and drives the turn through
`router.stream(messages, estimated_tokens=..., agentic=state["agent_mode"],
tools=ALL_TOOLS, on_provider=...)`, replacing its entire old inline cascade
(`select_model_for_task` → `_get_bound_llm` → backup Groq keys →
`_get_fallback_llm("openrouter"/"gemini")`) — all now deleted. The reported
mechanism holds up: that inline cascade tracked nothing across calls, so once
Groq's 5100 TPM window was spent, *every* subsequent turn retried Groq (and
every `GROQ_API_KEY_n`) from scratch before ever reaching another provider —
stacked against `run_query()`'s 60s ceiling, a slow-failing cascade could
still be working through dead keys when the outer timeout fired. Verified
directly: with `groq.tokens_used` forced to its 5100 limit, a query is now
routed to Gemini on the first attempt, correct answer, no retry cycle.

The fix request's own pseudocode had several claims that didn't match this
codebase and were corrected rather than implemented literally:
- `router._slots[0]` — `_slots` is `dict[str, ProviderSlot]` keyed by
  provider name, not a list. Real form: `router._slots["groq"]`.
- `slot.consume(total)` — no such method. `record_success(tokens)` /
  `record_failure()` already existed and already ran inside `invoke()`/
  `stream()`; nothing needed adding here.
- `self.last_provider_used = slot.name` as a shared instance attribute on
  the router singleton — a real regression risk, not just a style
  preference: `PhantomRouter` is a shared singleton and two turns can run
  concurrently under LangGraph, so a shared mutable "last provider" field
  lets one turn report *another* turn's provider. `invoke()`'s existing
  `(response, provider_name)` tuple return was already race-free and
  untouched; `stream()` (a generator with no simple return channel) got a
  new `on_provider` callback instead, fired once right as the router commits
  to a slot — mirrors the codebase's existing `token_callback` idiom rather
  than inventing shared state.
- Calling `router.invoke(..., stream=False)` from `llm_call_node` as
  specified would have silently killed token-by-token streaming to the UI
  (§20.1 GAP 1's whole point). Wired to `router.stream(...)` instead,
  preserving real-time `token_callback` behavior exactly as before.
- Not mentioned in the spec at all, and the most severe gap: `PhantomRouter`
  clients built by `_get_client()` are plain — no tools bound. `llm_call_node`
  requires tool-bound models for its entire ReAct loop; wiring it to the
  router without addressing this would have silently stripped Phantom's
  ability to call any tool (file operations, everything §6.5 lists) as an
  unannounced side effect of a routing fix. Fixed with a new
  `PhantomRouter._client_for(name, tools)` that binds tools onto the cached
  client per-call without disturbing what's cached (`bind_tools()` returns a
  new wrapper rather than mutating in place — same pattern `llm_call_node`
  already relied on); `tools` is now a parameter on both `invoke()` and
  `stream()`.
- `agentic_weight` was added to `PROVIDER_CONFIG` and threaded through
  `_pick_slot()` and `_log_pick()` largely as specified (gemini 150, groq 20,
  openrouter 80, nvidia 60, xai 40, ollama 5) — this part of the spec was
  accurate. `agentic=True` skips the Groq speed lane unconditionally and
  scores weighted selection on `agentic_weight` instead of `weight`. Verified
  live: "organize my downloads by file type" → `mode_classifier` now
  recognizes it (new `_ORGANIZE_FILES` pattern in `AGENT_PATTERNS` — nothing
  previously matched this phrasing) → `agentic=True` → router scores groq
  20×1.0=20 vs gemini 150×1.0=150 → gemini picked, confirmed via
  `_pick_slot()` directly rather than by actually running the reorganization
  (see below).

### A gap the router's own tests didn't catch, that live testing did

`stream()`'s calling-side timeout (`_call_with_timeout`, independent of each
client's own `request_timeout`/`timeout` field — see §9 for why the field
alone isn't trustworthy) originally wrapped only `next(chunk_iter)`, on the
assumption that `client.stream(...)` itself is cheap/lazy — true for a
generator-based implementation, but not guaranteed. Caught live, not by
inspection: pointing the router at an unreachable Ollama host
(`http://localhost:1`) took the full 60s outer `run_query()` ceiling to fail,
not the 15s the calling-side backstop should have enforced — `client.stream()`
itself was blocking before ever handing back an iterator, entirely outside the
wrapped window. Fixed by wrapping `client.stream(...)` and the first
`next()` together in one `_call_with_timeout` call, so the bound covers
connection setup through first byte regardless of which half hangs. Re-verified:
the same unreachable-host case now fails in 13.5s.

### Test 5's spec vs. the router's actual (correct) design

The fix request's TEST 5 asserted Groq should show "0 or low usage" after 5
ordinary chat queries, on the assumption that PhantomRouter should shift
general traffic to Gemini. That's not what was built, deliberately: the speed
lane (`_pick_slot`, non-agentic path) prefers Groq for any short/streaming
call *because it's dramatically faster* — measured live, 1.4–5.0s per trivial
query on Groq vs. 19.8s for the same class of question on Gemini. Run for
real: 4 of 5 ordinary queries were served by Groq quickly, the 5th
automatically fell to Gemini once Groq wasn't a good candidate, and forcing
Groq's budget to its limit (separately, TEST 3) reroutes every subsequent call
to Gemini on the first try. That is the correct fix — Gemini taking over
*all* ordinary traffic would trade the original timeout bug for a
latency regression on every trivial query. Recorded as a spec correction, not
implemented literally.

### Live test results (real provider APIs, real graph, this session)
| Test | Result |
|---|---|
| Sanitization: no provider/timeout/API-key text reaches the user on total failure | PASS |
| 5 consecutive ordinary queries, zero failures | PASS |
| Groq forced to its tracked limit → next call reroutes to Gemini, correct answer | PASS |
| Agentic phrase → `agent` mode → Gemini wins agentic-weight scoring (150 vs 20) | PASS |
| Live agent-mode turn end-to-end through the real graph avoids Groq | PASS |
| Groq shows near-zero usage after ordinary traffic (TEST 5b, as literally specified) | Did not hold — see above; not a defect |
