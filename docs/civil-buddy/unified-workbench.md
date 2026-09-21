# Rust unified workbench

This implementation is being verified against the [acceptance checklist](architecture/implementation.md). It runs a Rust task host and a fixed Python domain service, with one model loop in Rust for new Agent tasks. Existing specialist, CAD and engineering surfaces remain available during migration.

## Start locally

Install the project's Python dependencies plus `requirements-documents.txt` in a virtual environment. Engineering and local speech remain optional dependencies in their existing requirements files.

```powershell
cargo build --release --manifest-path workbench/Cargo.toml
python scripts/start_unified_workbench.py --python .venv/Scripts/python.exe --env-file demo/.env --open
```

The launcher binds both services to loopback, starts `/static/agent.html`, and stops both on Ctrl+C. `--state-root` isolates task history/domain records. `--binary` selects an already built executable. It refuses a second launcher using the same state directory. Source workspaces are opened explicitly in the page; only selected files enter a model task. New copies are saved beneath that workspace's `.civil-buddy/out`.

The default view offers a model-free structural check and a model task. Configure the model in the page or through environment variables. A model task with `read-only` cannot apply a document patch. `workspace-write` permits new draft copies; original files cannot be replaced.

## Provider configuration

```dotenv
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
JEV_MODE=off
# Optional: JEV_MODE=shadow or assist
# JEV_API_KEY=your-key
# JEV_ENDPOINT=https://api.typesafe.ai/v1/systemone
# JEV_MODEL=jev-latest
```

DeepSeek Chat Completions requests explicitly disable thinking for the initial tool-loop baseline, bound output tokens, preserve complete tool interactions, and record provider usage. See the [official DeepSeek API](https://api-docs.deepseek.com/api/create-chat-completion/). An explicit existing model setting is preserved.

Jev uses the [TypeSafe System One API](https://docs.typesafe.ai/introduction/quickstart). The host defines candidates/questions from selected evidence. Off makes no Jev calls; shadow records validated proposals; assist may schedule an additional read-only review when the fixed candidate and confidence gate pass. The initial 0.9 confidence threshold is an unevaluated product setting, not a claimed accuracy guarantee. Jev cannot permit a write, change solver numbers or approve an engineering conclusion. Engineering replan adapters beyond document review remain on the implementation checklist.

## Execution guarantees and limits

- Events persist before the page sees them. Refresh reconnects from the last sequence; restart marks unfinished tasks interrupted and never silently repeats writes.
- A task tree shares input/output/call budgets. At most two read-only children run together, four children in total, depth one; cancellation propagates.
- Context occupancy is a conservative serialized-byte estimate, separately shown from model billed usage and task stages. It never silently removes the current request or half a tool interaction.
- Fixed Python workers establish the requested OS sandbox before reading their request. The default `CIVIL_WORKER_SANDBOX=os` fails closed. Explicit `app` is a diagnostic/application-policy mode and must never be reported as OS isolation.
- On Windows, the existing Low Integrity/Job backend restricts writes/spawn. It does not claim kernel read or network confinement; the UI records the actual process probe.
- RAG uses selected-source SQLite FTS5/BM25 with original hashes and exact locators. Verification re-extracts the current original, not the derived index. This proves quotation identity, not engineering truth.
- Document patches require matching original hashes, expected old values and a successful identical preview. Added numbers need preserved original values, explicit user input or verified source quotations. Saved files remain model proposals.
- PDF body rewriting/OCR, Office visual rendering and spreadsheet formula recalculation are not provided by this worker. Results report these limitations explicitly.

The product's ordinary tests use scripted local models. `scripts/unified_acceptance.py --live` is separate opt-in acceptance against an already configured local server; it never reads or writes API keys.
