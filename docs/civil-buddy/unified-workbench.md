# Rust unified workbench

This implementation records feature-specific evidence in the [acceptance record](architecture/implementation.md). It runs a Rust task host and a fixed Python domain service, with one model loop in Rust for new Agent tasks. Existing specialist, CAD and engineering surfaces remain available during migration.

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
- Document patches require matching original hashes, expected old values and a successful identical preview. The returned preview_id can apply the cached patch without asking the model to reproduce it. Added numbers need preserved original values, explicit user input or verified source quotations. Saved files remain model proposals.
- PDF body rewriting/OCR, Office visual rendering and spreadsheet formula recalculation are not provided by this worker. Results report these limitations explicitly.

The product's ordinary tests use scripted local models. `scripts/unified_acceptance.py --live` is separate opt-in acceptance against an already configured local server; it never reads or writes API keys.

## Engineering, speech and distribution

The Agent page lists saved CAD section and explicit frame projects from the domain service. That library is shared within this launched instance; registering a source workspace does not silently migrate or filter the existing project library. A turn authorizes up to four exact project revisions and input hashes. CAD requires a fresh entity/hole confirmation. The model can choose only an index, never supply geometry or solver inputs. Computation checks the project version before and after the worker; result cards preserve solver units, source revision and signed sampled extrema.

The fixed domain service also mounts the existing CAD, analysis, schedule, planning and routing pages. Planning/schedule records in the unified launcher use its state directory. These extra pages retain their deterministic services; they are not all registered as arbitrary model tools. IFC and planning remain on their own pages.

Speech uses a cancellable fixed process with an explicit prepare step for model download. Audio transcription produces editable text and never auto-submits. Missing faster-whisper/model assets are reported as unavailable. Browser speech fallback requires the existing explicit consent flow. The current acceptance environment did not exercise a real microphone or download a speech model.

Build a Windows source-plus-executable package after committing distribution sources:

```powershell
python scripts/build_unified_release.py --version 0.5.0-preview --binary workbench/target/release/civil-workbench.exe --output-dir dist
python scripts/build_unified_release.py --verify dist/civil-buddy-unified-workbench-0.5.0-preview-windows-x86_64.zip
```

Use the actual filename printed by the builder for verification. The package includes a supplied Windows executable and the allowlisted source/assets; Python and optional dependencies are installed separately in a local virtual environment. No provider credentials, personal project records or generated outputs are packaged. Each file and the archive have SHA-256 checksums.
