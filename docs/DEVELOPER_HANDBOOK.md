# Priya Developer Handbook

## Development knowledge, support, and presentation guide

**Audience:** the developer who needs to understand, maintain, demonstrate, and
explain Priya to end users and clients.

**Snapshot:** 14 November 2026; application release marker `2026.11.14.3`.
This describes the current implementation, not a promise that every deployment
has these features configured. The latest recorded local regression run passed
**55 tests**, with zero failures, errors, or skips.

**Read alongside:** [Technical Client Guide](TECHNICAL_CLIENT_GUIDE.md) for
architecture review, API contracts, deployment gates, and acceptance discussions.
The [README](../README.md) remains the shorter setup reference.

---

## Contents

1. [What we built](#1-what-we-built)
2. [How to explain the product](#2-how-to-explain-the-product)
3. [Architecture and ownership](#3-architecture-and-ownership)
4. [A message from input to answer](#4-a-message-from-input-to-answer)
5. [Feature-by-feature development knowledge](#5-feature-by-feature-development-knowledge)
6. [Development journey and engineering lessons](#6-development-journey-and-engineering-lessons)
7. [Set up and run the project](#7-set-up-and-run-the-project)
8. [Configuration reference](#8-configuration-reference)
9. [How to make changes safely](#9-how-to-make-changes-safely)
10. [Testing and interpreting evidence](#10-testing-and-interpreting-evidence)
11. [Troubleshooting and support](#11-troubleshooting-and-support)
12. [Demonstration and explanation scripts](#12-demonstration-and-explanation-scripts)
13. [Questions you should be ready to answer](#13-questions-you-should-be-ready-to-answer)
14. [Next development stages](#14-next-development-stages)
15. [Glossary](#15-glossary)

## 1. What we built

Priya modernizes an earlier Zara/Python voice-assistant experiment into a
browser-based, single-owner learning and productivity assistant. The product
combines several independent capabilities:

| Capability | What actually happens |
|---|---|
| Learning conversation | A pretrained local language model generates explanations through Ollama. |
| Typed input | The browser sends a validated message to Flask. |
| Microphone input | The browser records audio; the Priya server transcribes it with a local English model. |
| Spoken replies | Google text-to-speech generates Indian-English MP3 audio, played in the user's browser. |
| Reliable tasks | Application code validates and saves tasks in SQLite before confirming success. |
| Reminders | Open pages display persistent overdue reminders until acknowledged or completed. |
| Research | Wikipedia supplies up to four search results with excerpts and real links. |
| Optional grounded answers | Wikipedia excerpts are supplied to the model; citation identifiers are checked. |
| 3D learning | Browser WebGL renders prebuilt educational scenes and an abstract avatar. |
| AR/VR integration | WebXR controls are exposed only when the browser reports compatible support. |
| Developer visibility | The monitor shows observable stages, file metadata changes, maintained notes, and real test results. |
| Deployment preparation | Container configuration, password access, CSRF, quotas, persistent storage, and health endpoints are included. |

### What we did not build

- An assistant that can do anything like a fictional Jarvis.
- A wake-word or always-listening background assistant.
- An email, inbox, calendar, operating-system, or connected-device agent.
- An AI-generated 3D asset pipeline or a physical holographic projector.
- A multi-user SaaS product with tenant isolation.
- A medical, financial, legal, industrial safety, or critical-reminder system.
- A custom-trained foundation model, vector database, or document-indexing RAG
  platform.
- A verified public production deployment.

These are scope boundaries, not features to imply during a demonstration.

## 2. How to explain the product

### Thirty-second end-user explanation

> Priya is a personal learning and productivity companion. You can type or
> speak, ask for explanations, look up Wikipedia starting points, save tasks,
> and explore simple 3D illustrations. Priya can read replies aloud when Voice
> is on. Tasks are saved, but chat context lasts only in the current tab.
> Important answers need checking, and reminders require returning to the app.

### One-minute technical explanation

> Priya uses a browser frontend and a Flask backend. Supported actions are
> handled by deterministic Python code rather than trusting a language model
> to claim success. Ollama handles open-ended explanations, faster-whisper
> handles server-local transcription, SQLite persists tasks, and Google gTTS
> supplies spoken replies. HTTP streaming improves perceived responsiveness.
> The system includes explicit failure states and an in-app monitor, but it
> remains a single-owner prototype requiring deployment hardening and
> environment-specific acceptance testing.

### The most important distinction

**Generating a sentence is not executing an action.**

If a model says "I will remind you," that sentence does not create a reminder.
The application must parse the request, validate it, commit the task, and only
then confirm it. This distinction explains much of the reliability work.

## 3. Architecture and ownership

```text
USER'S BROWSER
  Chat UI / microphone / audio playback / tasks / WebGL / monitor
          |
          | same-origin HTTP, JSON, audio, streamed NDJSON
          v
PRIYA FLASK SERVER
  Access checks -> validation -> deterministic routing or AI service
       |                |                |
       |                |                +-> Ollama model service
       |                +-> SQLite tasks
       +-> local faster-whisper transcription
       +-> Google gTTS / Wikipedia / optional YouTube download

DEVELOPER'S TERMINAL
  unittest runner -> private verification report -> monitor reads results
```

The browser uses the end user's microphone and speakers. The web server does
not capture its own microphone or play audio through its own speakers.

### Source map

| File or area | Responsibility | Read it when |
|---|---|---|
| [web_app.py](../web_app.py) | Flask endpoints, supported command routing, streaming lifecycle, speech/transcription, release notes, health | Understanding a complete web request |
| [action_router.py](../action_router.py) | Polite-phrase normalization, relative reminders, unsupported-action guard | Adding or diagnosing action phrases |
| [assistant_services.py](../assistant_services.py) | Identity replies, model messages, Ollama requests, Wikipedia retrieval | Changing model behavior or grounding |
| [task_store.py](../task_store.py) | Task validation, SQLite transactions, import and idempotent creation | Changing persistent task behavior |
| [web_access.py](../web_access.py) | Login, session, CSRF, limits, response headers, request logs | Diagnosing access or deployment configuration |
| [app_monitor.py](../app_monitor.py) | Bounded events, request IDs, file metadata scanning, live test reporting | Changing observable monitoring |
| [development_status.json](../development_status.json) | Developer-maintained phase status and evidence | Updating implementation notes truthfully |
| [templates/index.html](../templates/index.html) | Chat page, panel markup, script loading, CSRF metadata | Adding or changing controls |
| [templates/login.html](../templates/login.html) | Password sign-in page | Changing authentication presentation |
| [static/app.js](../static/app.js) | Chat, stream parsing, queue, Stop, voice, recording, browser history | Debugging frontend conversation state |
| [static/api.js](../static/api.js) | Shared fetch wrapper, CSRF retry, expired-session signal | Diagnosing cross-feature API failures |
| [static/tasks.js](../static/tasks.js) | Task UI, migration, reminders, shared panel opening | Debugging reminders or tool panels |
| [static/studio.js](../static/studio.js) | WebGL scenes, camera interaction, feature-detected WebXR | Changing illustrations or immersive mode |
| [static/monitor.js](../static/monitor.js) | Runtime/development views and visible-panel polling | Changing monitor presentation |
| [static/style.css](../static/style.css) | Layout, cards, chat bubbles, mobile and reduced-motion rules | Changing appearance |
| [web-requirements.txt](../web-requirements.txt) | Web/runtime dependencies | Preparing the web environment |
| [Dockerfile](../Dockerfile) | Linux image, model provisioning, Gunicorn, volume and healthcheck | Preparing deployment |
| [Windows setup](../setup.ps1), [start helper](../start.ps1), [version constraints](../requirements-windows-py311.lock.txt) | Per-clone Python environment, dependencies and model provisioning | Moving to another Windows laptop |
| [priya_data.py](../priya_data.py) | Consistent private task backup and non-overwriting restore | Moving task data separately from Git |
| [tests](../tests) | Desktop, web, access, and monitor regression tests | Verifying behavior before handover |
| [Desktop entry point](../Voice%20open%20and%20play%20in%20youtube%20code.py) | Separate command-line assistant | Maintaining the older desktop workflow |

The desktop application is not the web backend. Its microphone recognition
uses Google's recognition service and its speech configuration still uses UK
English. The current web application uses local transcription and
Indian-English speech. Do not mix their dependencies, privacy explanations,
commands, or voice behavior.

## 4. A message from input to answer

For a normal typed question:

1. The browser trims the input and enforces the 500-character limit.
2. If another answer is running, the message enters the visible queue rather
   than being discarded.
3. The shared API wrapper sends the message, bounded AI history, grounding
   choice, streaming choice, and a generated action ID.
4. The server applies access checks, request limits, body limits, and input
   validation.
5. Command normalization removes supported polite prefixes/suffixes and
   terminal punctuation.
6. Supported commands are handled before open-ended AI. A task request, for
   example, is committed to SQLite before the response is built.
7. Unsupported-action patterns receive explicit capability guidance. This is
   a bounded rule-based guard, not a perfect understanding of every phrase.
8. If no supported command applies, the server validates AI history and
   optionally fetches Wikipedia excerpts.
9. A semaphore admits one model generation at a time per process.
10. Ollama's incremental output is translated into application NDJSON events.
11. The browser displays draft text safely while tokens arrive.
12. On valid completion, sanitized Markdown replaces the draft. Only completed
    results of kind `ai` enter the short AI conversation history.
13. If Voice is enabled and no further queued reply needs processing, the
    browser requests speech and plays the returned MP3.
14. The next queued message runs after success. Failure instead leaves queued
    work available for an explicit retry.

The microphone path adds these steps before the normal message flow:

```text
Permission -> MediaRecorder -> recording blob -> /api/transcribe
  -> decode to 16 kHz samples -> local tiny.en transcription
  -> recognized text -> the same submit/queue/routing path
```

## 5. Feature-by-feature development knowledge

### 5.1 Identity and conversation

The configured identity is Priya, with Naveen as the companion. Common
questions such as "Who am I?" use fixed replies. The model also receives an
identity instruction, but fixed replies are stronger than hoping a small
model follows a prompt.

The default model is `qwen2.5:1.5b`. Requests use temperature `0.2` and a
500-token prediction limit. Temperature influences sampling; it is not an
accuracy guarantee. A token budget is not the same as a word count.

AI context contains at most six prior messages: approximately three user/AI
exchanges. Each supplied history item is limited to 1,500 characters.
Deterministic tool replies and evidence-only citation fallbacks are not a
general long-term memory system. New conversation and page reload clear the
in-memory chat context. Tasks remain because they are stored separately.

### 5.2 Local transcription and online speech

**Transcription** converts audio to text. **Speech synthesis** converts text
to audio. They are separate services with different failure modes.

| Item | Web implementation |
|---|---|
| Recording | Browser MediaRecorder; microphone permission required |
| Maximum recording | 30 seconds; 2 MiB request body |
| Accepted audio MIME types | WebM, Ogg, MP4, WAV |
| Decode target | 16,000 samples/second |
| Recognition model | faster-whisper `tiny.en`, CPU, int8 |
| Recognition settings | English, beam size 1, voice-activity filtering |
| Model provisioning | Download once on the target host; runtime uses local files only |
| Concurrency | One transcription at a time per process |
| Reply audio | gTTS, English, `tld="co.in"` |
| Playback | Rate 0.9 and volume 0.65; hidden player |
| Autoplay recovery | Small Enable audio control when the browser requires a click |

Int8 reduces model memory/compute requirements. Voice-activity detection helps
separate speech from silence. Neither guarantees accent or noisy-room accuracy.

The chosen web voice is Indian English. Do not promise a permanently fixed
female speaker: the external gTTS service controls the voice and does not
provide a gender selector here.

The application processes web recordings in memory rather than saving audio
files. Nevertheless, recordings reach the Priya host, and spoken reply text
reaches Google. Hosting infrastructure and external-service retention policies
must be considered separately.

### 5.3 Tasks and reminders

A task contains:

```json
{
  "id": "example-task",
  "title": "Review motor notes",
  "due": "2026-11-15T10:00:00+00:00",
  "done": false,
  "acknowledged": false
}
```

- IDs are validated; new IDs are normally UUIDs.
- Titles contain 1-160 nonblank characters.
- Due times must include a timezone and are normalized to UTC.
- The list is limited to 100 tasks.
- Creation/import is transactional.
- Reusing the same ID with the same title/due returns the existing task
  without resetting completion or acknowledgement.
- Reusing the ID for different title/due values is rejected.
- PATCH currently changes only completion and acknowledgement. Editing an
  existing title or due time is not implemented.

Relative reminders recognize patterns such as
`remind me in two minutes to drink water`, with seconds/minutes/hours/days
between one second and 366 days. This is not a general natural-language date
parser. For a specific date/time, create the reminder in the Tasks panel.

Acknowledgement means "I have seen this reminder"; completion means "I have
finished this task." They are intentionally separate.

The browser checks due state and refreshes server tasks every ten seconds
while visible. A hidden tab cannot consume a reminder by marking it notified.
Acknowledgement is saved on the server and synchronizes to other tabs on their
next refresh. There is no background server scheduler, email delivery, or
closed-browser push service.

Old browser tasks are imported once. The browser copy is deleted only after a
successful import; failed migration leaves it available for recovery.

### 5.4 Queue, cancellation, and recovery

- Five messages can wait in the browser queue.
- Microphone transcripts use the same queue.
- Queued messages have Send now and Cancel controls.
- Full queues retain the latest text in the input.
- Sending queued work must not erase a separate unsent input draft.
- A failed request stops automatic queue advancement.
- Stop uses AbortController, a generation marker, recording cancellation,
  audio cleanup, and queue clearing to prevent late results updating the chat.
- The server closes the upstream generator and releases the AI semaphore in
  cleanup paths.

Cancellation means Priya stops consuming/displaying the request and releases
its resources when the stream closes. It is not a guarantee of instantaneous
termination of all computation inside a separately running Ollama service.
Already committed tasks are not rolled back by pressing Stop afterward.

### 5.5 Streaming and formatting

The protocol is HTTP with newline-delimited JSON, **not WebSockets or SSE**.
Important event types are:

```json
{"type":"sources","sources":[]}
{"type":"token","text":"Voltage "}
{"type":"done","kind":"ai","reply":"Final answer","html":"<p>Final answer</p>","sources":[],"warning":null}
```

An error event can arrive after HTTP 200 has already been sent. Therefore,
HTTP success alone is not proof of a completed answer.

Draft output uses text rendering. Final Markdown goes through Markdown
conversion followed by an explicit bleach tag allowlist. Code, tables, lists,
and paragraphs are supported; arbitrary model-produced HTML is not trusted.
There is no LaTeX renderer.

An interrupted stream, missing completion event, or generation-length limit
produces an incomplete/error state. Partial answers do not enter AI history.

### 5.6 Research and grounding

`research solar energy` retrieves English Wikipedia results. It does not
perform a general internet crawl or claim to summarize every linked page.

For grounded AI explanations:

1. Enable the sources checkbox or append `with sources`.
2. Retrieve up to four Wikipedia search excerpts.
3. Treat those excerpts as reference data, not instructions.
4. Ask the model for numbered citations.
5. Validate citation numbers against the retrieved list.
6. If citations are missing or invalid, replace the draft with actual excerpts
   explicitly labelled as not a verified AI summary.

A valid `[1]` only proves that reference 1 exists. It does not prove that the
sentence is supported by that source. This is excerpt-assisted generation,
not full factual verification or a production enterprise RAG system.

### 5.7 3D, AR, and VR

The frontend creates sphere/ring/line geometry and renders it using WebGL
shaders and transformation matrices. Scenes are an abstract Priya avatar,
stylized atom, simplified water molecule, and simplified solar system.
Dragging changes rotation. Reduced-motion preferences are considered.

WebXR adds feature detection, session requests, per-eye/view rendering, and
session cleanup. Compatible hardware, browser permissions, and a secure
context are needed. Physical AR/VR operation has not been verified.

Explain this as **interactive screen-based illustration with optional
immersive integration**, not generated holograms, accurate simulation, or
arbitrary 3D model creation from a prompt.

### 5.8 Websites, graphs, and music

Supported websites are allowlisted links. Returning "Open Google" does not
mean Priya controlled another browser tab. The user follows the link.

The graph command displays a fixed sample of x squared, not arbitrary
data-driven plotting.

Music normally returns a YouTube search link. Optional server-side audio:

- Is disabled unless an administrator configures a private download key.
- Uses yt-dlp with a controlled subprocess argument list.
- Allows one preparation at a time, with 90-second timeout, ten-minute
  duration and 25 MiB output bounds.
- Uses a temporary directory and removes server files after reading the audio.
- Is limited to content the user is authorized to download and use.

The download key protects that optional endpoint, not the whole application.
Do not present it as a substitute for password access.

### 5.9 Access and deployment safeguards

Local development binds to loopback and stays passwordless without configured
credentials. Production mode requires a Werkzeug password hash and a stable
session secret of at least 32 characters.

Configured access includes password login, signed cookie sessions, HttpOnly
and SameSite Strict cookies, secure cookies in production, CSRF validation,
eight-hour inactivity lifetime, logout, request limits, and security headers.
The shared browser API wrapper handles expiry and can refresh a changed CSRF
token after re-login in another tab without discarding the draft.

These controls are preparation for private single-owner deployment. They are
not SSO, role-based access, tenant isolation, independent security certification,
or a public-hosting SLA.

### 5.10 Release notes and live development visibility

Three different kinds of evidence must stay separate:

| View | Origin | Meaning |
|---|---|---|
| What's new | Maintained release constants in the server | Shipped feature description, not a live trace |
| Runtime monitor | Instrumented server/browser events | Observable execution stages and outcomes |
| Development notes | Developer-maintained JSON | Human-maintained progress and browser-test evidence |
| Automated verification | Actual unittest result callbacks | Real test totals and current/latest run status |
| File notices | Allowlisted file size/mtime comparison | Changes detected since server startup |

The visible monitor polls every two seconds. It holds up to 200 server events
and 80 browser events, displaying the newest 100 merged entries. Server
history and counters reset on restart.

Request IDs connect browser responses to server stages. Setup time measures
time to response or stream headers; `ai.completed`, `ai.failed`, and
`ai.cancelled` report full model-stream duration. A quick setup measurement is
not a quick completed AI answer.

The monitor deliberately excludes prompts, replies, transcripts, recordings,
tokens/secrets, source contents, and absolute paths. Ordinary server access
logs can contain paths and other request metadata; hosting logs need their
own retention policy. The monitor is not a hidden-reasoning display, an
automatic explanation of every editor action, a Git diff viewer, or durable
production telemetry.

## 6. Development journey and engineering lessons

This is a development narrative, not a reconstructed commit-by-commit history.

| Problem or requirement | What changed | Engineering lesson |
|---|---|---|
| Older desktop-only assistant | Added a separate web server and responsive browser UI | Browser deployments need client/server ownership boundaries |
| Zara renamed to Priya; role confusion | Branding, prompts, and deterministic identity replies | Critical identity behavior should not depend solely on generation |
| Silent browser UK voice | Replaced dependence on installed voices with online reply audio | A voice selector does not prove a usable voice exists |
| Softer voice requested | Chose web Indian English, rate 0.9, volume 0.65; removed playback clutter | Validate the actual playback path, not only synthesis |
| Browser speech recognition returned a network failure | Added browser recording plus server-local faster-whisper | Recognition and reply audio must be diagnosed independently |
| Spoken punctuation missed a local command | Normalized terminal punctuation before routing | Voice transcripts require the same command semantics as typing |
| Model promised reminders without saving them | Deterministic parsing and save-before-confirm | Tool execution must be verified outside the model |
| Refresh/restart lost browser-only task state | SQLite persistence and cautious legacy import | Durable state belongs in managed server storage |
| Hidden tab consumed an alert | Persistent acknowledgement instead of one-time notification flags | "Displayed somewhere" is not "seen by the user" |
| Busy chat discarded microphone input | Visible queue and controlled retry | Concurrent inputs need explicit state management |
| Queue delivery erased an unsent draft | Clear the input only when sending that matching nonqueued input | Automated work must preserve unrelated user edits |
| Slow answers and raw Markdown | Streamed text, Stop, final sanitized formatting | Perceived responsiveness and correctness need separate handling |
| Model omitted/invented references | Validate IDs and show labelled retrieved excerpts instead | Evidence fallback must not look like a verified generated answer |
| Public-hosting concerns | Access controls, quotas, health/status, persistent-volume configuration | "Has a Dockerfile" is not "production verified" |
| Developer could not see what happened | Runtime stages, maintained progress, real test reporting | Observability should show evidence rather than invented narration |
| Windows report replacement failed during live reading | Bounded PermissionError retries around atomic replacement | Verify concurrency on the actual operating system |

## 7. Set up and run the project

Use the project root as the working directory. Commands below are PowerShell.
Python 3.11 was the locally tested runtime; do not infer certification of all
other Python versions.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r web-requirements.txt
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
```

Install/start Ollama separately and provision the default model:

```powershell
ollama pull qwen2.5:1.5b
```

Then run:

```powershell
.\.venv\Scripts\python.exe web_app.py
```

Default address: `http://127.0.0.1:5000`. The development session used
`http://127.0.0.1:18755`; that is an environment choice, not a fixed product port.

To select that port yourself:

```powershell
$env:PORT = "18755"
.\.venv\Scripts\python.exe web_app.py
```

If a managed Windows certificate store is needed after a certificate failure:

```powershell
.\.venv\Scripts\python.exe -m pip --use-feature=truststore install -r web-requirements.txt
```

Use the enterprise certificate policy; do not disable certificate validation.

For the full desktop-plus-web regression suite, install the desktop manifest
as well:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app_monitor --test
```

The Flask development server is not the public production server. Follow
[deployment instructions](../README.md#deploy-the-web-app) for the container
and hosting prerequisites.

## 8. Configuration reference

Set environment variables before starting the process. Imports capture some
configuration, so changing a variable after startup is not sufficient.

| Variable | Default or behavior | Developer responsibility |
|---|---|---|
| `PORT` | Local 5000; image 8080 | Match the actual listener and hosting port |
| `PRIYA_ENV` | Local mode unless set; image sets `production` | Never expose passwordless local mode publicly |
| `PRIYA_PASSWORD_HASH` | Unset locally | Use Werkzeug scrypt/PBKDF2, never plaintext |
| `PRIYA_SESSION_SECRET` | Ephemeral local fallback without configured login | Supply a stable, private value of at least 32 characters for configured login |
| `PRIYA_DATA_DIR` | User-home `.priya`; image `/data` | Use private persistent storage; back it up |
| `PRIYA_AI_ENABLED` | Enabled locally; disabled in image | Enable only with a provisioned, reachable model service |
| `PRIYA_OLLAMA_MODEL` | `qwen2.5:1.5b` | Pull the selected model and retest its behavior |
| `PRIYA_OLLAMA_URL` | `http://127.0.0.1:11434` | Use a trusted service reachable from the Priya host/container |
| `PRIYA_DOWNLOAD_KEY` | Unset; optional audio disabled | Keep secret, restrict use, review rights and resource needs |

Do not commit passwords, hashes intended for a live deployment, session
secrets, download keys, private recordings, or real user data. The current
local development instance has not been password-protected merely because
the application supports authentication.

## 9. How to make changes safely

### Add a supported action

1. Define the allowed input, required permission, side effect, and truthful
   confirmation. Decide what cancellation and retries mean.
2. Reuse normalization and validation instead of writing a second parser.
3. Place the supported handler before the unsupported-action guard and
   open-ended AI fallback.
4. Validate/execute in server code; never give arbitrary generated text shell
   or device privileges.
5. Confirm success only after the actual operation commits.
6. Add failure, invalid-input, and retry/idempotency tests relevant to the action.
7. Instrument fixed non-sensitive stages.
8. Update help/release notes and both handover documents where behavior changes.

### Change the model or source behavior

- Test the target model on the real host, including cold start.
- Keep identity/action guarantees outside probabilistic generation.
- Preserve bounded history and validation.
- Check truncation, absent completion, malformed response, and citation fallback.
- Evaluate factual quality and latency separately; unit tests with mocked
  responses do not establish model quality.

### Change frontend behavior

- Use the shared API wrapper for CSRF/session handling.
- Preserve the queue, unsent draft, Stop, and generation-marker invariants.
- Use text rendering for untrusted strings; only insert server-sanitized
  final answer HTML.
- Keep new controls usable on mobile and with reduced motion.
- Use the existing panel events rather than introducing a second panel manager.
- Check visible error feedback, not only console output.

### Update development evidence

Edit phase notes only when supported by actual work. Run
`python -m app_monitor --test` to publish real tests; never manually replace
counts with a claimed pass. Keep the runner and app on the same
`PRIYA_DATA_DIR`. Python changes require restart; static changes need refresh.
The two handbook files are not currently in the monitor's explicit file
allowlist; do not expect them to be automatically listed there. The setup,
migration helper, migration tests and new-laptop guide are allowlisted.

## 10. Testing and interpreting evidence

### Recorded baseline

The latest recorded local run completed on **14 November 2026 at 10:37 UTC**
using the live-reporting runner:

| Suite | Tests | Main coverage |
|---|---:|---|
| [Web application](../tests/test_web_app.py) | 34 | Commands, limits, speech/transcription contracts, storage, streaming, sources, identity |
| [Access](../tests/test_access.py) | 4 | Login/CSRF/logout, cookie settings, login and expensive-request limits, production configuration |
| [Monitor](../tests/test_monitor.py) | 4 | Correlation/privacy, allowlist/bounds, malformed/missing reports, transient/permanent report locks |
| [Desktop regression](../tests/test_assistant.py) | 9 | Command dispatch, service/device error handling, download cleanup |
| [Private task migration](../tests/test_priya_data.py) | 4 | Snapshot/restore fidelity, overwrite refusal, corruption/unexpected entry rejection, incompatible input |
| **Total** | **55** | **55 passed; 0 failed; 0 errors; 0 skipped** |

The regression suite predominantly simulates external services and devices.
Separately performed integration/browser checks included real Ollama
streaming, formatted completion, Stop cleanup, recorded-fixture recognition,
queued input and draft preservation, reminder restart/multi-tab behavior,
task CRUD, monitor reconnect behavior, mobile layout at 390px, and a real HTTP
login/CSRF/logout smoke test using temporary credentials.

The actual HTTP smoke test was local HTTP, not an end-to-end TLS deployment.
Secure-cookie settings were tested separately. Physical microphone/speaker
audibility, physical AR/VR, Docker execution, cloud hosting, load capacity,
target-host disaster-recovery restoration, and independent security review
are not established by these results. The separate private task snapshot
was restored and compared in an isolated temporary database without
changing current data.

### Commands

```powershell
# Full suite, publishing genuine results for the monitor:
.\.venv\Scripts\python.exe -m app_monitor --test

# Small relevant suite during development:
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_monitor.py -v

# Installed dependency consistency:
.\.venv\Scripts\python.exe -m pip check

# Whitespace issues in tracked changes:
git --no-pager diff --check
```

The targeted unittest command does not publish a new live monitor report.
A passing report proves that particular run, not all later edits.

### Release-check checklist

- [ ] Supported actions execute and failures do not claim success.
- [ ] Tasks survive refresh/restart and synchronize acknowledgement.
- [ ] Voice permission, silence, service failure, and autoplay cases are explicit.
- [ ] Queue success/failure/full behavior preserves drafts.
- [ ] Stop marks partial output incomplete and another AI request can run.
- [ ] Sources, valid/invalid citations, and generation truncation are handled.
- [ ] Login/expiry/CSRF/logout work under the intended hosting scheme.
- [ ] Runtime and test-report monitoring remain truthful while polling.
- [ ] Target browser/mobile/hardware checks are recorded, not assumed.
- [ ] Deployment changes have host-specific validation and rollback evidence.

## 11. Troubleshooting and support

Collect the time, page origin, visible symptom, monitor stage/request ID, and
relevant status. Avoid requesting passwords or sensitive conversation text.

| Symptom | Likely layer | First checks and honest recovery |
|---|---|---|
| Failed to fetch | Browser/server connectivity | Check the exact host/port, server process, `/healthz`, HTTPS/proxy path. Do not call it a model failure without evidence. |
| Server alive but AI unavailable | Ollama dependency | Inspect `/api/status`, Ollama reachability, model name, and configuration on the server host. |
| Typed commands work but microphone fails | Permission/recording/transcription | Confirm secure context and permission, installed tiny.en cache, accepted recording, model load; offer typing. |
| Text appears but no voice | Speech generation or playback | Confirm Voice on, internet, speech HTTP result, browser mute/output device, Enable audio. Browser playback events do not prove physical audibility. |
| First answer or recording is slow | Model initialization/resources | Separate cold start, time to first token, and total completion; do not invent an SLA. |
| Reminder appears late | Browser scheduling/polling | Check due timezone and browser clock, visible tab, polling. No closed-browser alert is promised. |
| Reminder still visible | Acknowledgement/completion | Explain the difference, save the chosen action, and allow other tabs to refresh. |
| "Saved" not confirmed | Validation/storage | Inspect status and storage error; check private data-directory permissions/capacity. Do not claim a save based on generated text. |
| Request returns 429 | Busy semaphore or quota | Read the specific message and Retry-After if supplied. Wait or retry; do not disable controls for a demo. |
| Session expired/CSRF rejected | Authentication state | Sign in again as instructed; preserve draft. Check stable secret and HTTPS/cookie setup. |
| Raw text becomes formatted only at end | Normal streaming behavior | Draft is text; sanitized formatting is applied after valid completion. |
| Evidence excerpts instead of AI summary | Citation validation | Explain the fallback and open the real sources; do not relabel it as verified reasoning. |
| Monitor says Not live | Monitor fetch failure | Displayed data may be stale; restore connectivity/authentication before interpreting it as current. |
| Verification says not_run | No report in this data directory | Run the live-reporting command with the same `PRIYA_DATA_DIR` as the app. |
| Verification remains running/interrupted | Runner stopped or publishing failed | Check terminal/start time and permissions; fix the cause and rerun. Never manually mark it passed. |
| AR/VR controls absent | Hardware/browser feature detection | Use normal 3D; absence on unsupported hardware is expected. |

For task backup, use SQLite's backup facilities or a controlled stop-and-copy
procedure, then test restoration in a separate environment. Copying an active
database without a consistency plan is not a validated backup strategy.
Do not delete the data directory as a troubleshooting shortcut.

## 12. Demonstration and explanation scripts

### End-user demo: approximately five minutes

1. Explain supported scope and the privacy difference between recognition and
   spoken replies.
2. Ask "Who am I?" and "What time is it?" Show predictable local behavior.
3. Ask "Explain an electric motor." Show the blue chat experience and streaming.
4. Ask "remind me in one minute to review the demo notes." Show the saved task.
5. Open 3D studio and rotate a model; call it an illustration.
6. Demonstrate acknowledgement after the reminder becomes due.
7. If audio is appropriate and permissions are granted, demonstrate Voice;
   never claim a physical device test from automation alone.
8. Delete the demonstration task when finished.

### Technical-client demo: approximately ten minutes

1. Draw browser -> Flask -> action/store/model boundaries.
2. Contrast a deterministic task commit with a generated explanation.
3. Show optional sources and explain citation-ID checks versus factual proof.
4. Start a reply, queue another message, and press Stop.
5. Open Runtime activity; explain request IDs and setup versus total duration.
6. Open Development & tests; show the genuine latest run and its time.
7. Explain single-owner access and privacy/deployment boundaries.
8. Present the explicit unverified items and agree acceptance criteria before
   discussing production sign-off.

### Explaining a failure professionally

> The browser reached Priya, but the model dependency was unavailable. The app
> reported that failure rather than inventing an answer or confirming work.
> Here is the request stage and status. I will restore the dependency, retry,
> and verify the actual outcome before calling this resolved.

## 13. Questions you should be ready to answer

**Did you train the AI?**

No. The project integrates pretrained models and adds orchestration,
validation, prompts, state management, persistence, and user experience.

**Is this an autonomous agent?**

Not an unrestricted one. It is a bounded assistant with application-controlled
actions and a model fallback for explanations.

**Is it fully offline?**

No. Provisioned local AI, local recognition, tasks, and illustrations can work
without internet dependencies, but Google speech, Wikipedia, YouTube, initial
model downloads, and remote access paths may require connectivity.

**Does local AI mean no information leaves the device?**

No. It runs on the configured Priya/Ollama host, which may be a remote server.
Sources send topics to Wikipedia; Voice sends reply text to Google.

**Can it send email or control machines?**

Not currently. An integration would require explicit permissions, safe
execution, confirmations, audit, tests, and client approval.

**Are tasks available on another device?**

Devices using the same server share its single-owner task list. Chat context
is not synchronized. This is not isolated accounts for different users.

**Does Acknowledge complete the task?**

No. It dismisses the pending reminder state. Completion is separate.

**Why not just ask the language model to do everything?**

Because generating plausible words does not establish a saved task, a sent
email, an accurate citation, or a completed operation.

**Does the monitor show the AI's thoughts?**

No. It shows observable application stages. Development explanations are
maintained notes, while test totals come from actual runner callbacks.

**Do 55 passing tests mean production ready?**

No. They establish the recorded regression run. Target hosting, TLS,
performance, security, recovery, privacy, and physical-device acceptance still
need evidence.

## 14. Next development stages

These are proposed, not implemented commitments.

1. **Production gate:** choose a host, validate TLS/proxy streaming, configure
   secrets and storage, exercise backup/restore, add external alerts and
   hosting resource controls.
2. **Quality gate:** maintain representative questions, accents/noise samples
   with permission, and factual/citation evaluations; measure latency on target
   hardware before changing models.
3. **Product gate:** agree whether authentication stays single-owner or needs
   accounts, tenant isolation, audit, deletion/export, and collaboration.
4. **Integration gate:** add approved email/calendar/device capabilities one
   at a time, with permission boundaries and real execution confirmation.
5. **Knowledge gate:** consider document ingestion and retrieval only after
   defining source authorization, provenance, updating, evaluation, and retention.
6. **Immersive gate:** test chosen AR/VR hardware before promising a supported
   immersive experience.

## 15. Glossary

| Term | Meaning in this project |
|---|---|
| LLM | Language model used to generate explanations |
| Ollama | Service that loads and runs the selected local language model |
| STT / transcription | Audio-to-text recognition |
| TTS / synthesis | Text-to-audio generation |
| VAD | Voice-activity detection used during recognition |
| Quantization / int8 | Lower-precision computation used for the recognition model |
| Deterministic routing | Explicit application rules selecting supported handlers |
| Grounding | Supplying retrieved reference material to generation |
| Hallucination | Plausible but unsupported generated content |
| NDJSON | One JSON object per line, used here for streamed responses |
| Semaphore | Limit on concurrent work for a service in one process |
| Idempotency | Repeating the same identified operation without duplicating its effect |
| CSRF | Cross-site request forgery; token validation helps protect state changes |
| Sanitization | Removing unapproved HTML before displaying generated formatting |
| WebGL / WebXR | Browser graphics / immersive-device APIs |
| Liveness / readiness | Process is responding / required dependencies are available |
| Observability | Evidence of application execution, not hidden model reasoning |
| SLA | Contracted service-level commitment; none is established by local tests |
