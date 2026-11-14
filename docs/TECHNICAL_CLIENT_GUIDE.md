# Priya Technical Client Guide

## Architecture, implementation, assurance, and delivery boundaries

**Audience:** technical clients, architects, engineering reviewers, deployment
owners, and stakeholders assessing what Priya does and what remains before
production acceptance.

**Assessment snapshot:** 14 November 2026.

**Application release marker:** `2026.11.14.3`.

**Delivery status:** locally verified, single-owner prototype with deployment
safeguards; not a certified or production-accepted service.

For implementation onboarding and support procedures, see the
[Developer Handbook](DEVELOPER_HANDBOOK.md). For commands, see the
[README](../README.md).
The [New Laptop Windows Guide](NEW_LAPTOP_WINDOWS.md) documents the separate
clean-clone/fresh-environment setup verification and private task migration.

---

## Contents

1. [Executive technical position](#1-executive-technical-position)
2. [Requirements and delivered scope](#2-requirements-and-delivered-scope)
3. [System architecture](#3-system-architecture)
4. [Technology choices and trade-offs](#4-technology-choices-and-trade-offs)
5. [End-to-end execution flows](#5-end-to-end-execution-flows)
6. [API contracts](#6-api-contracts)
7. [Persistence and state lifecycle](#7-persistence-and-state-lifecycle)
8. [AI behavior and answer assurance](#8-ai-behavior-and-answer-assurance)
9. [Access controls and privacy](#9-access-controls-and-privacy)
10. [Resource, concurrency, and performance boundaries](#10-resource-concurrency-and-performance-boundaries)
11. [Observability and development transparency](#11-observability-and-development-transparency)
12. [Deployment and operations](#12-deployment-and-operations)
13. [Verification evidence](#13-verification-evidence)
14. [Risks and production acceptance gates](#14-risks-and-production-acceptance-gates)
15. [Technical review questions and answers](#15-technical-review-questions-and-answers)
16. [Handover and acceptance checklist](#16-handover-and-acceptance-checklist)

## 1. Executive technical position

Priya provides browser-based conversation, optional voice input/output,
educational explanations, persistent tasks, in-app reminders, Wikipedia
research, prebuilt 3D illustrations, and developer visibility.

The principal engineering decision is to keep **business effects outside the
language model**. Supported actions execute through validated Python handlers.
The model produces explanation text; it is not entrusted with an unrestricted
tool loop, computer control, or authority to confirm operations.

Current suitability is a controlled demonstration, personal learning use,
and a foundation for a scoped pilot. Public service delivery still requires
target-environment validation, operational ownership, privacy decisions,
recovery testing, capacity measurement, and any required independent review.

There is no contracted SLA, guaranteed factual accuracy, multi-tenant
isolation, closed-browser reminder delivery, or verified physical AR/VR
experience in the current scope.

## 2. Requirements and delivered scope

| ID | Requirement | Delivered behavior | Boundary |
|---|---|---|---|
| R1 | Modernize the earlier voice assistant | Separate Flask web application with responsive chat | Desktop application remains separate |
| R2 | Priya branding and companion identity | Priya identity, Naveen companion context, fixed common identity replies | No authenticated per-user personalization profile |
| R3 | Typed and spoken input | Text input plus browser recording and server-local transcription | English tiny.en; permissions and recording limits apply |
| R4 | Gentle spoken replies | Online Indian-English gTTS audio at reduced browser rate/volume | External voice is not a selectable or guaranteed female model |
| R5 | Explain concepts | Ollama-generated explanations with short conversational context | Model can be wrong or ignore length/format instructions |
| R6 | Research with evidence | Wikipedia links/excerpts; optional excerpt-grounded generation | Not a general search engine or semantic fact checker |
| R7 | Execute reliable reminders/tasks | Validated deterministic task creation, SQLite commit before confirmation | Limited phrase grammar; no calendar/email integration |
| R8 | Preserve reminders | Server persistence and acknowledgement synchronized across pages | Open-page overdue alerts, not a background notification service |
| R9 | Handle overlapping requests | Visible five-message queue, Stop, retry and draft preservation | Queue is tab-local and not durable |
| R10 | Modern visual experience | Blue chat UI, animation, safe Markdown, WebGL scenes | Prebuilt illustrative geometry, not generated 3D assets |
| R11 | AR/VR pathway | Feature-detected WebXR session integration | Physical hardware acceptance is outstanding |
| R12 | Explain development/runtime behavior | Live monitor, maintained development notes, genuine test reports | No hidden model reasoning or automatic editor-action narration |
| R13 | Prepare web deployment | Container/Gunicorn configuration, authentication, quotas, persistent volume and health endpoints | Container/cloud execution not verified in this environment |

### Explicitly excluded capabilities

No wake word, always-on agent, arbitrary shell execution from chat, email
sending, inbox access, device control, full-document knowledge indexing,
multi-user account management, or physical hologram projection is implemented.
Optional YouTube audio preparation is disabled by default and requires
administrative configuration and authorized use.

## 3. System architecture

```text
                          USER DEVICE
                 +---------------------------+
                 | Browser                   |
                 | Chat, queue, short context|
                 | Microphone, MP3 playback  |
                 | Task view, WebGL, WebXR   |
                 | Developer monitor         |
                 +-------------+-------------+
                               |
                 Same-origin HTTP / HTTPS in production
                 JSON, binary audio, streamed NDJSON
                               |
                   PRIYA APPLICATION HOST
                 +-------------v-------------+
                 | Flask application         |
                 | Session / CSRF / quotas   |
                 | Validation and routing    |
                 | Explicit action handlers  |
                 +--+-----------+----------+--+
                    |           |          |
          +---------v--+  +-----v------+  +v----------------+
          | SQLite     |  | Local STT  |  | Ollama service  |
          | Task state |  | tiny.en    |  | Language model  |
          +------------+  +------------+  +-----------------+
                    |
          Bounded in-memory monitor + private verification report

              EXTERNAL SERVICES, WHEN FEATURES ARE USED
              Wikipedia / Google gTTS / YouTube
```

The Ollama service can run on the same host or a configured trusted network
endpoint. "Local AI" describes the configured processing location; in a hosted
deployment it does not mean computation occurs on each user's laptop.

### Component responsibilities

- **Browser:** user interaction, recording, rendering, local chat/queue state,
  audio playback, notification permissions, and graphics.
- **Flask:** API boundary, validation, action orchestration, access safeguards,
  dependency calls, and error responses.
- **SQLite:** authoritative single-owner task, completion, due-time, and
  acknowledgement state.
- **Ollama:** pretrained model serving, not application authorization.
- **faster-whisper:** recognition on the Priya host.
- **gTTS/Wikipedia/YouTube:** optional external dependencies with different
  availability and privacy implications.
- **Developer terminal:** runs tests; the browser reads reports but cannot
  launch terminal commands.

Reference implementation:
[web_app.py](../web_app.py), [assistant_services.py](../assistant_services.py),
[task_store.py](../task_store.py), [web_access.py](../web_access.py).

## 4. Technology choices and trade-offs

| Choice | Reason in this implementation | Trade-off |
|---|---|---|
| Flask/Python | Straightforward API boundary and reuse of Python assistant services | Synchronous external calls require bounded work and capacity planning |
| Plain JavaScript/HTML/CSS | Direct browser integration without a Node build toolchain | UI state must be managed explicitly and regression-tested |
| Ollama + `qwen2.5:1.5b` | Accessible local inference for a small prototype | Accuracy/instruction following and latency depend on model/hardware |
| faster-whisper `tiny.en` int8 CPU | Avoid failing browser recognition dependency; local recognition | Small English model has accuracy limits; provisioning/cold load required |
| Online gTTS | Working browser-playable audio without installed Windows voices | Internet/provider dependency; reply text leaves the Priya host |
| SQLite | Durable transactional state with low operational complexity | No tenant model, high-availability database, or proven large-scale write capacity |
| HTTP NDJSON streaming | Incremental reply delivery without WebSocket infrastructure | Client must validate terminal events; proxy buffering must be disabled |
| Markdown + bleach | Readable final output with an explicit HTML allowlist | Not a full rich-document or math-rendering system |
| Raw WebGL/WebXR | Browser-native prebuilt educational visuals and optional immersive sessions | Device/browser support varies; physical-device verification outstanding |
| Polling monitor/tasks | Simple bounded implementation without a realtime messaging service | Polling delay and browser scheduling affect freshness |
| One Gunicorn worker, four threads | Matches per-process locks, quotas, and memory-held monitoring | Not a horizontally scalable architecture without further changes |

No model training/fine-tuning, vector store, LangChain-style orchestration
framework, WebSocket server, or server background reminder scheduler is
required by this implementation.

## 5. End-to-end execution flows

### 5.1 Deterministic task request

Example: `Please remind me in two minutes to review the motor notes`.

1. Browser validates input and sends it with an action ID.
2. Server checks access, CSRF where configured, quotas, and payload shape.
3. Supported polite phrasing is normalized.
4. The reminder parser validates the duration and extracts the title.
5. The task store validates the record and commits it transactionally.
6. Only after commit does the server return a task-saved confirmation.
7. Connected pages refresh authoritative task state.
8. A due reminder remains overdue until acknowledgement or completion.

If storage fails, the response explicitly states that a save was not
confirmed. The language model is not used to fabricate success.

### 5.2 Open-ended learning request

1. Supported deterministic handlers run first.
2. History shape/roles/lengths are validated.
3. Optional grounding retrieves Wikipedia excerpts; failure is explicit.
4. A per-process AI semaphore admits or rejects generation as busy.
5. The server sends model instructions and bounded context to Ollama.
6. The browser receives draft tokens through NDJSON.
7. The server verifies generation completion and citation identifiers.
8. The browser receives final sanitized output or an explicit failure.
9. Completed AI responses update the short tab-local AI context.

### 5.3 Spoken interaction

1. User grants microphone permission in a secure context.
2. Browser records audio for up to 30 seconds.
3. Server validates/decode/transcribes with local tiny.en.
4. Recognized text enters the ordinary command/queue flow.
5. If Voice is enabled, reply text is sent to Google gTTS.
6. MP3 audio returns to the browser, which attempts playback.
7. Autoplay/decoding/service errors are presented separately.

Recognizing speech and playing a reply are independent operations. Successful
recognition or MP3 generation does not establish physical speaker audibility.

### 5.4 Cancellation and partial success

Stop cancels active browser work, clears queued messages, and marks partial
answers incomplete. Generator cleanup closes upstream consumption and
releases application locks. It is not a transactional rollback of an already
saved task, nor proof that external inference stopped instantly.

## 6. API contracts

All paths below are relative to the application origin. When password access
is configured, APIs require the authenticated session except `/healthz`.
State-changing requests additionally require CSRF validation. Optional
`/api/audio` also requires its separate download key.

| Method/path | Purpose | Important shape or result |
|---|---|---|
| `GET /` | Main UI | HTML with configuration flags, never download-key values |
| `GET /login` | Sign-in form | CSRF-bearing form when access is configured |
| `POST /login` | Password authentication | Form password + CSRF; redirect on success |
| `POST /logout` | Clear session | CSRF-protected when access is configured |
| `GET /api/session` | Refresh CSRF metadata | `{ "csrf_token": "..." }`; never log this value |
| `GET /healthz` | Process liveness | `{ "status": "ok" }`; not dependency readiness |
| `GET /api/status` | Task/model availability | `status`, `tasks`, `ai`, `transcription` |
| `GET /api/updates` | Maintained release notes | `kind`, `release`, `reply`, `html` |
| `POST /api/chat` | Route commands or generate | JSON reply or NDJSON stream |
| `POST /api/transcribe` | Recognize recording | Raw audio body -> `{ "text": "..." }` |
| `POST /api/speech` | Generate reply audio | `{ "text": "..." }` -> MP3 |
| `GET /api/tasks` | List tasks | `{ "tasks": [...] }` |
| `POST /api/tasks` | Create task | `{ "title": "...", "due": null, "id": "optional" }` -> 201 `{ "task": {...} }` |
| `POST /api/tasks/import` | Transactional legacy import | `{ "tasks": [...] }` -> authoritative task list |
| `PATCH /api/tasks/<task_id>` | Change task state | Nonempty subset of boolean `done`, `acknowledged` -> `{ "task": {...} }` |
| `DELETE /api/tasks/<task_id>` | Delete task | `{ "deleted": true }`; missing task -> 404 |
| `POST /api/audio` | Optional temporary audio | `X-Priya-Download-Key` plus `{ "song": "..." }` -> audio |
| `GET /api/monitor` | Read observability | `runtime`, `events`, `files`, `development`, `verification`, privacy metadata |

### Chat request

```json
{
  "message": "Explain voltage with sources",
  "history": [],
  "stream": true,
  "grounded": true,
  "action_id": "example-unique-action-id"
}
```

`message` is required. `history` defaults to an empty list. `stream` selects
the generation delivery style; deterministic handlers still return ordinary
JSON. `action_id` supports identified task/reminder creation rather than
turning the whole chat endpoint into an exactly-once transactional service.

Reply kinds include `text`, `time`, `link`, `graph`, `tasks`, `task_saved`,
`visual`, `sources`, `music`, `ask_song`, `updates`, and `ai`.
Feature-specific fields accompany the kind; clients must not assume every
reply is an AI paragraph.

### Streaming contract

Content type is `application/x-ndjson`. Each event ends with a newline.

```json
{"type":"sources","sources":[]}
{"type":"token","text":"An electric motor "}
{"type":"done","kind":"ai","reply":"Final answer","html":"<p>Final answer</p>","sources":[],"warning":null}
```

An `error` event contains an `error` message. The client must receive a valid
terminal `done` event and complete framing before accepting success. HTTP
200 only means stream setup succeeded. Truncated or interrupted output is
not added to AI history.

### Error interpretation

| Status | Typical meaning |
|---|---|
| 400 | Invalid message, unsupported recording MIME type, malformed task/history |
| 401 | Sign-in required or expired |
| 403 | CSRF failure or wrong optional audio key |
| 404 | Task not found |
| 413 | Request exceeds body limit |
| 422 | Recording silence/duration issue, unusable bounded output, or nonstreaming generation-length limit |
| 429 | Per-service busy limit or request quota; distinguish using the error text |
| 502 | External retrieval, speech, or audio-preparation failure |
| 503 | Unavailable/disabled service, transcription initialization issue, or storage/I/O failure |
| 504 | Optional audio preparation timeout |

These are application examples, not an exhaustive substitute for inspecting
the returned error contract and stream terminal events.

## 7. Persistence and state lifecycle

### Authoritative task schema

| Field | Type | Meaning |
|---|---|---|
| `id` | String primary key | Validated ID, normally UUID |
| `title` | String | Trimmed, 1-160 characters |
| `due` | UTC ISO timestamp or null | Optional timezone-aware due time |
| `done` | Boolean | Task completion |
| `acknowledged` | Boolean | Whether reminder was explicitly acknowledged |

SQLite stores booleans as integer fields; API responses expose booleans.
Connections are per operation, with transactions and a ten-second SQLite busy
timeout. SQL values are parameterized; the PATCH field names are restricted
to a fixed allowed set.

Creation with the same ID/title/due is idempotent and preserves existing
completion/acknowledgement state. A conflicting reuse of the ID is rejected.
Import is all-or-nothing for the validated batch. There is no owner/tenant
column, schema migration framework, or task title/due update endpoint.

### Storage location and retention

| Data | Current lifecycle |
|---|---|
| Tasks | Persistent SQLite in `PRIYA_DATA_DIR`; default user-home `.priya` |
| Chat/history | Current browser tab memory; no server chat archive |
| Message queue | Current tab memory only |
| Web recording | In-memory recognition pipeline; not deliberately saved as a recording file |
| Synthesized speech | In-memory server audio and browser playback objects |
| Optional downloaded audio | Temporary server directory, removed after content is read |
| Server monitor events | Last 200 in process memory; reset on restart |
| Browser monitor events | Last 80 in the tab; reset on page lifecycle |
| Test results | Latest private `verification.json` in the data directory |
| Phase notes | Maintained source JSON, packaged with the application |
| Portable task backup | Separate unencrypted ZIP, created explicitly with SQLite backup API; never committed |

Tasks are not encrypted at rest by the application. Browser/server memory,
hosting logs, backups, crash handling, external processors, and local-device
access need separate operational policies. There is no account-wide export,
retention management, or automated deletion-policy subsystem.

## 8. AI behavior and answer assurance

### What is controlled outside the model

- Supported command parsing and actual persistence.
- Common identity questions.
- Input/history limits and allowed history roles.
- Allowlisted website links and supported 3D scene names.
- Citation-number validation and labelled excerpt fallback.
- Generation truncation/missing-completion handling.
- Final HTML sanitization and explicit error responses.

### What remains probabilistic

- Factual correctness, completeness, and instructional quality.
- Adherence to requested answer length or bullet format.
- Correct interpretation of retrieved excerpts.
- Handling unfamiliar wording not matched by deterministic routes.

### Grounding is not fact certification

The source workflow retrieves Wikipedia search excerpts, not full pages or a
curated organization knowledge base. The model receives those excerpts with
instructions to treat them as untrusted reference data and cite them.

If no valid citations exist, or any reference number is out of range, the
application shows actual excerpts with a warning instead of retaining a
pretend sourced summary. Valid citation identifiers do not establish
sentence-level support, freshness, completeness, or freedom from bias.

### Model settings and evaluation

Default generation uses `qwen2.5:1.5b`, temperature 0.2, and prediction budget
500 tokens. Recognition uses pretrained `tiny.en`; no training or fine-tuning
was performed by this project.

Before client acceptance, agree an evaluation set for expected concepts,
unanswerable questions, unsupported actions, source use, accents/noise, and
untrusted input. Score answer correctness, refusal/action boundaries,
citation support, recognition accuracy, and latency independently.
No benchmark accuracy percentage is asserted by the current regression tests.

## 9. Access controls and privacy

### Implemented access controls

- Single shared-owner password, configured as a Werkzeug scrypt/PBKDF2 hash.
- Production startup refusal without required credentials.
- Stable session secret of at least 32 characters required for configured
  password access.
- Flask signed sessions; signing is not encryption.
- HttpOnly, SameSite Strict cookies; Secure in production.
- Eight-hour inactivity session lifetime and logout.
- CSRF checks on state-changing requests when authentication is configured.
- Same-origin frontend API requests and explicit expired-session handling.
- CSP, no-content-sniffing, same-origin referrer policy, and production HSTS.
- Application limits and per-service concurrency controls.

There is no SSO, MFA, individual accounts, RBAC, per-user storage isolation,
durable security audit trail, secrets rotation workflow, or independent
penetration-test certification in this delivery.

The current local development server remains passwordless unless configured.
Support for login must not be presented as evidence that the current local
instance already has a password.

### Data egress by feature

| Destination | Data involved | When |
|---|---|---|
| Priya application host | Typed input, history, task data, recordings | Normal browser interaction |
| Configured Ollama host | Prompt, bounded history, optional excerpts | AI explanation request |
| Wikipedia | Search topic/query | Research or grounded answer |
| Google gTTS | Spoken reply text | Voice-enabled synthesis |
| YouTube | Search/topic and ordinary service request metadata | Following search links or optional audio preparation |
| Model distribution services | Download requests and network metadata | Initial model provisioning |

The web recognition path does not intentionally send audio to a cloud STT
provider. The separate desktop entry point does use Google's recognition
service; web privacy statements must not be applied to that desktop workflow.

### Privacy responsibilities before a pilot

1. Agree permitted data classifications and external-service usage.
2. Disclose remote-host and speech-provider processing to end users.
3. Define log, backup, recording, and task retention/deletion expectations.
4. Protect volumes, host access, transport, and secret storage.
5. Review model/dependency licenses and optional audio rights/service terms.
6. Review whether monitoring/developer notes should be exposed in a particular
   client deployment; access currently follows application login.

These are deployment/privacy review requirements, not a declaration of
regulatory compliance.

## 10. Resource, concurrency, and performance boundaries

| Control | Current value/behavior |
|---|---|
| Ordinary body limit | 16 KiB |
| Recording body limit | 2 MiB |
| Chat message | 1-500 characters |
| Supplied history | At most six messages; each content at most 1,500 characters |
| Speech input | 1-4,000 characters |
| Task title/list | 1-160 characters; at most 100 tasks |
| Relative reminder | One second to 366 days |
| Browser waiting queue | Five messages |
| Recording duration | At most 30 seconds |
| Ollama request timeout | 120 seconds |
| Wikipedia timeout | 15 seconds |
| gTTS timeout setting | 15 seconds; not an end-to-end SLA |
| Optional audio | Song query at most 120 characters; ten minutes; 25 MiB; 90-second subprocess timeout |
| Per-service concurrency | One each for AI, transcription, synthesis, optional download per process |
| Login quota | Five POST attempts per five minutes per address/limiter identity |
| General request quota | 120/minute for requests subject to the access limiter |
| Combined expensive POST quota | 30/minute across chat, speech, transcription, optional audio |
| Container server | One worker, four threads, 180-second worker timeout |

Authentication checks precede the monitor's rate-limit exemption.
Static files and liveness bypass the normal access-limiter path; monitor
polling is excluded from normal request quotas. General limiting also applies
to ordinary non-API application requests handled by that middleware, not just
chat. Authenticated owner traffic shares its owner limiter bucket; anonymous
traffic uses the remote address.

Quotas, semaphores, and monitor state are process-local. They reset on restart
and are not distributed. Forwarded client-IP headers are deliberately not
trusted; anonymous users behind one proxy can share a bucket.

### Performance claims

Streaming improves perceived responsiveness; it does not speed up every
model computation. Cold model loading, CPU contention, network services, and
concurrent voice work influence results.

The development checks established functional streaming and cancellation,
not sustained throughput, percentile latency, maximum users, hardware sizing,
or an availability SLA. Those measurements belong on the proposed hosting
environment with representative workloads.

Adding workers is not a transparent scaling fix: it duplicates model memory,
locks, limits, and monitoring state. Multi-user/high-availability operation
requires an explicit architecture decision.

## 11. Observability and development transparency

The monitor has two user-facing views:

### Runtime activity

- Correlated request IDs and safe route templates.
- HTTP response/error counters and average setup time.
- Active streamed AI count.
- Routing, persisted-action, retrieval, transcription, speech, playback,
  first-token, completion/failure/cancellation stages.
- Browser events combined with bounded server events.

Setup time ends at the response/stream headers. Full model duration is
reported separately. HTTP-error counters and stream-failure events measure
different things; a stream can fail after HTTP 200.

### Development and tests

- Phase notes maintained by the developer.
- Actual unittest callback totals and latest outcome.
- Allowlisted file metadata changes detected since server startup.
- Explicit limitations and stale/disconnected state.

The panel polls every two seconds only when it and the document are visible.
No terminal execution endpoint is provided. Live reports are written
atomically, with bounded retries for transient Windows replacement locks.
Permanent failures surface rather than being marked as success.

A missing report means `not_run`. Interrupted reporting is not a pass; a
forcibly killed runner can leave a stale `running` record, so start time and
terminal evidence matter. Reports describe their run, not arbitrary later
source changes.

Source:
[app_monitor.py](../app_monitor.py),
[monitor frontend](../static/monitor.js),
[maintained evidence](../development_status.json).

## 12. Deployment and operations

### Supported delivery shape

The supplied [Dockerfile](../Dockerfile) targets a long-running Linux Python
container using Gunicorn. The frontend is served with the backend; static-only
hosting cannot run this application.

The image:

- Installs the web requirements and downloads tiny.en during build.
- Sets port 8080, production mode, and `/data` storage.
- Disables AI by default until a reachable Ollama service is provisioned.
- Runs one Gunicorn worker with four threads and a 180-second timeout.
- Defines a process liveness healthcheck.

It does not package or start Ollama, include a cloud account, configure TLS,
provide a persistent-volume service, or establish production readiness.
The runtime image also does not copy the repository test suite; run
verification in the development/CI source environment rather than assuming
the image contains a test workstation.

### Deployment prerequisites

| Area | Required decision/configuration |
|---|---|
| Hosting | Long-running container/Python service, target region, resource budget |
| Transport | HTTPS termination, correct public origin and cookie behavior |
| Reverse proxy | Disable response buffering for streams; align request/body/time limits |
| Authentication | Password hash and stable session secret via secret management |
| Storage | Private persistent volume for `/data`, ownership/permissions and capacity |
| Model service | Trusted Ollama route, provisioned model, private network exposure |
| Recognition | Model cache available to the runtime user |
| External access | Allowed Wikipedia/Google/YouTube connectivity according to policy |
| Operations | Restart policy, external uptime/error alerts, log retention and resource quotas |
| Recovery | Consistent SQLite backups, restore drill, rollback procedure |
| Release | Reviewed source version, dependency/model license review, change record |

In a container, `127.0.0.1:11434` refers to that container, not the operator's
laptop. An appropriate trusted network endpoint must be configured. Ollama
should not be directly exposed to the public internet.

The application has no repository-provided deployment automation or completed
container/cloud acceptance evidence in this snapshot. Python 3.11 and the
local Windows development setup were exercised; the Linux container still
requires validation.

### Health and support interpretation

- `/healthz`: process is responding, not proof that AI/storage/audio work.
- `/api/status`: checks task storage and Ollama model availability; recognition
  status describes model load state, not microphone hardware.
- Monitor: current bounded diagnostic view, not external incident monitoring.
- Application/access logs: request metadata and errors, not an intentional
  chat-body archive. Configure hosting/proxy logs separately.

## 13. Verification evidence

### Automated baseline

Latest recorded runner: `python -m app_monitor --test`.

Completed: **14 November 2026, 10:53 UTC**.

Result: **55/55 passed, 0 failed, 0 errors, 0 skipped**.

| Suite | Count | Evidence category |
|---|---:|---|
| [Web tests](../tests/test_web_app.py) | 34 | Command/validation/service contracts, persistence, streaming, sources, identity |
| [Access tests](../tests/test_access.py) | 4 | Authentication/CSRF/logout, cookie config, quotas, production configuration |
| [Monitor tests](../tests/test_monitor.py) | 4 | Safe correlation, bounded allowlist, reports, Windows lock handling |
| [Desktop tests](../tests/test_assistant.py) | 9 | Existing desktop dispatch/errors/cleanup |
| [Private task migration](../tests/test_priya_data.py) | 4 | Backup/restore fidelity, overwrite refusal, invalid/tampered archive rejection |

External-service responses and hardware are simulated in much of this suite.
It does not constitute a measured model-quality benchmark or complete
end-to-end production test.

The [Windows checks workflow](../.github/workflows/windows-checks.yml) also
reuses the setup script on clean GitHub-hosted Windows/Python 3.11 x64 runners
for pushes and pull requests to `main` or the Priya branch. Models are skipped;
no private credentials or hardware are required. Consult the commit-specific
[Actions result](https://github.com/NaveenDataNinja/Ai-voice-assistant/actions/workflows/windows-checks.yml),
not this recorded local baseline, to establish whether a later commit passed.
These are regression checks, not public-hosting or model-quality certification.

### Separately observed integration/browser behavior

- Real local Ollama token streaming and final formatted rendering.
- Stop with incomplete marker and cleanup to zero active AI streams.
- Recorded-fixture recognition and queueing while a reply was active.
- Queue retry retaining a separate unsent draft.
- Reminder persisted across a real application restart.
- Reminder visible in two tabs; acknowledgement synchronized.
- Real task create/update/delete with acceptance fixture cleanup.
- Real HTTP password login, cookie flags, CSRF enforcement, protected monitor,
  action request, and logout using temporary credentials.
- Monitor stages, actual run totals, allowlisted file-change detection,
  disconnect warning, and reconnect recovery.
- Mobile page at 390px without horizontal page overflow.
- Installed dependency consistency and tracked-change whitespace checks.
- Consistent private task snapshot restored and compared in isolation; current
  database untouched. This is not a target-host disaster-recovery drill.

These are development observations, not an automated browser suite or a
repeatable cloud certification pipeline. The actual HTTP authentication smoke
test did not terminate TLS; production Secure-cookie configuration was
covered separately by tests.

### Explicitly unverified

- Public DNS, HTTPS termination, provider routing and deployed streaming.
- Building/running the supplied Docker image.
- Physical microphone capture/speaker audibility and physical AR/VR.
- Sustained load, latency percentiles, maximum concurrency, and failover.
- Backup restore/rollback drill on the intended host.
- Independent security audit, regulatory/privacy certification.
- Formal client UAT, accessibility certification, and business acceptance.

## 14. Risks and production acceptance gates

| Priority | Risk/gap | Mitigation or acceptance gate |
|---|---|---|
| Before public access | Passwordless local mode accidentally exposed | Production configuration, startup checks, HTTPS and external access validation |
| Before client data | External speech/research processing and unencrypted tasks | Approved data classification, consent, storage/log/backup policy |
| Before operational reliance | No proven restore/uptime process | Backup/restore drill, external alerts, named operational owner |
| Before capacity promises | CPU models and process-local limits | Target-hardware load/latency tests and agreed resource budget |
| Before factual reliance | Small model hallucination and weak citation entailment | Domain evaluation, human review and clear usage exclusions |
| Before multi-user use | Shared-owner storage and authentication | Accounts/authorization/tenant design; not merely more server workers |
| Before reminder guarantees | Open-page scheduling only | Keep scope explicit or design a durable scheduler and permitted delivery channel |
| Before voice/hardware claims | Recognition and playback vary by device/room | Physical-device acceptance matrix with consented fixtures |
| Before immersive claims | Untested physical WebXR operation | Target-device tests, browser compatibility, safe UX and fallback |
| Before optional audio | Copyright/service terms and third-party changes | Rights review, explicit enablement, quotas and link-only fallback |
| Before audit claims | Bounded transient monitor is not durable audit | Separate protected logging/audit system with retention/redaction policy |

Future integrations, SSO, multi-tenancy, richer RAG, better voice providers,
generated 3D, and durable notifications are potential roadmap items. They
require separate scope, implementation, test evidence, and acceptance.

## 15. Technical review questions and answers

**Why does the design not let the model execute every requested action?**

Because permission, validation, actual side effects, and reliable confirmation
are application responsibilities. Language generation is not execution proof.

**Is this RAG?**

It has retrieval-assisted generation using Wikipedia excerpts. It is not the
full ingestion/indexing/vector-retrieval/access-control pipeline commonly
associated with an enterprise document RAG solution.

**Can it run without the internet?**

Some provisioned capabilities can: local inference, local recognition,
persistent tasks, and screen graphics. Google speech, Wikipedia, YouTube,
initial downloads, and remote client access can require connectivity.

**Does the server store conversation history?**

There is no application chat archive. Short AI context lives in the tab and is
sent with AI requests. Tasks are persistent. Logs/backups/providers have
separate policies and must not be implied to have zero retention.

**Can each client employee have isolated data?**

Not currently. The implemented model is a single shared owner. Individual
accounts and authorization must be designed before multi-user use.

**Can the client install a different model?**

Administrators can configure a provisioned Ollama model/URL. Functional,
accuracy, resource, and latency evaluation must be repeated; changing the
model name is not qualification.

**Does a valid citation prove correctness?**

No. It proves the reference number points to a retrieved item. Semantic
support and source quality still need evaluation.

**Are reminder notifications guaranteed after the browser is closed?**

No. Persistent tasks remain, but current alerts are open-page behavior.
Overdue reminders appear when the user returns.

**Does the app provide exactly-once actions?**

Identified task creation is idempotent for matching ID/title/due. There is no
general distributed exactly-once execution system.

**Can we scale by increasing Gunicorn workers?**

Not without reviewing duplicated limits/model memory, task access,
observability, authentication/session behavior, and capacity. Current
configuration intentionally uses one worker.

**Why does the monitor sometimes show HTTP 200 for a failed answer?**

The stream was accepted before generation finished. The terminal stream
event and `ai.failed` stage describe generation outcome.

**Is development progress fully automatic?**

No. Runtime events and unittest totals are automatic observations.
Development explanations and manual browser evidence are maintained notes.
File notices report allowlisted metadata changes since startup.

**Does the interface create physical holograms?**

No. It renders browser illustrations. Immersive viewing additionally needs
supported hardware and remains physically unverified.

**Is this ready for a production sign-off today?**

Not based on local regression evidence alone. The acceptance gates in this
guide must be agreed and verified on the intended environment.

## 16. Handover and acceptance checklist

Use this as a proposed review checklist, not a claim of completed sign-off.

| Acceptance item | Current evidence | Remaining decision or proof |
|---|---|---|
| Agreed functional scope | Implemented feature/boundary matrix | Client approves supported and excluded use cases |
| Reproducible source release | Application release marker and source files | Reviewed immutable source version and change approval |
| Regression baseline | 55 passing tests recorded | Rerun against the accepted source/environment |
| End-user flows | Local browser/integration checks | Client UAT on target devices |
| Voice quality | Indian-English configuration; fixtures | Human audibility/recognition acceptance in target conditions |
| AI answer quality | Guardrails and source fallbacks | Domain evaluation with agreed thresholds |
| Authentication | Local HTTP smoke and automated controls | Real HTTPS/proxy/session acceptance |
| Deployment | Container/runtime configuration supplied | Build/run and public routing verification |
| Persistence | SQLite restart/multi-tab evidence | Persistent-volume backup/restore and permissions drill |
| Monitoring | Local live stages and real test results | Hosting alerts, operational logging and incident ownership |
| Capacity | Bounded process-local implementation | Measured throughput/latency, agreed resource sizing |
| Privacy/security | Data-flow disclosure and safeguards | Client policy review and independent review as required |
| Accessibility/immersive | Responsive checks and feature detection | Required browser/accessibility/hardware certification |
| Operations | Runbook and documented boundaries | Named support owner, escalation, rollback and maintenance plan |

### Suggested technical review meeting

1. Confirm business use cases and non-goals.
2. Walk through browser/server/model/data boundaries.
3. Demonstrate a real saved action and a generated answer separately.
4. Inspect runtime monitoring and the timestamped regression result.
5. Discuss external data processing, access, persistence, and resource limits.
6. Agree production gates, evidence owners, and acceptance criteria.
7. Record future features separately from the accepted delivery.

The appropriate final statement is: **the prototype has a verified local
functional baseline and explicit boundaries; production acceptance depends
on the agreed target-environment gates.**
