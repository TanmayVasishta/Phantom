# CLAUDE.md — Project HELIX
## Master Context File for Claude Code

> Place this file at the **root of the HELIX repository** as `CLAUDE.md`.
> Claude Code reads this automatically on every session. Keep it updated as the project evolves.

---

## 0. HOW TO USE THIS FILE

This file gives Claude Code complete context about Project HELIX so it can assist with implementation, debugging, and architecture decisions without needing repeated explanations. Every section is intentionally detailed. Do not summarise or shorten it.

---

## 1. PROJECT IDENTITY

| Field | Value |
|---|---|
| Project Name | HELIX — Hybrid Edge Cloud Learning and Intelligent Exchange |
| Type | AI Operating System (AIOS) — Major Project, Phase 1 complete |
| Institution | B.M.S. College of Engineering (BMSCE), Dept. of CSE, Bengaluru |
| Academic Year | 2025–2026 |
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

HELIX is a **privacy-first hybrid local-cloud AI Operating System** that runs on consumer hardware (minimum 16 GB RAM laptop). It accepts natural language voice/text commands, sanitises all PII locally, routes tasks intelligently between a local LLM and cloud, and requires explicit human approval before irreversible OS actions.

### Core Design Principles
1. **Local-first**: Every query is processed locally before any cloud routing decision.
2. **PII-zero cloud boundary**: Nothing with PII ever leaves the machine.
3. **Human-supervised**: Any action with risk_score > 40 requires explicit user approval.
4. **Offline-capable**: Core functions work without internet (Gemini calls gracefully degrade).
5. **Consumer hardware**: Runs on 16 GB RAM, no GPU required (GPU optional for speed).

### Six Research Gaps HELIX Fills
1. No local PII guardrail before cloud routing in any existing system
2. No mandatory HITL checkpoint before OS-level actions
3. Hardware exclusion — most capable AI requires expensive cloud subscriptions
4. No offline-first persistent contextual memory
5. Unfair privacy trade-off (intelligence vs sovereignty)
6. Dangerous AI autonomy in multi-step agents (AutoGPT-style)

### SDG Alignment
- **SDG 9** — Industry, Innovation and Infrastructure (decentralised AI on edge)
- **SDG 16** — Peace, Justice and Strong Institutions (digital privacy, ethical AI)

---

## 3. FIVE-LAYER PIPELINE ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LAYER 1: Input & Intent Recognition                                     │
│  [Voice HUD — PyQt6 async] → Whisper ASR → Text Normalisation           │
│  Owner: Varshitha                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: Privacy & Context                                               │
│  [Sentinel Node — LLaMA 3.2 3B] → [PII Redaction Engine]               │
│  → [Memory-Augmented Re-prompting — ChromaDB RAG]                        │
│  Owner: Tanmay (Sentinel + PII + Re-prompting), Yukta (ChromaDB)         │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: Dynamic Workload Router                                         │
│  [LangChain Task Orchestrator] → routing decision + risk scoring         │
│  Owner: Tanmay                                                            │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 4: Dual-Path Execution                                             │
│  LOCAL → [Python OS Middleware] (Vedika)                                  │
│  CLOUD  → [Gemini 1.5 Flash Oracle] (Tanmay coordinates)                │
├─────────────────────────────────────────────────────────────────────────┤
│  LAYER 5: Safety & Visualisation                                          │
│  [HITL Dashboard — PyQt6] → Approve / Reject / Modify                   │
│  → [PII Restorer] → [Async Memory Write-back]                            │
│  Owner: Tanmay                                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. TECH STACK

### Runtime & Language
- **Python 3.10+** — all AI pipelines, middleware, orchestration
- **Node.js** — not used in production (only build tooling)

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
- **PyQt6** — Voice HUD, HITL Dashboard (QThread for async)

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
helix/
├── CLAUDE.md                          ← this file
├── README.md
├── requirements.txt
├── .env                               ← GEMINI_API_KEY (never commit)
├── .gitignore
│
├── main.py                            ← entry point, starts all services
│
├── sentinel/
│   ├── __init__.py
│   ├── sentinel_node.py               ← Tanmay: intent classification via Ollama
│   ├── pii_engine.py                  ← Tanmay: tiered PII redaction
│   ├── session_pii_map.py             ← Tanmay: SESSION_PII_MAP + PII Restorer
│   └── intent_types.py                ← Enum: FILE_OP, SYSTEM_CMD, etc.
│
├── memory/
│   ├── __init__.py
│   ├── chroma_manager.py              ← Yukta: ChromaDB collections management
│   ├── retrieval_engine.py            ← Yukta: cosine + recency decay scoring
│   ├── reranker.py                    ← Tanmay: cross-encoder re-ranking
│   ├── reprompting.py                 ← Tanmay: prompt construction + token budget
│   └── eviction_policy.py             ← Yukta: LRU + relevance hybrid eviction
│
├── orchestrator/
│   ├── __init__.py
│   ├── task_orchestrator.py           ← Tanmay: LangChain ReAct routing engine
│   ├── risk_scorer.py                 ← Tanmay: risk_score formula
│   ├── routing_rules.py               ← Tanmay: decision tree logic
│   └── gemini_oracle.py               ← Tanmay: Gemini API wrapper + PII assertion
│
├── middleware/
│   ├── __init__.py
│   ├── os_middleware.py               ← Vedika: sandboxed command execution
│   ├── command_mapper.py              ← Vedika: intent → OS command translation
│   ├── risk_classifier.py             ← Vedika: command-level risk scoring
│   ├── rollback_stack.py              ← Vedika: undo mechanism
│   └── blocked_commands.py            ← Vedika: static + dynamic blocklist
│
├── hitl/
│   ├── __init__.py
│   ├── hitl_controller.py             ← Tanmay: approval state machine
│   └── approval_states.py             ← Tanmay: PENDING, APPROVED, REJECTED, MODIFIED
│
├── hud/
│   ├── __init__.py
│   ├── voice_hud.py                   ← Varshitha: main PyQt6 HUD window
│   ├── asr_pipeline.py                ← Varshitha: Whisper + normalisation
│   ├── state_machine.py               ← Varshitha: IDLE→LISTENING→PROCESSING→...
│   └── hitl_widget.py                 ← Varshitha: approval dialog widget
│
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   └── config.py                      ← loads .env, model paths, thresholds
│
└── tests/
    ├── test_pii_engine.py
    ├── test_sentinel.py
    ├── test_routing.py
    └── test_memory.py
```

---

## 6. MODULE SPECIFICATIONS

### 6.1 Sentinel Node (`sentinel/sentinel_node.py`) — TANMAY

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

**Pass 1 — Intent Classification**:
```python
def classify_intent(query: str) -> dict:
    """
    Returns:
    {
        "intent": IntentType,
        "confidence": float,   # 0.0–1.0
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

**Pass 2 — Basic PII Pre-screen**:
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

### 6.2 PII Redaction Engine (`sentinel/pii_engine.py`) — TANMAY

**Purpose**: Tiered PII detection and redaction. Three-tier cascade. Output must be zero-PII guaranteed.

**Architecture** (ORIGINAL DESIGN — Tiered Cascade):

```
Tier 1: Regex (FAST — always runs first)
    ↓ (if missed entities detected by confidence scoring)
Tier 2: Presidio + spaCy NER (ACCURATE)
    ↓ (if Tier 2 confidence still low on some spans)
Tier 3: LLaMA 3.2 3B semantic check (SAFETY NET — expensive, rare)
    ↓
Merge all results → deduplicate → apply redaction → build SESSION_PII_MAP
```

**Tier 1 — Regex patterns for Indian context**:
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

**Tier 2 — Presidio configuration**:
```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine

# Recognisers to load:
# EmailRecognizer, PhoneRecognizer, CreditCardRecognizer,
# PersonRecognizer, LocationRecognizer, NRP recogniser (for Indian IDs)
```

**Tier 3 — LLaMA semantic check** (only called when Tiers 1+2 combined confidence < 0.80):
```python
SEMANTIC_PII_PROMPT = """Analyse this text for ANY personally identifiable information including:
indirect references ("my sister's address"), financial references ("the card I use for Netflix"),
medical information, or any data that could identify a specific person.

List ALL PII found as JSON:
{"pii_found": [{"text": "...", "type": "...", "start": 0, "end": 0}]}
If none found: {"pii_found": []}
"""
```

**SESSION_PII_MAP** (ORIGINAL DESIGN — Presidio does NOT do this):
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

**PII Restorer** (ORIGINAL DESIGN — bidirectional PII control):
- After Gemini responds, run `SESSION_PII_MAP.restore(response)` before showing to user.
- Also scan response for any leaked PII patterns (Gemini hallucinated real-sounding PII).
- Alert if response contains placeholders that don't match the map (indicates a bug).

---

### 6.3 ChromaDB Memory Manager (`memory/chroma_manager.py`) — YUKTA

**Purpose**: Offline persistent vector memory. Two-collection design.

**Collections**:
```python
# Collection 1: Session memory (cleared each session)
SESSION_COLLECTION = "helix_session_memory"

# Collection 2: Persistent memory (survives restarts)
PERSISTENT_COLLECTION = "helix_persistent_memory"
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

**Retrieval** (ORIGINAL DESIGN — Recency-weighted scoring):
```python
def retrieve_relevant(query: str, top_k: int = 5) -> list[dict]:
    """
    1. Embed query → 384-dim vector
    2. ChromaDB cosine similarity search → top-k=5
    3. Apply recency decay:
       final_score = cosine_sim * exp(-λ * days_old)
       where λ = 0.1
    4. Filter: final_score > 0.65
    5. Return top-3 after filtering
    """
    λ = 0.1
    # ...
```

**Eviction policy** (ORIGINAL DESIGN — LRU + relevance hybrid):
```python
def evict_if_needed(collection_name: str, max_entries: int = 1000):
    """
    Eviction score = (recency_rank * 0.4) + (retrieval_frequency * 0.6)
    Remove entries with lowest score when collection > max_entries.
    """
```

**Write-back** (ORIGINAL DESIGN — outcome-gated):
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

### 6.4 Memory-Augmented Re-prompting (`memory/reprompting.py`) — TANMAY

**Purpose**: Constructs enriched prompts by injecting relevant memory context.

**Cross-encoder re-ranking** (ORIGINAL DESIGN — added on top of ChromaDB):
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
SYSTEM_PROMPT = """You are HELIX, a privacy-first AI assistant for local system management.
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

### 6.5 LangChain Task Orchestrator (`orchestrator/task_orchestrator.py`) — TANMAY

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

### 6.6 Gemini Oracle (`orchestrator/gemini_oracle.py`) — TANMAY

**Purpose**: Cloud reasoning via Gemini 1.5 Flash. Strict PII guarantee before every API call.

**Critical pre-call assertion** (ORIGINAL DESIGN — must never be removed):
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

### 6.7 Python OS Middleware (`middleware/os_middleware.py`) — VEDIKA

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
        mkdir ~/test        → inverse: rmdir ~/test
        cp a.txt b.txt      → inverse: rm b.txt
        mv a.txt ~/docs/    → inverse: mv ~/docs/a.txt .
        
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
        → "find ~/Downloads -name '*.pdf' -mtime +30 -delete"
    
    FILE_OP/list + ["Documents"]
        → "ls -lah ~/Documents"
    
    FILE_OP/create + ["notes.txt", "Desktop"]
        → "touch ~/Desktop/notes.txt"
    """
```

---

### 6.8 HITL Controller (`hitl/hitl_controller.py`) — TANMAY

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

### 6.9 Voice HUD (`hud/voice_hud.py`) — VARSHITHA

**Purpose**: Asynchronous PyQt6 interface for voice + text input and system state display.

**State machine** (ORIGINAL DESIGN):
```
IDLE → LISTENING (mic activated) → PROCESSING (Whisper ASR running)
     → AWAITING_SENTINEL (Sentinel Node processing)
     → AWAITING_HITL (HITL approval dialog shown)
     → DISPLAYING (response shown)
     → back to IDLE
```

**Key components**:
- `AudioCapture` (QThread): non-blocking microphone capture
- `WhisperWorker` (QThread): ASR in background thread
- `TextNormaliser`: lowercase → filler word removal → punctuation → spell check
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

**ASR pre-processing** (ORIGINAL DESIGN — Indian accent robustness):
```python
def preprocess_audio(audio_data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """
    1. Bandpass filter: 300–3400 Hz (voice frequency range)
    2. Noise gate: suppress frames below -40 dB
    3. Amplitude normalisation: RMS to -20 dBFS
    Output: cleaned PCM array ready for Whisper
    """
```

---

## 7. DATA FLOW — COMPLETE SEQUENCE

```
1. User speaks or types
        ↓
2. [HUD] AudioCapture (QThread) → WhisperWorker → raw transcript
        ↓
3. [HUD] TextNormaliser → PromptIntentAnnotator → AnnotatedQuery
        ↓
4. [SENTINEL] Pass 1: LLaMA 3.2 3B intent classification
   → if confidence < 0.65: return ClarificationRequest to HUD (GOTO 1)
   → if confidence >= 0.65: continue
        ↓
5. [PII ENGINE] Tier 1 (Regex) → Tier 2 (Presidio+spaCy) → Tier 3 (LLaMA, if needed)
   → Build SESSION_PII_MAP
   → Output: sanitised_query (guaranteed zero-PII)
        ↓
6. [MEMORY] ChromaDB cosine search → top-5 results
   → Cross-encoder re-rank → top-2 snippets
   → Recency decay scoring → filter < 0.65
        ↓
7. [RE-PROMPTING] Build enriched_prompt:
   system_instructions + memory_context + sanitised_query
   → Token budget check (max 2048 tokens)
        ↓
8. [ORCHESTRATOR] Routing decision:
   LOCAL (FILE_OP/SYSTEM_CMD with conf≥0.80) → GOTO 9a
   CLOUD (GENERAL_QA/UNKNOWN or conf<0.80)   → GOTO 9b
   MEMORY (MEMORY_LOOKUP)                     → GOTO 9c
        ↓
   Risk score calculated → if risk_score > 40: flag HITL_REQUIRED
        ↓
9a. [OS MIDDLEWARE] Blocked check → resource-capped subprocess → ExecutionResult
    → RollbackStack.push(command, inverse)
    → ExecutionContextTracker.record(diff)
9b. [GEMINI ORACLE] PII assertion → API call → AI response → PII Restorer
9c. [CHROMADB] Direct semantic search → return result
        ↓
10. if HITL_REQUIRED:
    [HITL CONTROLLER] → HITLDisplayData → [HUD] shows approval dialog
    → User: APPROVE / REJECT / MODIFY
    → if APPROVED: execute + write-back to persistent_memory (async)
    → if REJECTED: rollback + write-back to session_memory only
    → if MODIFIED: re-route from step 8
        ↓
11. [PII RESTORER] Substitute SESSION_PII_MAP placeholders in response
        ↓
12. [HUD] Display final response to user
        ↓
13. [MEMORY] Async write-back to ChromaDB (summarise → embed → store)
```

---

## 8. KEY ALGORITHMS — IMPLEMENTATION REFERENCE

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

### Cluster A — PII Sentinel Node (Tanmay's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [1] BASE | Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing | Ding, Mallick, Wang et al. | 2024 | 2404.14618 | Routes queries between small local + large cloud model based on difficulty. 40% fewer cloud calls. |
| [2] | PRvL: Quantifying LLM Capabilities for PII Redaction | Anonymous | 2025 | 2508.05545 | No single PII method works across all entity types. Justifies tiered cascade. |
| [3] | RouteLLM: Learning to Route LLMs with Preference Data | Ong et al. | 2024 | 2406.18665 | Learned routing achieves 2x cost reduction. Validates HELIX routing architecture. |
| [4] | Agentic RAG: A Survey | Xiong et al. | 2025 | 2501.09136 | Autonomous agents in RAG pipelines with dynamic retrieval and write-back. |
| [5] | PBa-LLM: Privacy- and Bias-aware NLP using NER | Peña et al. | 2025 | 2507.02966 | NER-driven anonymisation at LLM input layer. Justifies Sentinel Node NER design. |

### Cluster B — Memory Management (Yukta's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [6] BASE | MemGPT: Towards LLMs as Operating Systems | Packer et al. | 2023 | 2310.08560 | Hierarchical memory tiers (session vs archival) inspired by OS memory management. |
| [7] | MemoryBank: Enhancing LLMs with Long-Term Memory | Zhong et al. | 2023/2024 | 2305.10250 | Ebbinghaus Forgetting Curve applied to memory decay. Justifies recency formula. |
| [8] | Conversational Agents with Time-Sensitive Long-term Memory | Alonso et al. | 2024 | 2406.00057 | Pure cosine retrieval fails on time-based queries. Motivates hybrid scoring. |
| [9] | RAG for LLMs: A Survey | Gao et al. | 2023 | 2312.10997 | Defines Naive/Advanced/Modular RAG. HELIX = Advanced RAG. |
| [10] | Agentic RAG: A Survey | Xiong et al. | 2025 | 2501.09136 | Bidirectional memory in agents. Justifies write-back architecture. |

### Cluster C — OS Middleware (Vedika's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [11] BASE | OS-Copilot: Towards Generalist Computer Agents | Wu et al. | 2024 | — | Generalist OS agent with sandboxed execution and HITL. HELIX extends with rollback. |
| [12] | Toolformer | Schick et al. | 2023 | 2302.04761 | LLMs decide when to invoke tools. Underpins intent→command mapping. |
| [13] | ReAct: Synergizing Reasoning and Acting | Yao et al. | 2023 | 2210.03629 | Reason-Act-Observe loop. Models HELIX middleware workflow. |
| [14] | ToolLLM | Qin et al. | 2023 | 2307.16789 | Structured API selection. Informs command template selection. |
| [15] | AgentBench | Liu et al. | 2023 | 2308.03688 | Benchmarks LLM agents on real OS tasks. Identifies failure modes HELIX solves. |

### Cluster D — Voice & Interaction (Varshitha's papers)

| Ref | Paper | Authors | Year | arXiv | Key Insight |
|---|---|---|---|---|---|
| [16] BASE | OS-Copilot (same as [11]) | Wu et al. | 2024 | — | OS interaction model. How HUD connects to execution layer. |
| [17] | Toolformer (same as [12]) | Schick et al. | 2023 | 2302.04761 | Tool invocation chains triggered from HUD input. |
| [18] | ReAct (same as [13]) | Yao et al. | 2023 | 2210.03629 | HUD feedback loop: user sees reasoning + observations per action step. |
| [19] | ToolLLM (same as [14]) | Qin et al. | 2023 | 2307.16789 | HUD intents matched to validated command templates. |
| [20] | AgentBench (same as [15]) | Liu et al. | 2023 | 2308.03688 | Failure modes HUD + HITL design solves. |

---

## 10. ORIGINAL CONTRIBUTIONS — DO NOT CONFUSE WITH EXISTING TOOLS

These are the parts Tanmay designed from scratch. When Claude Code touches these, do not simplify them away or replace them with off-the-shelf equivalents without discussion.

| Contribution | Owner | What It Does | What Existing Tool It Extends |
|---|---|---|---|
| Two-Pass Sequential Architecture | Tanmay | Pass 1 intent enriches context for Pass 2 PII detection | Presidio + spaCy (normally run independently) |
| SESSION_PII_MAP with Reversibility | Tanmay | Stores original PII values for local restoration in responses | Presidio (throws away originals) |
| Tiered Redaction Cascade | Tanmay | Regex → NER → Semantic LLM fallback with confidence thresholds | Presidio + spaCy (normally one-shot) |
| Confidence-Gated Clarification Loop | Tanmay | confidence < 0.65 → ask user before routing | Ollama/LLaMA (no built-in gate) |
| Risk-Scored HITL Trigger | Tanmay | Weighted formula determines if HITL fires | LangChain (provides agent loop only) |
| Cross-Encoder Re-ranking | Tanmay | Re-ranks ChromaDB top-5 before prompt injection | ChromaDB (returns cosine only) |
| PII Restorer on Response Path | Tanmay | Bidirectional PII control: sanitise in, restore out | Presidio (input only) |
| Recency-Weighted Retrieval Score | Yukta | cosine_sim × exp(−λ × days_old) | ChromaDB (cosine only) |
| Interaction Summarisation Strategy | Yukta | Privacy-safe summarisation before ChromaDB storage | ChromaDB (stores raw text) |
| Session vs Persistent Memory Separation | Yukta | Two collections, outcome-gated promotion | MemGPT (single archival store) |
| LRU + Relevance Hybrid Eviction | Yukta | (recency_rank × 0.4) + (retrieval_freq × 0.6) | ChromaDB (no built-in eviction) |
| Outcome-Gated Promotion Policy | Yukta | Only HITL-approved interactions enter persistent memory | MemGPT/MemoryBank (store everything) |
| Dual-Mode Async Input State Machine | Varshitha | Voice + text simultaneously, non-blocking | PyQt6 (no built-in AI state machine) |
| Prompt Intent Annotator | Varshitha | Metadata packet: modality + system state + language confidence | Whisper (transcript only) |
| Indian Accent Robustness Pipeline | Varshitha | Bandpass + noise gate + normalisation before Whisper | Whisper (raw audio) |
| Dynamic Intent-to-Command Mapping | Vedika | NL intent + entities → safe OS command string | subprocess (executes commands only) |
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
SESSION_COLLECTION=helix_session_memory
PERSISTENT_COLLECTION=helix_persistent_memory
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
| GPU | None required | NVIDIA RTX (any VRAM ≥ 6 GB) |
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
- **Ollama startup time** on CPU: 10–15 seconds cold load. Start as background service at boot.

---

## 13. PHASE 2 IMPLEMENTATION PRIORITY ORDER

Build in this order (each step unlocks the next):

1. **`utils/config.py`** — environment setup, all thresholds loaded
2. **`sentinel/pii_engine.py`** — most testable, most critical, most exam-ready
3. **`sentinel/session_pii_map.py`** — tiny but foundational
4. **`sentinel/sentinel_node.py`** — depends on pii_engine
5. **`memory/chroma_manager.py`** — Yukta's core, needed by re-prompting
6. **`memory/retrieval_engine.py`** + **`memory/reranker.py`** — Yukta + Tanmay
7. **`memory/reprompting.py`** — Tanmay, depends on reranker
8. **`orchestrator/risk_scorer.py`** — Tanmay, standalone
9. **`orchestrator/routing_rules.py`** — Tanmay, standalone
10. **`middleware/blocked_commands.py`** + **`middleware/risk_classifier.py`** — Vedika
11. **`middleware/rollback_stack.py`** — Vedika
12. **`middleware/command_mapper.py`** + **`middleware/os_middleware.py`** — Vedika
13. **`orchestrator/gemini_oracle.py`** — Tanmay, needs pii_engine
14. **`orchestrator/task_orchestrator.py`** — Tanmay, needs everything above
15. **`hitl/hitl_controller.py`** — Tanmay, needs orchestrator
16. **`hud/asr_pipeline.py`** — Varshitha
17. **`hud/state_machine.py`** — Varshitha
18. **`hud/voice_hud.py`** — Varshitha, needs ASR + state machine
19. **`hud/hitl_widget.py`** — Varshitha, needs hitl_controller
20. **`main.py`** — wires everything together

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
- Write 10 interactions → retrieve with known query → verify top-3 returned
- Test recency decay: old interactions should score lower
- Test eviction: add 1001 entries → verify lowest-score evicted

---

## 15. KNOWN CONSTRAINTS & DECISIONS

- **Do not use LLaMA 3 8B for the Sentinel Node** — too heavy for 16 GB RAM alongside other services. Use LLaMA 3.2 3B. Reserve 8B for future enhancement only if GPU is available.
- **Do not use `WidthType.PERCENTAGE`** in any docx output — breaks in Google Docs.
- **Gemini model**: use `gemini-1.5-flash`, NOT `gemini-1.5-pro`. Flash is fast enough for this use case and stays within free tier for development.
- **Whisper model**: use `tiny` for development, `base` for final demo if latency allows. Do not use `small` or larger — too slow on CPU.
- **ChromaDB**: use local persistent client (`chromadb.PersistentClient`), not the HTTP client. No server needed.
- **PyQt6 not PyQt5**: the report specifies PyQt6. If a library only supports PyQt5, use a compatibility shim.
- **No threading.Thread**: use QThread for all background work so PyQt6 event loop stays clean.
- **All regex patterns use raw strings**: `r"\b..."` not `"\b..."`.
- **SESSION_PII_MAP is cleared at the start of every new query**, not at session end, to prevent stale mappings from bleeding across unrelated queries.

---

## 16. PLAGIARISM ASSESSMENT

Closest existing project: **Open Interpreter** (~35-40% conceptual similarity). Key differences that make HELIX distinct:
- Open Interpreter has NO dedicated PII redaction layer
- Open Interpreter has NO hybrid local-cloud routing (local only)
- Open Interpreter has NO persistent offline memory (ChromaDB)
- Open Interpreter's "confirmation" is a simple y/n — not HELIX's risk-scored HITL with timeout policy
- Open Interpreter has NO SESSION_PII_MAP reversibility

HELIX's unique combination: PII-first + hybrid routing + offline memory + HITL risk scoring = no direct clone exists.

---

## 17. QUICK COMMANDS

```bash
# Install all Python dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# Start Ollama (keep running in background)
ollama serve &
ollama pull llama3.2:3b

# Run HELIX
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
col = client.get_collection('helix_persistent_memory')
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

## 19. MISSING FROM INITIAL DESIGN — ADDITIONS (PATCHED)

### 19.1 Query Intent Cache (NEW MODULE — `orchestrator/intent_cache.py`) — TANMAY

This module was explicitly recommended during architecture review but was missing from the initial spec. It sits **between the Sentinel Node and the Task Orchestrator**.

**Purpose**: Cache recent intent→route decisions. If the same intent pattern was seen recently with a known safe outcome, skip 2 full LLM calls (Sentinel re-classification + Orchestrator routing LLM). Significant latency reduction for repetitive OS tasks (e.g. "list my downloads" asked multiple times per session).

**Implementation**:
```python
import hashlib
import time
from collections import OrderedDict

class IntentCache:
    """
    Key   = (intent_type, hash(normalised_query_structure))
    Value = (route_target, risk_score, cached_at_timestamp)
    TTL   = 300 seconds (5 minutes) — stale after that
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
        """Call this after any HITL rejection — cached decisions may be wrong."""
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
    # Safe cached route — skip LLM routing call
    return RouteDecision(cached['route_target'], hitl_required=False, from_cache=True)

# After routing decision is made:
intent_cache.set(intent, query, route_target, risk_score)
```

**Add to project structure** under `orchestrator/intent_cache.py`.

---

### 19.2 Sequence Diagram — Known Bugs to Fix Before Phase 2 Presentation

These are the **5 architectural errors** identified in the existing HELIX sequence diagram during the design audit. Fix these in the diagram before any presentation or submission.

**Bug 1 — Memory-Augmented Re-prompting is missing from the sequence**
- Current diagram: `SentinelNode → sanitised_query → TaskOrchestrator` (direct jump)
- Correct flow: `SentinelNode → sanitised_query → MemoryManager (retrieve) → MemoryManager returns context → Re-prompting Module → enriched_prompt → TaskOrchestrator`
- Fix: Add MemoryManager and Re-prompting as explicit lifelines. Add `Retrieve Relevant Memory` call from SentinelNode to MemoryManager, `Memory Context` return arrow, `Enriched Query` arrow from Re-prompting to TaskOrchestrator.

**Bug 2 — No failure path in the sequence diagram**
- Current diagram: Only shows the happy path (Gemini responds → result returned)
- Required: Add an `alt` fragment for cloud failure:
  ```
  alt [Cloud Execution — Gemini Available]
      Send Sanitised Query → GeminiService
      AI Response ← GeminiService
  [Cloud Execution — Gemini Unavailable]
      Fallback to local Llama
      Local AI Response
  end
  ```
- When Gemini API is down or times out (10s timeout): re-route to local Llama with a degraded prompt. Log the failure. Show user: "Cloud unavailable — using local model (response may be less detailed)."

**Bug 3 — ChromaDB write-back path is missing from the sequence**
- Current diagram: After displaying response, the sequence ends. No write-back shown.
- Required: After `Display Response`, add an async dashed arrow: `HELIXHUD → MemoryManager: async write-back (outcome summary)`
- This is a dashed arrow (memory context flow) not a solid arrow (data flow), per the HLD legend.

**Bug 4 — Final Decision arrow goes to wrong component**
- Current diagram: `ApprovalManager → OSMiddleware: Final Decision`
- Correct: `ApprovalManager → TaskOrchestrator: Final Decision` — the orchestrator then decides whether to call OSMiddleware or abort.
- The orchestrator must receive the HITL decision because it may need to re-route a modified command, not just pass it to OSMiddleware.

**Bug 5 — Response-side PII check is missing**
- Current diagram: `GeminiService → TaskOrchestrator: AI Response` goes directly back with no processing.
- Required: Add a `PIIRedactionEngine: restore + validate` step between receiving the AI Response and returning it to HELIXHUD.
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
            prompt=f"[OFFLINE MODE — Limited capability]\n\n{sanitised_prompt}",
            options={"temperature": 0.3, "num_predict": 512}
        )
        return fallback_response['response'], False
```

**HUD display when fallback occurs**:
```
"⚠ Cloud unavailable — using local model. Response may be less detailed."
```

**Memory write-back when fallback**:
- Tag the interaction `{"cloud_used": False, "fallback": True}` in ChromaDB metadata.
- Do not promote fallback responses to persistent memory (lower quality).

---

### 19.4 Varshitha's Correct Research Papers (Cluster D — Voice & Interaction Systems)

The CLAUDE.md Cluster D section incorrectly lists the same papers as Cluster C. Cluster D is Varshitha's voice/HUD section and should reference the following papers (from the original document's reference list [16]–[20]):

| Ref | Paper | Authors | Year | arXiv / Venue | Key Insight | Relevance to HELIX |
|---|---|---|---|---|---|---|
| [16] BASE | OS-Copilot: Towards Generalist Computer Agents with Self-Improvement | Wu et al. | 2024 | arXiv preprint | Generalist OS agent with HUD-level interaction design, self-improving from feedback. | Base design for how the HELIX HUD connects to and triggers the execution layer. |
| [17] | WhisperX: Time-Accurate Speech Transcription with Forced Alignment | Bain et al. | 2023 | arXiv:2303.00747 | Extends Whisper with forced phoneme alignment for time-accurate word-level transcription. | Justifies Whisper as the ASR backbone. WhisperX's alignment technique informs HELIX's accent robustness pipeline. |
| [18] | Speech-to-Text Pipeline in Real Time on Edge | Vaidya et al. | 2023 | IEEE Conference | Real-time STT on edge devices with latency constraints similar to consumer laptops. | Validates feasibility of running Whisper tiny/base locally on consumer hardware within the 2-second latency target. |
| [19] | Efficient On-Device Wake Word Detection Using Tiny Transformers | Anonymous | 2024 | arXiv preprint | Ultra-lightweight transformer for always-on wake word detection without cloud dependency. | Informs the future enhancement of HELIX HUD with wake word activation ("Hey HELIX") before full ASR pipeline. |
| [20] | Attention Is All You Need | Vaswani et al. | 2017 | NeurIPS 2017 | Introduces the Transformer architecture — foundational to Whisper, LLaMA, and all Transformer-based models in HELIX. | Foundational reference for the entire model stack: Whisper ASR, LLaMA Sentinel Node, Gemini Cloud Oracle. |

**Varshitha's base paper is [16] OS-Copilot** — it describes the HUD-level interaction and how a generalist agent interfaces with the OS, which maps to how HELIX's Voice HUD triggers the full pipeline.

---

### 19.5 Corrected Complete Data Flow (Revised with All Fixes Applied)

This replaces Section 7 as the authoritative sequence. Differences from Section 7 are marked with ▶

```
1. User speaks or types
        ↓
2. [HUD] AudioCapture (QThread) → WhisperWorker → raw transcript
   ▶ Pre-processing: bandpass filter (300–3400 Hz) + noise gate + normalisation
        ↓
3. [HUD] TextNormaliser → PromptIntentAnnotator → AnnotatedQuery
   (Annotated with: modality, language confidence, system state)
        ↓
▶ 3b. [INTENT CACHE] Check cache for (intent, query_hash)
   → Cache HIT + risk_score ≤ 40: skip steps 4-8, use cached route (GOTO 9)
   → Cache MISS: continue to step 4
        ↓
4. [SENTINEL] Pass 1: LLaMA 3.2 3B intent classification
   → if confidence < 0.65: return ClarificationRequest to HUD (GOTO 1)
   → if confidence >= 0.65: continue
        ↓
5. [PII ENGINE] Tier 1 (Regex) → Tier 2 (Presidio+spaCy) → Tier 3 (LLaMA, if needed)
   → Build SESSION_PII_MAP (RAM only, never logged or persisted)
   → Output: sanitised_query (guaranteed zero-PII)
        ↓
6. [MEMORY] ChromaDB cosine search → top-5 results
   → Cross-encoder re-rank → top-2 snippets (Tanmay's addition)
   → Recency decay scoring: final_score = cosine_sim × exp(−0.1 × days_old)
   → Filter results with score < 0.65
        ↓
7. [RE-PROMPTING] Build enriched_prompt:
   system_instructions + memory_context + sanitised_query
   → Token budget check (max 2048 tokens, truncate old snippets first)
        ↓
8. [ORCHESTRATOR] Routing decision + risk score
   LOCAL (FILE_OP/SYSTEM_CMD conf≥0.80)  → GOTO 9a
   CLOUD (GENERAL_QA/UNKNOWN or conf<0.80) → GOTO 9b
   MEMORY (MEMORY_LOOKUP)                  → GOTO 9c
   → risk_score calculated → if > 40: HITL_REQUIRED = True
   ▶ Store route in IntentCache
        ↓
9a. [OS MIDDLEWARE]
    → Blocked pattern check → Resource-capped subprocess (CPU 5s, RAM 512MB)
    → ExecutionResult captured
    → RollbackStack.push(command, inverse_command)
    → ExecutionContextTracker.record(filesystem_diff)
    
9b. [GEMINI ORACLE]
    → PII assertion (assert no raw PII in payload — abort if detected)
    → API call with 10s timeout
    ▶ If Gemini unavailable: fallback to local Llama, tag as degraded
    → AI response received
    
9c. [CHROMADB] Direct semantic search → return result (skip to step 11)
        ↓
▶ 10. [PII RESTORER] (MISSING FROM ORIGINAL DIAGRAM — NOW EXPLICIT)
    → SESSION_PII_MAP.restore(response): replace placeholders with original values
    → Scan response for leaked raw PII (Gemini hallucination check)
    → Alert if placeholder mismatch detected
        ↓
11. if HITL_REQUIRED:
    [HITL CONTROLLER] → HITLDisplayData → [HUD] shows approval dialog
    Panel 1: Proposed action (human-readable)
    Panel 2: Risk level + colour (green/amber/red/dark red)
    Panel 3: Memory context (relevant past interactions)
    Panel 4: Approve / Reject / Modify buttons + countdown
    
    → APPROVED:
      ▶ [TASK ORCHESTRATOR receives Final Decision] (not OSMiddleware directly)
      → Execute (if not already executed in 9a) or confirm result
      → RollbackStack.clear()
      → Async write-back to ChromaDB persistent_memory
    
    → REJECTED:
      → RollbackStack.pop_and_execute() (undo partial steps)
      → Async write-back to ChromaDB session_memory only (not persistent)
      → IntentCache.invalidate(intent) (rejected routes should not be cached)
      → HUD: "Action cancelled."
    
    → MODIFIED:
      → Re-route modified_command from step 8 (full pipeline again)
        ↓
12. [HUD] Display final response to user
        ↓
▶ 13. [MEMORY] Async write-back (QThread — non-blocking)
    → Summarise interaction using LLaMA (privacy-safe, no PII)
    → Run PII check on summary before storage
    → Store in session_memory always
    → Store in persistent_memory ONLY IF hitl_approved=True AND not degraded (fallback)
    → Increment retrieval_count for any memories that were used
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
├── intent_cache.py          ← NEW: Query Intent Cache (Section 19.1)
│
sentinel/
├── pii_restorer.py          ← NEW: Explicit PII Restorer module (Section 19.2 Bug 5)
│
utils/
├── requirements.txt         ← at project root (Section 19.6)
├── fallback_handler.py      ← NEW: Gemini fallback logic (Section 19.3)
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

## 20. FULL PROJECT ASSESSMENT — GAPS AND IMPROVEMENTS (May 2025)

This section documents every gap, missing feature, and improvement identified after a complete audit of HELIX against the 2025-2026 state of the art in local AI agent systems. All items here are **additions to what is already specified in Sections 1–19**. Claude Code must implement everything in this section during Phase 2.

---

### 20.1 CRITICAL GAPS — Will cause crashes or major missing functionality if not fixed

---

#### GAP 1: No Streaming Responses (HIGHEST PRIORITY UX FIX)

**Problem**: Currently Ollama and Gemini calls are fully blocking. The HUD shows a spinner for 5–15 seconds with no feedback. This is the single worst UX issue in the project.

**Fix**: Stream tokens from both Ollama and Gemini directly to the HUD using Qt signals.

**Implementation — `hud/streaming_worker.py`** (Varshitha):
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

**Add to requirements.txt**: no new package needed — ollama SDK already supports streaming.

---

#### GAP 2: No Conversation Buffer (Multi-Turn Context)

**Problem**: If user says "delete that file" in a follow-up query, the system has no reference to what "that file" means. RAG retrieval gets past interactions but not the current conversation thread.

**New module — `memory/conversation_buffer.py`** (Yukta):
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
    Cleared on session end (not persisted — session-scoped only).
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
        'delete that' → look in last 3 user turns for file/path mentions.
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

#### GAP 3: No Pydantic Validation for Sentinel Output — Will Crash on Bad JSON

**Problem**: LLaMA 3.2 3B sometimes returns malformed JSON. Currently `json.loads()` will throw an exception and crash the pipeline.

**Fix — Use Ollama's native structured output + Pydantic validation with retry**:

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

#### GAP 4: No Health Check System — Crashes Silently on Missing Services

**New module — `utils/health_check.py`**:
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
        lines = ["HELIX Health Check:"]
        for name, result in self.checks.items():
            icon = "✓" if result["ok"] else "✗"
            lines.append(f"  {icon} {name}: {result['message']}")
        lines.append("" )
        lines.append("All systems ready." if self.all_ok else "FIX ERRORS ABOVE BEFORE STARTING HELIX.")
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

#### GAP 5: No Gemini Rate Limiter — Will Fail Under Testing Load

**Free tier limit**: 15 requests per minute, 1 million tokens per minute.

**New module — `orchestrator/rate_limiter.py`**:
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

# Singleton — import and use everywhere
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

#### GAP 6: No HELIX CLI Mode — Impossible to Test Without GUI

**New file — `helix_cli.py`** (run from project root):
```python
#!/usr/bin/env python3
"""
HELIX CLI Mode — headless pipeline for testing without PyQt6 GUI.
Usage: python helix_cli.py
       python helix_cli.py --query "list my downloads"
       python helix_cli.py --test   (runs built-in test suite)
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

    if verbose: print(f"\n[HELIX CLI] Query: {query}")

    # Pipeline
    sentinel_result = sentinel.process(query)
    if verbose: print(f"[SENTINEL] Intent: {sentinel_result.intent} (conf: {sentinel_result.confidence:.2f})")

    sanitised, n_pii = pii_engine.redact(query, sentinel_result)
    if verbose: print(f"[PII] Redacted {n_pii} entities. Sanitised: {sanitised}")

    enriched = reprompt.build(sanitised, sentinel_result)
    route = orchestrator.route(sentinel_result, enriched)
    if verbose: print(f"[ROUTE] → {route.target} | Risk: {route.risk_score}")

    response = orchestrator.execute(route, enriched)
    restored = pii_map.restore(response)
    if verbose: print(f"[RESPONSE] {restored}")

    return {"query": query, "intent": sentinel_result.intent, "response": restored, "n_pii": n_pii}

def interactive_mode():
    print("HELIX CLI — type 'exit' to quit, 'stats' for session stats")
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
    parser = argparse.ArgumentParser(description="HELIX CLI")
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

#### GAP 7: No Custom Exception Hierarchy — Error Handling Will Be Messy

**New file — `utils/exceptions.py`**:
```python
class HELIXBaseError(Exception):
    """Base class for all HELIX exceptions."""
    pass

class PIILeakageError(HELIXBaseError):
    """Raised when raw PII is detected in a cloud-bound payload."""
    pass

class SentinelError(HELIXBaseError):
    """Raised when Sentinel Node fails to classify after max retries."""
    pass

class MemoryWriteError(HELIXBaseError):
    """Raised when ChromaDB write-back fails."""
    pass

class RouteError(HELIXBaseError):
    """Raised when task orchestrator cannot determine a valid route."""
    pass

class HITLTimeoutError(HELIXBaseError):
    """Raised when HITL approval times out on a medium-risk action."""
    pass

class CommandBlockedError(HELIXBaseError):
    """Raised when OS middleware detects a blocked command pattern."""
    pass

class GeminiRateLimitError(HELIXBaseError):
    """Raised when Gemini rate limit is exhausted and fallback is unavailable."""
    pass

class OllamaUnavailableError(HELIXBaseError):
    """Raised when Ollama service is not running."""
    pass

class ChromaDBCorruptionError(HELIXBaseError):
    """Raised when ChromaDB data cannot be loaded (possible corruption)."""
    pass
```

---

#### GAP 8: Whisper Not Pre-Warmed — First Voice Command Unusably Slow

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
            fp16=False,            # CPU mode — no fp16
            initial_prompt="HELIX AI assistant. User is giving a command in English or Hinglish."
        )
```

The `initial_prompt` improves accuracy for Indian-accented English by priming Whisper's attention.

---

#### GAP 9: No ChromaDB WAL Mode — Risk of Data Corruption on Power Loss

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
    # Verify: the .chromadb directory should contain helix.sqlite3-wal
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

#### GAP 10: No Pydantic Models — Using @dataclass Throughout

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
    presidio_score: float  # 0.0–1.0

class RouteDecision(BaseModel):
    target: str            # "local" | "cloud" | "memory"
    risk_score: int        # 0–100
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

### 20.2 IMPROVEMENTS — Significantly Enhance HELIX's Value and Demo Impact

---

#### IMPROVEMENT 1: Privacy Metrics Dashboard (KILLER DEMO FEATURE)

This is the most visually impactful addition for any judge or panel. Shows exactly what HELIX is protecting in real time.

**New module — `utils/privacy_metrics.py`**:
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
┌─────────────────────────────┐
│  🔒 Privacy Score: 87%      │
│  ─────────────────────────  │
│  Queries: 15 total          │
│  Local:   13  ████████▓░░   │
│  Cloud:    2  ██░░░░░░░░    │
│  PII protected: 34 entities │
│  HITL: 3 approved, 1 reject │
└─────────────────────────────┘
```

Update this panel after every query using a QTimer or direct signal.

---

#### IMPROVEMENT 2: Structured Privacy-Respecting Audit Log

Logs WHAT happened (intent, route, outcome, risk) without logging the actual query content or any PII. Safe to review for debugging. Safe to show to panel.

**New module — `utils/audit_logger.py`**:
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
    def __init__(self, log_path: str = "./data/helix_audit.jsonl"):
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

When user closes HELIX, display a summary card before the window closes.

**In `voice_hud.py`** (Varshitha) — override `closeEvent`:
```python
def closeEvent(self, event):
    from utils.privacy_metrics import session_metrics
    summary = session_metrics.to_display_dict()
    msg = "\n".join([f"{k}: {v}" for k, v in summary.items()])
    dialog = QMessageBox(self)
    dialog.setWindowTitle("HELIX Session Summary")
    dialog.setText(f"Session complete.\n\n{msg}\n\nThank you for using HELIX.")
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

**In `utils/config.py`** — add model preference chain:
```python
# Model preference order — system tries each in order, uses first available
SENTINEL_MODEL_PREFERENCE = [
    "llama3.2:3b",       # Best balance — default
    "phi3.5",            # Microsoft Phi-3.5 Mini — fast, surprisingly capable
    "gemma2:2b",         # Google Gemma 2B — very lightweight
    "qwen2.5:3b",        # Alibaba Qwen 2.5 — good at structured tasks
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

**In `utils/config.py`** — add:
```python
# Options: "LOW" | "MEDIUM" | "HIGH"
# LOW    = Tier 1 (Regex) only. Fast, catches structured PII only.
# MEDIUM = Tier 1 + Tier 2 (Presidio+spaCy). Default. Good balance.
# HIGH   = All three tiers including Semantic LLM. Slowest, most thorough.
PII_SENSITIVITY = os.getenv("PII_SENSITIVITY", "MEDIUM")
```

**In `sentinel/pii_engine.py`** — use this to short-circuit the cascade:
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
        # Do NOT hardcode language — let Whisper detect it
        # This handles English, Hindi, and Hinglish automatically
        initial_prompt="HELIX AI assistant for local system management."
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

Add `language` and `language_confidence` to `AnnotatedQuery` Pydantic model. Pass to Sentinel Node — for non-English, add instruction to handle transliterated text.

---

### 20.3 UPDATED PROJECT STRUCTURE (adds all new modules)

Add these files to Section 5's folder structure:

```
helix/
├── helix_cli.py                           ← NEW: Headless CLI mode (GAP 6)
│
├── utils/
│   ├── exceptions.py                      ← NEW: Custom exception hierarchy (GAP 7)
│   ├── models.py                          ← NEW: All Pydantic data models (GAP 10)
│   ├── privacy_metrics.py                 ← NEW: Session privacy counters (IMPROVEMENT 1)
│   ├── audit_logger.py                    ← NEW: Privacy-respecting audit log (IMPROVEMENT 2)
│   └── health_check.py                    ← NEW: Service health checker (GAP 4)
│
├── orchestrator/
│   └── rate_limiter.py                    ← NEW: Gemini rate limiter (GAP 5)
│
├── memory/
│   └── conversation_buffer.py             ← NEW: Multi-turn context (GAP 2)
│
├── hud/
│   └── streaming_worker.py                ← NEW: Qt streaming workers (GAP 1)
│
└── data/
    ├── chromadb/                          ← ChromaDB persistence
    ├── backups/                           ← ChromaDB backups (GAP 9)
    └── helix_audit.jsonl                  ← Audit log (IMPROVEMENT 2)
```

---

### 20.4 UPDATED IMPLEMENTATION PRIORITY ORDER

Replace Section 13 with this corrected order that includes all new modules:

```
Phase 2 build order:

FOUNDATION (do these first — everything depends on them):
1.  utils/exceptions.py                 — custom exception hierarchy
2.  utils/models.py                     — all Pydantic data models
3.  utils/config.py                     — environment + model selection
4.  utils/health_check.py               — run this to verify environment
5.  utils/privacy_metrics.py            — session counters singleton
6.  utils/audit_logger.py               — audit log singleton

SENTINEL + PII (core logic):
7.  sentinel/session_pii_map.py         — SESSION_PII_MAP + PIIRestorer
8.  sentinel/pii_engine.py              — tiered PII cascade
9.  sentinel/sentinel_node.py           — Ollama structured output + retry
10. sentinel/pii_restorer.py            — response-side PII check

MEMORY (Yukta):
11. memory/conversation_buffer.py       — multi-turn context
12. memory/chroma_manager.py            — ChromaDB two-collection setup
13. memory/retrieval_engine.py          — cosine + recency scoring
14. memory/reranker.py                  — cross-encoder re-ranking
15. memory/reprompting.py               — prompt construction + token budget
16. memory/eviction_policy.py           — LRU + relevance eviction

ORCHESTRATION (Tanmay):
17. orchestrator/intent_cache.py        — query intent cache
18. orchestrator/rate_limiter.py        — Gemini rate limiter
19. orchestrator/risk_scorer.py         — risk score formula
20. orchestrator/routing_rules.py       — decision tree
21. orchestrator/gemini_oracle.py       — streaming + fallback
22. orchestrator/task_orchestrator.py   — LangChain ReAct agent

MIDDLEWARE (Vedika):
23. middleware/blocked_commands.py      — blocklist
24. middleware/risk_classifier.py       — command risk scoring
25. middleware/rollback_stack.py        — undo mechanism
26. middleware/command_mapper.py        — NL → OS command
27. middleware/os_middleware.py         — sandboxed execution + dry-run

HITL (Tanmay):
28. hitl/approval_states.py            — state enum
29. hitl/hitl_controller.py            — approval state machine

HUD (Varshitha):
30. hud/asr_pipeline.py                — Whisper pre-warmed + language detection
31. hud/streaming_worker.py            — Qt token streaming workers
32. hud/state_machine.py               — HUD state machine
33. hud/hitl_widget.py                 — approval dialog
34. hud/voice_hud.py                   — main window + privacy panel + command history

INTEGRATION:
35. helix_cli.py                        — headless test mode
36. main.py                             — health check → start HUD
```

---

### 20.5 UPDATED QUICK COMMANDS

```bash
# Health check (always run this first)
python -m utils.health_check

# CLI mode (no GUI — for testing)
python helix_cli.py
python helix_cli.py --query "list my downloads"

# GUI mode (full system)
python main.py

# Run specific module tests
python -m pytest tests/test_pii_engine.py -v
python -m pytest tests/test_sentinel.py -v
python -m pytest tests/test_memory.py -v
python -m pytest tests/ -v --tb=short

# View audit log
cat data/helix_audit.jsonl | python -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"

# View privacy metrics (from CLI mode 'stats' command)
python helix_cli.py  # then type 'stats'

# Backup ChromaDB manually
python -c "from memory.chroma_manager import backup_chromadb; backup_chromadb('./data/chromadb')"

# Check Ollama models available
ollama list

# Pull model if missing
ollama pull llama3.2:3b

# Check rate limiter status (in Python)
python -c "from orchestrator.rate_limiter import gemini_rate_limiter; print(f'Calls in window: {len(gemini_rate_limiter._calls)}')"
```

