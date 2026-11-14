# Priya Voice Assistant

Priya is a personal assistant prototype with a local AI learning companion,
Wikipedia research, persistent tasks, and interactive 3D illustrations. It
also tells the time, opens websites, and finds music on YouTube. It does not
have a wake word, unrestricted computer control, or connected-device control.
Priya's local AI is configured to recognize its companion as Naveen.
Common identity questions use fixed replies to prevent the small model from
confusing Naveen's role with Priya's.

## Share the correct version

Share this **[Priya next-version link](https://github.com/NaveenDataNinja/Ai-voice-assistant/tree/priya-v2-windows-portable)**,
not the repository's default page: `main` still contains the original version.
GitHub can list the same branch under both **Your branches** and **Active
branches**; these are categories, not duplicate branches or applications.
Do not delete a branch to remove a repeated category listing.

Use the web setup below as the maintained application. The earlier experimental
scripts are retained for learning/history and are not alternative web versions.
Source sharing does not host a public application or transfer your private data.

## New laptop: clone Priya's next version

For Windows x64 with Python 3.11, start with the
[New Laptop Windows Guide](docs/NEW_LAPTOP_WINDOWS.md). It covers cloning the
`priya-v2-windows-portable` review branch, prerequisites, setup/start scripts,
tested dependency constraints, model provisioning, and private task migration.
Virtual environments, model caches, credentials and real task data are not
stored in Git. Hardware permissions and online-service connectivity still
need verification on the new laptop.

```powershell
git clone --branch priya-v2-windows-portable --single-branch https://github.com/NaveenDataNinja/Ai-voice-assistant.git
Set-Location -LiteralPath ".\Ai-voice-assistant"
powershell -NoProfile -File .\setup.ps1
powershell -NoProfile -File .\start.ps1
```

Install Python 3.11 x64 and start Ollama first. Restore a separately transferred
private task backup before the first app start if you want your existing tasks.
Local setup does not deploy the app publicly or enable a password automatically.

## Detailed project documentation

- [Developer Handbook](docs/DEVELOPER_HANDBOOK.md): implementation knowledge,
  development history, setup, safe changes, testing, troubleshooting, and
  explanations for end users and clients.
- [Technical Client Guide](docs/TECHNICAL_CLIENT_GUIDE.md): architecture, API
  contracts, data/privacy boundaries, safeguards, verification evidence,
  deployment requirements, risks, and acceptance criteria.

Both describe the current implementation and distinguish verified local
behavior from proposed features and unverified production/hardware work.

## Web app: run locally

The web version provides a responsive chat interface, typed commands, optional
microphone input and spoken replies. Its server is separate from the desktop
assistant; it does not use a microphone or speakers on the server.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r web-requirements.txt
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
.\.venv\Scripts\python.exe web_app.py
```

Open `http://127.0.0.1:5000` in your browser. The Flask server above is for
local development only. Microphone input requires microphone permission and
HTTPS when deployed (localhost works for development). Click the microphone,
speak, then click it again to send; recording stops automatically at 30 seconds.
Recordings (maximum 2 MB) are sent to **your Priya server**, decoded in memory,
and transcribed locally using faster-whisper's `tiny.en` CPU model. They are not
saved or sent to a cloud transcription service. The setup command above
downloads the model once from Hugging Face; recognition then works offline.
Run it on each deployment host before serving microphone requests; the Docker
image already downloads the model during its build.
The first transcription loads the model and may take longer. One recording is
processed at a time per server process. This small English model may mishear
accents or background noise; typing remains available.
Spoken replies use **online Google Indian-English text-to-speech**
(`gTTS`, `lang="en"`, `tld="co.in"`), not installed Windows voices. Google
controls the voice and does not expose a gender selector through this API.
Turn **Voice on** to hear a greeting. Reply text is sent to Google for speech
generation; do not use this feature for sensitive text. Internet access is
required. Speech plays at 90% speed and 65% volume for a gentler delivery,
without a visible playback bar. If the browser blocks automatic playback,
an **Enable audio** button appears. Voice-service and playback
errors are shown below the input. No administrator installation is required.
Indian English is fixed for spoken replies; there is no voice selector or
comparison control.

### Reliable commands and reminders

- **What's new** (sidebar or below the input), or **"show updates"**, posts the
  shipped feature list and limitations directly in Priya's chat without using
  the model. A release notice also appears once per tab/session for a new
  release. Maintain `APP_RELEASE` and `APP_UPDATES` in `web_app.py` together
  when shipping future changes so the in-app notice stays accurate.
- Polite commands such as "Please open Google for me" use the same validated
  actions as "open Google"; Priya offers a link rather than claiming to control
  another browser tab.
- Say **"remind me in two minutes to drink water"** (seconds, minutes, hours,
  or days; up to 366 days), or **"create a task to review my notes"**.
  The server saves the task before confirming it. Unsupported reminder formats
  produce guidance, not a fictional promise; use the Tasks date/time picker
  for specific local times.
- Tasks are stored in SQLite at `~/.priya/tasks.sqlite3` by default. Set
  `PRIYA_DATA_DIR` to a private, persistent directory to change this location.
  Back up this directory. This is a single-owner application, not multi-user
  storage. Task titles and times are not encrypted at rest.
- Old browser tasks are imported once after a successful server save, then
  removed from browser storage. Failed imports retain the original data.
  Existing reminder flags are not treated as acknowledgement.
- Overdue reminders remain in a visible banner across tabs, page refreshes,
  and server restarts until **Acknowledge reminder** or task completion.
  Visible pages refresh tasks every 10 seconds. Closing the browser does not
  send an email or OS notification; overdue reminders appear when you return.
- While a reply is running, up to five typed or spoken messages queue visibly.
  A full queue retains the latest message in the input. Failed requests retain
  queued messages for **Send now**; **Stop** cancels generation, audio, microphone
  recording, and the queue. New conversation also clears chat context.
  Intermediate queued replies are displayed; only the last reply is spoken.

### Local AI and learning

Install [Ollama for Windows](https://ollama.com/download), then open a new
PowerShell window and download a small model:

```powershell
ollama pull qwen2.5:1.5b
```

Start Ollama before starting Priya. Ask a question such as "Explain how an
electric motor works" or a follow-up question. Priya sends your question and up
to the previous three AI exchanges to the Ollama service on the **server
machine** at `127.0.0.1:11434`; it does not send those questions to an AI cloud
provider. The first response may take time while the model loads. The small
model can be inaccurate: check important answers and do not rely on it for
medical, legal, financial, or safety-critical decisions. Conversation history
is kept only in the current browser tab and resets with a new conversation.
Replies stream incrementally and render sanitized Markdown lists, code blocks,
and tables on completion. Math is requested as readable plain-text equations,
not rendered LaTeX. Stopped or interrupted answers are not added to AI history.

Select **Use Wikipedia sources for AI answers**, or append **"with sources"**
to an explanation request, to retrieve numbered Wikipedia search excerpts
before generation. The topic is sent to Wikipedia. The model is instructed to
cite these excerpts, and actual retrieved links appear below the answer.
These are short excerpts, not a full-document RAG index or verified fact-checking;
the small model can still misinterpret them. If retrieval fails or finds
nothing, Priya reports that explicitly instead of claiming a sourced answer.
Citation numbers are checked against the retrieved list. If the model omits
citations or invents reference numbers, Priya explicitly replaces its draft
with the actual retrieved excerpts, labelled **not a verified AI summary**.
This validates reference IDs, not semantic entailment of every claim.
Replies that hit the model's generation limit are marked incomplete, not
silently treated as finished answers.

To select another locally installed model, set `PRIYA_OLLAMA_MODEL` before
starting Priya. `PRIYA_OLLAMA_URL` can be set by the administrator to point
the server at a **trusted** Ollama service. When deployed, the default address
refers to the deployment host or container, not the user's laptop. Never expose
Ollama directly to the public internet. To disable local AI, set
`PRIYA_AI_ENABLED=0`; it is disabled by default in the Docker image.

### Live Developer Monitor

Open **Developer monitor** in the sidebar, or **Monitor** below the message
input. Two views refresh every two seconds while the panel and tab are visible:

- **Runtime activity** shows observable browser/server stages: recording,
  transcription, command routing, saved tool actions, Wikipedia retrieval,
  model streaming, playback, HTTP statuses, timings, and request IDs.
  Stream setup latency is labelled separately from full model-stream duration.
  It does not expose hidden AI reasoning.
- **Development & tests** shows developer-maintained phase notes from
  `development_status.json`, actual unittest progress/results, and file-change
  notices for an explicit source/test/config allowlist. Changes are detected
  from file metadata since the current server start, not reconstructed Git
  history or source diffs. Python changes still require a restart.

Run the existing unittest suite with live reporting:

```powershell
.\.venv\Scripts\python.exe -m app_monitor --test
```

This uses Python's existing unittest runner and writes an atomic
`verification.json` into `PRIYA_DATA_DIR` (default `~/.priya`). The monitor
shows real pass/fail/error/skipped counts; no recorded run is shown as
**not_run**, never as a pass. Browser/hardware checks are separate,
developer-maintained evidence and are explicitly labelled. If a test process
is forcibly killed, its last report may remain `running`; check the start time
and terminal, then rerun the command rather than treating it as success.
The monitor never runs terminal commands from the browser.

Server runtime history is bounded to 200 events in memory and resets on
restart; this tab retains up to 80 browser events. The view omits chat text,
transcripts, recordings, request bodies, passwords, tokens, source contents,
and absolute filesystem paths. Monitor access requires login whenever login
is configured. Its lightweight polling is excluded from normal API rate-limit
counts and from runtime request metrics. A disconnected panel explicitly
marks displayed information as stale. This is a local developer/demo view,
not a replacement for durable production telemetry or a security audit.

### Research, tasks, and 3D

- Type `research solar energy` to search **English Wikipedia** and display
  links and snippets. This sends the search topic to Wikipedia. It is not a
  general web search or an AI-written, source-verified answer; open the sources
  and verify their accuracy and dates yourself.
- Open **Tasks** to create, complete, and delete tasks, with optional due times.
  You can also type or say `add task review my notes` to create a task without
  a reminder; use the Tasks panel to set a reminder on a new task.
  Tasks are shared by tabs/devices connected to the same Priya server.
  Desktop notifications require an open, visible page and browser permission.
  Browser throttling can delay alerts; overdue banners persist until acknowledged.
  Do not rely on Priya for critical reminders.
- Open **3D studio** or type `show atom`, `show water molecule`, or
  `show solar system`. Drag the model to rotate it. The animated avatar and
  prebuilt models are illustrations, not generated 3D models or accurate
  scale diagrams. WebXR AR/VR controls appear only when the browser reports a
  compatible device; they require a secure context and suitable headset or AR
  hardware. AR/VR has not been validated with a physical headset. A laptop
  screen cannot project a physical hologram.

Music search opens YouTube in another tab. Optional temporary server-side audio
is **disabled by default**. To enable it locally, set a private access key
before starting the app:

```powershell
$env:PRIYA_DOWNLOAD_KEY = 'replace-with-a-long-random-secret'
.\.venv\Scripts\python.exe web_app.py
```

The key is entered in the web interface when requesting audio. Keep it secret.
The server downloads to a temporary directory, returns the audio to the
browser, and deletes the server copy. This requires an internet connection and
is not offline playback. Audio is limited to 10 minutes and 25 MiB, with one
download at a time per server process and a 90-second timeout. Only download
content you have permission to use and comply with the applicable service terms.
Audio preparation depends on yt-dlp and may stop working as YouTube changes.

### Deploy the web app

The included `Dockerfile` runs the web app with Gunicorn on the `PORT`
environment variable (default 8080). Deploy the container to a provider that
supports long-running Python/Docker web services, and configure HTTPS at the
provider. Static-only hosting cannot run the Python server.

```powershell
docker build -t priya-assistant .
docker run --rm -p 127.0.0.1:8080:8080 -v priya-data:/data -e PRIYA_PASSWORD_HASH -e PRIYA_SESSION_SECRET priya-assistant
```

For server-side audio, set `PRIYA_DOWNLOAD_KEY` as a secret in the hosting
provider's environment settings, not in source control or the Docker image.
Use a strong random key and share it only with trusted users. The key protects
audio preparation only; it is **not** user authentication for the rest of the
app. The image requires **single-owner password authentication** and a stable
session secret; it refuses to start without them. Set these in your hosting
provider's secret manager, never in source control. Locally, you can prepare
them without putting a plaintext password in command history:

```powershell
$env:PRIYA_PASSWORD_HASH = & .\.venv\Scripts\python.exe -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Choose Priya password: ')))"
$env:PRIYA_SESSION_SECRET = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Keep the session secret stable between restarts. Password hashes must use
Werkzeug scrypt or PBKDF2. Without these variables the ordinary local development
command remains loopback-only and passwordless; setting both also enables login
locally. **Never expose passwordless local mode on a public interface.**
Production uses `PRIYA_ENV=production` (set in Docker), HTTPS-only HttpOnly
SameSite cookies, CSRF checks, and an eight-hour inactivity session lifetime.
Terminate HTTPS at your hosting reverse proxy. For an HTTP-only localhost smoke
test of the container, explicitly override `-e PRIYA_ENV=local`; do not do this
on a public server.

The app limits login attempts to 5 per 5 minutes per address, API traffic to
120 requests/minute, and combined chat/speech/transcription/audio requests to
30/minute. Limits are per process and reset on restart. Proxy-forwarded client
IP headers are deliberately not trusted, so anonymous clients behind one proxy
share a limit. Use one Gunicorn worker as configured and add hosting-layer
rate limits, body/time/resource quotas, and TLS configuration for public use.
Do not treat these application safeguards as an independent security audit.

Mount `/data` on persistent storage (the example uses a named Docker volume).
The image runs one worker with four threads and a 180-second timeout. Disable
response buffering at the reverse proxy for streamed replies and allow
sufficient request timeouts. Enable local AI only when a reachable Ollama model
is provisioned on the deployment network; `127.0.0.1` inside a container is not
your laptop.

`/healthz` is an unauthenticated process liveness endpoint used by Docker.
The authenticated `/api/status` and clickable UI service indicator check task
storage and Ollama/model availability. The microphone status says whether its
model is loaded, not whether physical microphone hardware is working.
Application logs contain method, path, status, request setup duration, and
explicit service errors, not chat bodies or passwords. Hosting logs may still
contain request metadata. Configure log retention and external uptime/error
alerts at the provider. Chat history remains only in the open browser tab.

## Desktop setup on Windows

1. Install Python 3.11 (tested), connect a microphone and speakers, and allow
   microphone access in Windows settings.
2. In PowerShell, open this folder and install dependencies in a virtual environment:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe ".\Voice open and play in youtube code.py"
   ```

3. Try "time", "open YouTube", "open Google", "open ChatGPT", "show graph",
   "play a song", or "play [song name]". Say "stop" to exit, or press Ctrl+C.
   You may prefix a command with "Priya"; this is not a wake word.

If pip reports a certificate verification error on a managed Windows computer,
try using the Windows certificate store with
`.\.venv\Scripts\python.exe -m pip --use-feature=truststore install -r requirements.txt`,
or contact your IT administrator.

For music, say **online** to open the result in your browser, or **offline** to
download it into a temporary directory, play it locally, and remove it afterward.
Both choices require internet access to search; offline mode also requires a
download. The checked-in Windows FFmpeg binaries are used if present; otherwise
FFmpeg must be available on PATH. YouTube changes can occasionally require a
yt-dlp update. Respect the rights and terms applicable to any content.

## Desktop privacy and limitations

Speech recognition sends microphone audio to Google's recognition service, and
spoken responses use Google text-to-speech. YouTube searches and downloads
contact YouTube. Internet access is therefore required even for offline song
playback. Do not use this prototype for sensitive conversations or unattended
operation. The application does not implement authentication or a wake word.
Microphone and audio-device errors are reported in the console.

The other scripts and `Priya` are earlier experiments, not the maintained entry
point. Some require additional packages such as pandas and pyttsx3.

## Tests

The [Windows checks workflow](https://github.com/NaveenDataNinja/Ai-voice-assistant/actions/workflows/windows-checks.yml)
runs on pushes and pull requests targeting `main` or the Priya review branch.
It uses Python 3.11 x64 and the existing setup script with `-SkipModels` to
validate constrained dependencies and the regression suite on a clean Windows
runner. It does not need secrets, an Ollama service, model downloads, or audio
hardware. A green check is automated regression evidence, not proof of working
physical audio, online providers, public deployment, or every laptop.

With the dependencies installed, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Install both `requirements.txt` and `web-requirements.txt` to run the full test
suite. Tests simulate external services and audio devices; they do not verify your
microphone, speakers, or AR/VR hardware.
