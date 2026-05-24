---
name: langsmith-trace
description: "INVOKE THIS SKILL when working with LangSmith tracing OR querying traces. Covers adding tracing to applications and querying/exporting trace data. Uses the langsmith CLI tool."
---

<oneliner>
Two main topics: **adding tracing** to your application, and **querying traces** for debugging and analysis. Python and Javascript implementations are both supported.
</oneliner>

<setup>
Environment Variables

```bash
LANGSMITH_API_KEY=lsv2_pt_your_api_key_here          # REQUIRED
LANGSMITH_PROJECT=your-project-name                   # Optional: default project
LANGSMITH_WORKSPACE_ID=your-workspace-id              # Optional: for org-scoped keys
LANGSMITH_TRACING=true                                # Enable tracing (LangChain/LangGraph)
```

**FreightHero repo:** credentials live in the repo-root `.env` (copy from `.env.example`). This project uses `LANGSMITH_*` names; some docs still mention legacy `LANGCHAIN_API_KEY` / `LANGCHAIN_PROJECT` — treat them as aliases for the same values.

Authentication is REQUIRED: either set the `LANGSMITH_API_KEY` environment variable, or pass the `--api-key` flag to CLI commands (preferred):
```bash
langsmith trace list --project my-project --api-key $LANGSMITH_API_KEY
```

**IMPORTANT:** Always load `.env` and read `LANGSMITH_PROJECT` before querying LangSmith. If the project name is missing, run `langsmith project list --api-key $LANGSMITH_API_KEY` and pick the project with recent runs.

### Load credentials from `.env` (do this first)

Agents do **not** inherit shell env from the IDE. Before any `langsmith` command, load the repo-root `.env` into the current shell session.

**Bash / macOS / Linux / WSL** (from repository root):
```bash
set -a
source .env
set +a
# Verify without printing secrets:
test -n "$LANGSMITH_API_KEY" && echo "LANGSMITH_PROJECT=${LANGSMITH_PROJECT:-unset}"
```

**PowerShell** (from repository root; tested on Windows):
```powershell
Get-Content .env | ForEach-Object {
  $line = $_.Trim()
  if ($line -and -not $line.StartsWith('#') -and $line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
    $val = $matches[2].Trim().Trim('"').Trim("'")
    Set-Item -Path "env:$($matches[1])" -Value $val
  }
}
# Verify without printing secrets:
"LANGSMITH_PROJECT=$env:LANGSMITH_PROJECT"; "API_KEY_SET=$([bool]$env:LANGSMITH_API_KEY)"
```

**Python fallback** (cross-platform; use when shell sourcing is awkward):
```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); import os; assert os.environ.get('LANGSMITH_API_KEY'), 'LANGSMITH_API_KEY missing in .env'"
```

Map legacy LangChain names if only those are set:
```bash
export LANGSMITH_API_KEY="${LANGSMITH_API_KEY:-$LANGCHAIN_API_KEY}"
export LANGSMITH_PROJECT="${LANGSMITH_PROJECT:-$LANGCHAIN_PROJECT}"
```

Smoke test after loading `.env`:
```bash
langsmith project list --api-key "$LANGSMITH_API_KEY"
langsmith trace list --project "$LANGSMITH_PROJECT" --limit 3 --api-key "$LANGSMITH_API_KEY"
```

### CLI Tool

Install the **Go `langsmith` binary** (commands in this skill use `langsmith trace …` / `langsmith run …`):

```bash
# macOS / Linux
curl -fsSL https://cli.langsmith.com/install.sh | sh

# Windows (PowerShell)
irm https://cli.langsmith.com/install.ps1 | iex
# Then for the current session:
$env:PATH = "$env:LOCALAPPDATA\Programs\langsmith\bin;$env:PATH"
```

Alternative: `uv tool install langsmith-cli` installs a **different** Python CLI (`langsmith-cli runs list`, not `langsmith trace list`). Prefer the Go binary when following this skill.
</setup>

<trace_langchain_oss>
For LangChain/LangGraph apps, tracing is automatic. Just set environment variables:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<your-api-key>
export OPENAI_API_KEY=<your-openai-api-key>  # or your LLM provider's key
```

Optional variables:
- `LANGSMITH_PROJECT` - specify project name (defaults to "default")
- `LANGCHAIN_CALLBACKS_BACKGROUND=false` - use for serverless to ensure traces complete before function exit (Python)
</trace_langchain_oss>

<trace_other_frameworks>
For non-LangChain apps, if the framework has native OpenTelemetry support, use LangSmith's OpenTelemetry integration.

If the app is NOT using a framework, or using one without automatic OTel support, use the traceable decorator/wrapper and wrap your LLM client.

<python>
Use @traceable decorator and wrap_openai() for automatic tracing.
```python
from langsmith import traceable
from langsmith.wrappers import wrap_openai
from openai import OpenAI

client = wrap_openai(OpenAI())

@traceable
def my_llm_pipeline(question: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": question}],
    )
    return resp.choices[0].message.content

# Nested tracing example
@traceable
def rag_pipeline(question: str) -> str:
    docs = retrieve_docs(question)
    return generate_answer(question, docs)

@traceable(name="retrieve_docs")
def retrieve_docs(query: str) -> list[str]:
    return docs

@traceable(name="generate_answer")
def generate_answer(question: str, docs: list[str]) -> str:
    return client.chat.completions.create(...)
```
</python>

<typescript>
Use traceable() wrapper and wrapOpenAI() for automatic tracing.
```typescript
import { traceable } from "langsmith/traceable";
import { wrapOpenAI } from "langsmith/wrappers";
import OpenAI from "openai";

const client = wrapOpenAI(new OpenAI());

const myLlmPipeline = traceable(async (question: string): Promise<string> => {
  const resp = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: question }],
  });
  return resp.choices[0].message.content || "";
}, { name: "my_llm_pipeline" });

// Nested tracing example
const retrieveDocs = traceable(async (query: string): Promise<string[]> => {
  return docs;
}, { name: "retrieve_docs" });

const generateAnswer = traceable(async (question: string, docs: string[]): Promise<string> => {
  const resp = await client.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [{ role: "user", content: `${question}\nContext: ${docs.join("\n")}` }],
  });
  return resp.choices[0].message.content || "";
}, { name: "generate_answer" });

const ragPipeline = traceable(async (question: string): Promise<string> => {
  const docs = await retrieveDocs(question);
  return await generateAnswer(question, docs);
}, { name: "rag_pipeline" });
```
</typescript>

Best Practices:
- **Apply traceable to all nested functions** you want visible in LangSmith
- **Wrapped clients auto-trace all calls** — `wrap_openai()`/`wrapOpenAI()` records every LLM call
- **Name your traces** for easier filtering
- **Add metadata** for searchability
</trace_other_frameworks>

<traces_vs_runs>
Use the `langsmith` CLI to query trace data.

**Understanding the difference is critical:**

- **Trace** = A complete execution tree (root run + all child runs). A trace represents one full agent invocation with all its LLM calls, tool calls, and nested operations.
- **Run** = A single node in the tree (one LLM call, one tool call, etc.)

**Generally, query traces first** — they provide complete context and preserve hierarchy needed for trajectory analysis and dataset generation.
</traces_vs_runs>

<command_structure>
Two command groups with consistent behavior:

```
langsmith
├── trace (operations on trace trees - USE THIS FIRST)
│   ├── list    - List traces (filters apply to root run)
│   ├── get     - Get single trace with full hierarchy
│   └── export  - Export traces to JSONL files (one file per trace)
│
├── run (operations on individual runs - for specific analysis)
│   ├── list    - List runs (flat, filters apply to any run)
│   ├── get     - Get single run
│   └── export  - Export runs to single JSONL file (flat)
│
├── dataset (dataset operations)
│   ├── list    - List datasets
│   ├── get     - Get dataset details
│   ├── create  - Create empty dataset
│   ├── delete  - Delete dataset
│   ├── export  - Export dataset to file
│   └── upload  - Upload local JSON as dataset
│
├── example (example operations)
│   ├── list    - List examples in a dataset
│   ├── create  - Add example to a dataset
│   └── delete  - Delete an example
│
├── evaluator (evaluator operations)
│   ├── list    - List evaluators
│   ├── upload  - Upload evaluator
│   └── delete  - Delete evaluator
│
├── experiment (experiment operations)
│   ├── list    - List experiments
│   └── get     - Get experiment results
│
├── thread (thread operations)
│   ├── list    - List conversation threads
│   └── get     - Get thread details
│
└── project (project operations)
    └── list    - List tracing projects
```

**Key differences:**

| | `traces *` | `runs *` |
|---|---|---|
| Filters apply to | Root run only | Any matching run |
| `--run-type` | Not available | Available |
| Returns | Full hierarchy | Flat list |
| Export output | Directory (one file/trace) | Single file |
</command_structure>

<querying_traces>
Query traces using the `langsmith` CLI. Commands are language-agnostic.

```bash
# List recent traces (most common operation)
langsmith trace list --limit 10 --project my-project --api-key $LANGSMITH_API_KEY

# List traces with metadata (timing, tokens, costs)
langsmith trace list --limit 10 --include-metadata --api-key $LANGSMITH_API_KEY

# Filter traces by time
langsmith trace list --last-n-minutes 60 --api-key $LANGSMITH_API_KEY
langsmith trace list --since 2025-01-20T10:00:00Z --api-key $LANGSMITH_API_KEY

# Get specific trace with full hierarchy
langsmith trace get <trace-id> --api-key $LANGSMITH_API_KEY

# List traces and show hierarchy inline
langsmith trace list --limit 5 --show-hierarchy --api-key $LANGSMITH_API_KEY

# Export traces to JSONL (one file per trace, includes all runs)
langsmith trace export ./traces --limit 20 --full --api-key $LANGSMITH_API_KEY

# Filter traces by performance
langsmith trace list --min-latency 5.0 --limit 10 --api-key $LANGSMITH_API_KEY    # Slow traces (>= 5s)
langsmith trace list --error --last-n-minutes 60 --api-key $LANGSMITH_API_KEY     # Failed traces

# List specific run types (flat list)
langsmith run list --run-type llm --limit 20 --api-key $LANGSMITH_API_KEY
```
</querying_traces>

<filters>
All commands support these filters (all AND together):

**Basic filters:**
- `--trace-ids abc,def` - Filter to specific traces
- `--limit N` - Max results
- `--project NAME` - Project name
- `--last-n-minutes N` - Time filter
- `--since TIMESTAMP` - Time filter (ISO format)
- `--error / --no-error` - Error status
- `--name PATTERN` - Name contains (case-insensitive)

**Performance filters:**
- `--min-latency SECONDS` - Minimum latency (e.g., `5` for >= 5s)
- `--max-latency SECONDS` - Maximum latency
- `--min-tokens N` - Minimum total tokens
- `--tags tag1,tag2` - Has any of these tags

**Advanced filter:**
- `--filter QUERY` - Raw LangSmith filter query for complex cases (feedback, metadata, etc.)

```bash
# Filter traces by feedback score using raw LangSmith query
langsmith trace list --filter 'and(eq(feedback_key, "correctness"), gte(feedback_score, 0.8))' --api-key $LANGSMITH_API_KEY
```
</filters>

<export_format>
Export creates `.jsonl` files (one run per line) with these fields:
```json
{"run_id": "...", "trace_id": "...", "name": "...", "run_type": "...", "parent_run_id": "...", "inputs": {...}, "outputs": {...}}
```

Use `--include-io` or `--full` to include inputs/outputs (required for dataset generation).
</export_format>

<tips>
- **Start with traces** — they provide complete context needed for trajectory and dataset generation
- Use `traces export --full` for bulk data destined for datasets
- Always specify `--project` to avoid mixing data from different projects
- Use `/tmp` for temporary exports
- Include `--include-metadata` for performance/cost analysis
- Stitch files: `cat ./traces/*.jsonl > all.jsonl`
</tips>
