# Move Priya to a new Windows laptop

Priya is the next-version web application in the AI-voice-assistant repository.
You do not need the old laptop's virtual environment, Windows account,
absolute folder paths, installed browser voices, or Git credentials.

**Target:** Windows x64 (Intel/AMD), Python 3.11. The tested Python was 3.11.9.
Other operating systems, Windows ARM, and newer Python releases need their
own compatibility validation. No software project can guarantee working
microphones, speakers, graphics drivers, or network policy on every laptop.

## 1. What moves through Git, and what does not

| Git clone contains | Obtain separately on your own laptop |
|---|---|
| Application source, UI, tests, and handbooks | Git and Python 3.11 x64 |
| Windows setup and start scripts | Ollama application/service |
| Tested Python dependency version constraints | Python packages downloaded during setup |
| A private task backup/restore tool, but no real tasks | tiny.en and qwen2.5:1.5b model downloads/cache |
| Deployment configuration without credentials | Your own GitHub login, optional deployment secrets |
| Existing repository desktop/FFmpeg assets | Optional private task backup ZIP |

Model files are deliberately not committed. Setup provisions them on the new
machine. Internet is needed for first-time installation/model downloads and
for online Google speech, Wikipedia, and YouTube features.

Git does not transfer permanent chat history because the app does not maintain
one. It also must not transfer the old laptop's credentials or private data.

### Portability verification performed

On 14 November 2026, the next-version branch was cloned into a separate folder
and its full setup script was run with a **new virtual environment** on Windows
x64/Python 3.11.9. All **55 regression tests passed**. The start script then
served the clone on a separate local port, and actual HTTP checks passed for:

- Dependency readiness and release/monitor endpoints.
- A separately restored task database.
- Real Ollama streaming and final formatted output.
- Wikipedia retrieval.
- Google Indian-English MP3 generation.
- Local recognition of a generated speech fixture and deterministic command
  routing from the recognized text.
- Zero remaining active AI streams after completion.

The test reused this Windows account's existing model caches and the running
Ollama service. It did not physically test another laptop, a human microphone
or speaker, or AR/VR hardware. Perform section 7 on your own laptop; do not
treat a clean environment test as a guarantee of every device/network.

## 2. Install prerequisites

1. Install Git for Windows from <https://git-scm.com/downloads/win>.
2. Install Python **3.11 x64** from <https://www.python.org/downloads/windows/>.
   Include the Python launcher or add Python to PATH. If using another Python
   version, do not assume the pinned environment is supported.
3. Install/start Ollama from <https://ollama.com/download/windows>.
4. Open a new PowerShell window after installation. Keep Ollama running.
5. Use a current browser with microphone permission and WebGL support.

No separate Node.js build step or installed Windows speech voice is needed.
Leave optional server-side music download disabled unless you explicitly need
it and have the necessary rights.

## 3. Clone the next-version branch

Until reviewed and merged, the new application is on a review branch, not main:

Share the [Priya branch page](https://github.com/NaveenDataNinja/Ai-voice-assistant/tree/priya-v2-windows-portable),
which also exposes the current README and setup guide. The default repository
page still opens the original `main` version. GitHub's **Your branches** and
**Active branches** can show this same branch twice; do not delete it.

```powershell
git clone --branch priya-v2-windows-portable --single-branch https://github.com/NaveenDataNinja/Ai-voice-assistant.git
Set-Location -LiteralPath ".\Ai-voice-assistant"
```

Choose any folder you own. Do not copy the other laptop's `.venv`.
If the branch is later merged/deleted, use the reviewed main branch or its
agreed release commit instead.

## 4. Set up this clone

```powershell
powershell -NoProfile -File .\setup.ps1
```

The script:

1. Checks Windows x64 and Python 3.11.
2. Creates this clone's `.venv` if needed; refuses an incompatible environment.
3. Installs both requirement manifests under the tested Windows version
   constraints.
4. Checks installed dependency consistency.
5. Downloads/loads tiny.en for local CPU recognition.
6. Checks Ollama and downloads qwen2.5:1.5b if missing.
7. Runs the regression suite and publishes genuine verification progress.

Allow time for the first model downloads. Ollama must already be installed
and reachable; the script does not silently install system software or
request administrator privileges. Missing prerequisites and failed commands
stop setup explicitly.

If Python 3.11 is installed at a specific path:

```powershell
powershell -NoProfile -File .\setup.ps1 -PythonExecutable "C:\Path\To\Python311\python.exe"
```

`-SkipModels` is available for dependency/test work only. It is not a complete
voice/AI installation; rerun without it before expecting those features.

The setup uses pip's Windows certificate-store support without disabling
certificate validation. If scripts are blocked by organizational policy,
ask your administrator to approve the workflow; do not disable managed
security controls. Where permitted, the manual equivalent is:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip --use-feature=truststore install -r requirements.txt -r web-requirements.txt -c requirements-windows-py311.lock.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('tiny.en', device='cpu', compute_type='int8')"
ollama pull qwen2.5:1.5b
.\.venv\Scripts\python.exe -m app_monitor --test
```

The lock file supplies tested version constraints, not package hashes, an
offline installer, or a pinned immutable model digest. It does not change the
separate Docker/Linux dependency workflow.

## 5. Restore your private tasks, if wanted

Do this **before the first app start**, with the app stopped. Setup's tests
use temporary task databases and do not require importing your real tasks.
The verification report alone does not count as an existing task database.

Your separately supplied ZIP contains a consistent SQLite snapshot and a
manifest with a task count/checksum. It contains no deployment secrets,
recordings, model files, or chat archive. It is **not encrypted**: use trusted
private storage/transport, not GitHub or a public download link.

Copy the ZIP to your own Downloads folder and replace the example filename:

```powershell
.\.venv\Scripts\python.exe priya_data.py restore --input "$HOME\Downloads\priya-tasks-YOUR-BACKUP.zip"
```

Default destination is `$HOME\.priya\tasks.sqlite3`. Completion,
acknowledgement, titles, IDs, and due times are preserved.

Restore refuses an existing task database, even an empty one, rather than
overwriting anything. If you already started using a different task database,
stop the app and restore into a new private data directory:

```powershell
$env:PRIYA_DATA_DIR = "$HOME\Priya-restored-data"
.\.venv\Scripts\python.exe priya_data.py restore --input "$HOME\Downloads\priya-tasks-YOUR-BACKUP.zip" --data-dir "$env:PRIYA_DATA_DIR"
```

Use the **same** `PRIYA_DATA_DIR` when starting Priya and running live test
reporting. Environment variables set in a PowerShell window apply to that
window and its child processes, not automatically to every future window.
Repeat the setting when opening a new terminal if you use a custom directory.

Checksum checking detects corruption, not authenticity against a maliciously
rewritten archive. Restore only a backup you trust. Archive entries and
decompressed database size are restricted; maximum supported database size
for this migration tool is 8 MiB.

## 6. Start the app

```powershell
powershell -NoProfile -File .\start.ps1
```

Open <http://127.0.0.1:5000>. To choose a different free port:

```powershell
powershell -NoProfile -File .\start.ps1 -Port 18755
```

Keep the terminal running; press Ctrl+C to stop the server. Ollama runs
separately. Local Flask mode is loopback-only and passwordless without
configured credentials; this is not public hosting.

The scripts do not load a `.env` file. Set environment variables explicitly
before starting if you need custom configuration. Do not bring another
person's secrets from the old laptop.

## 7. Check the actual laptop, not just installation success

- [ ] Ask `Who am I?` and `What time is it?`.
- [ ] Ask `Explain voltage` and verify a completed streamed reply.
- [ ] Ask a follow-up; verify the short in-tab AI context.
- [ ] Turn Voice on; verify the soft Indian-English reply is actually audible.
- [ ] Grant microphone permission, record, and verify recognized text.
- [ ] Create a test reminder; confirm it appears in Tasks.
- [ ] Refresh/restart and check restored tasks remain.
- [ ] Acknowledge a due reminder; confirm other tabs refresh appropriately.
- [ ] Try `research solar energy` with internet available.
- [ ] Open 3D studio and rotate a model.
- [ ] Start an AI reply and use Stop; then send another request.
- [ ] Open Monitor and inspect runtime activity and genuine test results.
- [ ] Remove only the test task you created.

Speech recognition may vary with accent/noise. Voice needs Google connectivity
and browser playback permission. Normal 3D needs usable graphics; AR/VR also
requires compatible hardware and is not certified by these checks.

## 8. Make future backups and continue development

Create a new private archive, outside the clone:

```powershell
.\.venv\Scripts\python.exe priya_data.py backup --output "$HOME\Priya-private-migration\priya-tasks-new.zip"
```

The backup uses SQLite's consistent snapshot API and may be taken while the
app runs. It is a point-in-time snapshot: later task changes are not included.
Choose a new filename; existing archives are not overwritten.

For code updates:

```powershell
git pull --ff-only
powershell -NoProfile -File .\setup.ps1
```

Commit or otherwise preserve your own changes before pulling. The setup reuses
a compatible environment/models and reruns tests. Do not upgrade individual
packages casually and assume the tested constraints remain applicable.

Check the [Windows checks results](https://github.com/NaveenDataNinja/Ai-voice-assistant/actions/workflows/windows-checks.yml)
for the exact commit you intend to share. These automated runs skip models and
simulate external services/devices; still perform the real-laptop checklist in
section 7 after setup.

Configure your own Git author on your own laptop and sign in to your own
GitHub account. Do not copy credential-manager files from another machine.
Only push source/configuration templates, never task archives, passwords,
private databases, recordings, or virtual environments.

## 9. Troubleshooting

| Problem | Action |
|---|---|
| Python launcher cannot find 3.11 | Install the targeted x64 interpreter or pass its explicit path |
| Existing `.venv` has the wrong Python | Use a fresh clone/environment; setup will not delete yours |
| Script policy blocks execution | Ask the administrator; use permitted manual commands rather than disabling policy |
| Dependency installation fails | Preserve the error, check internet/certificates and Python architecture; do not silently loosen versions |
| Ollama unreachable | Start Ollama and rerun setup; verify a configured remote URL is trusted |
| Model download fails | Check network, disk space and provider access, then rerun; models are not in Git |
| Text works but voice does not | Check Voice setting, Google connectivity, speaker/mute and Enable audio |
| Microphone unavailable | Grant permission, use localhost/HTTPS, check input device and model setup |
| Restored tasks missing | Confirm the app and restore used the same Windows account/data directory |
| Restore refuses existing data | Do not delete it blindly; restore into a new empty data directory |
| Port already in use | Select another port; do not kill unrelated processes |

See the [Developer Handbook](DEVELOPER_HANDBOOK.md) for the deeper runbook and
the [Technical Client Guide](TECHNICAL_CLIENT_GUIDE.md) for hosting limitations.
