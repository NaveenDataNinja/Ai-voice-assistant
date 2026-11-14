"use strict";

const messages = document.getElementById("messages");
const suggestions = document.getElementById("suggestions");
const form = document.getElementById("chat-form");
const input = document.getElementById("message");
const send = document.getElementById("send");
const feedback = document.getElementById("feedback");
const conversation = document.querySelector(".conversation");
const mic = document.getElementById("microphone");
const voiceToggle = document.getElementById("voice-toggle");
const speechPlayer = document.getElementById("speech-player");
const speechRetry = document.getElementById("speech-retry");
const stopReply = document.getElementById("stop-reply");
const queuedMessages = document.getElementById("queued-messages");
const grounding = document.getElementById("grounding");
speechPlayer.volume = 0.65;
speechPlayer.defaultPlaybackRate = 0.9;
speechPlayer.playbackRate = 0.9;
const dialog = document.getElementById("audio-dialog");
const audioForm = document.getElementById("audio-form");
const audioKey = document.getElementById("audio-key");
const audioError = document.getElementById("audio-error");
const audioSubmit = document.getElementById("audio-submit");
const downloadsEnabled = document.body.dataset.downloadsEnabled === "true";
const objectUrls = new Set();
let waitingForSong = false;
let voiceEnabled = false;
let pendingSong = "";
let pendingMessage = null;
let pendingAudio = null;
let generation = 0;
let recorder = null;
let pendingTranscription = null;
let aiHistory = [];
let pendingSpeech = null;
let speechUrl = null;
let currentReply = null;
const messageQueue = [];

function scrollToBottom() {
  conversation.scrollTop = conversation.scrollHeight;
}

function addMessage(role, text, welcome = false) {
  const row = document.createElement("div");
  row.className = `message ${role}${welcome ? " welcome" : ""}`;
  if (role === "assistant") {
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "✦";
    row.append(avatar);
  }
  const content = document.createElement("div");
  content.className = "message-content";
  const heading = document.createElement("div");
  heading.className = "message-header";
  heading.textContent = role === "assistant" ? "Priya" : "You";
  const time = document.createElement("span");
  time.textContent = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date());
  heading.append(time);
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (welcome) {
    const title = document.createElement("div");
    title.className = "welcome-title";
    title.textContent = "Hello, Naveen. I'm Priya ✨";
    const body = document.createElement("div");
    body.className = "welcome-body";
    body.textContent = "Your companion for learning and everyday tasks. Ask me to explain a concept, research a topic, organize tasks, or explore a 3D model.";
    bubble.append(title, body);
  } else {
    bubble.textContent = text;
  }
  content.append(heading, bubble);
  row.append(content);
  messages.append(row);
  scrollToBottom();
  return bubble;
}

function stopSpeech() {
  if (pendingSpeech) pendingSpeech.abort();
  pendingSpeech = null;
  speechPlayer.pause();
  speechPlayer.removeAttribute("src");
  speechPlayer.load();
  speechPlayer.hidden = true;
  speechRetry.hidden = true;
  if (speechUrl) URL.revokeObjectURL(speechUrl);
  speechUrl = null;
}

async function say(text) {
  if (!voiceEnabled) return;
  stopSpeech();
  const controller = new AbortController();
  pendingSpeech = controller;
  feedback.textContent = "Preparing Priya's voice...";
  try {
    const response = await window.priyaApi("/api/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Voice generation failed.");
    }
    const audio = await response.blob();
    if (pendingSpeech !== controller || !voiceEnabled) return;
    speechUrl = URL.createObjectURL(audio);
    speechPlayer.src = speechUrl;
    await playSpeech();
  } catch (error) {
    if (error.name !== "AbortError" && pendingSpeech === controller) {
      feedback.textContent = `Voice unavailable: ${error.message}`;
    }
  } finally {
    if (pendingSpeech === controller) pendingSpeech = null;
  }
}

async function playSpeech() {
  const currentUrl = speechUrl;
  if (!currentUrl || !voiceEnabled) return;
  try {
    speechPlayer.playbackRate = 0.9;
    await speechPlayer.play();
    if (speechUrl === currentUrl && voiceEnabled) {
      speechRetry.hidden = true;
      feedback.textContent = "Priya is speaking.";
      window.priyaActivity("playback.started", "Browser MP3 playback started; this does not verify physical speaker audibility.", "ok");
    }
  } catch (error) {
    if (speechUrl !== currentUrl || !voiceEnabled) return;
    window.priyaActivity("playback.failed", "Browser audio playback failed or requires an explicit user gesture.", "error");
    speechRetry.hidden = error.name !== "NotAllowedError";
    feedback.textContent = error.name === "NotAllowedError"
      ? "Your browser requires a click to allow audio. Select Enable audio."
      : `Voice playback failed: ${error.message}`;
  }
}

speechRetry.addEventListener("click", playSpeech);
speechPlayer.addEventListener("ended", () => window.priyaActivity("playback.ended", "Browser speech playback finished."));
speechPlayer.addEventListener("error", () => {
  if (speechPlayer.getAttribute("src")) {
    window.priyaActivity("playback.failed", "The browser could not decode or play the speech audio.", "error");
    feedback.textContent = "Voice audio could not be played. Check browser audio settings and try again.";
  }
});

function addLink(container, label, url) {
  const link = document.createElement("a");
  link.className = "action-link";
  link.textContent = `${label} ↗`;
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  container.append(link);
}

function showReply(result, existingBubble = null) {
  window.priyaActivity("reply.rendered", `Rendering ${result.kind} output. Reply content is not logged.`);
  let text = result.reply;
  if (result.kind === "time") {
    text = `It's ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date())} in your local time.`;
  }
  if (result.kind === "task_saved") {
    window.priyaTasks.refresh().catch((error) => {
      feedback.textContent = `The task was saved, but the list could not refresh: ${error.message}`;
    });
  }
  const bubble = existingBubble || addMessage("assistant", text);
  bubble.classList.remove("typing");
  bubble.textContent = text;
  if (result.html) {
    bubble.innerHTML = result.html;
    bubble.classList.add("formatted");
  }
  if (!messageQueue.length && result.kind !== "updates") say(bubble.innerText.slice(0, 4000));
  if (result.warning) feedback.textContent = result.warning;
  else if (!voiceEnabled && !messageQueue.length) feedback.textContent = "Reply ready.";
  if (result.kind !== "updates") waitingForSong = result.kind === "ask_song";
  if (result.kind === "visual") {
    window.dispatchEvent(new CustomEvent("priya-open-studio", { detail: result.scene }));
  } else if (result.kind === "tasks") {
    window.dispatchEvent(new CustomEvent("priya-open-panel", { detail: "tasks-panel" }));
  }
  if (result.sources?.length) {
    const sources = document.createElement("div");
    sources.className = "source-list";
    result.sources.forEach((source, index) => {
      const card = document.createElement("div");
      card.className = "source-card";
      addLink(card, `[${index + 1}] ${source.title}`, source.url);
      const snippet = document.createElement("p");
      snippet.textContent = source.snippet;
      card.append(snippet);
      sources.append(card);
    });
    bubble.append(sources);
  }
  if (result.kind === "link" || result.kind === "music") {
    const actions = document.createElement("div");
    actions.className = "message-actions";
    addLink(actions, result.kind === "music" ? "Search YouTube" : result.label, result.url);
    if (result.kind === "music") {
      const button = document.createElement("button");
      button.className = "action-button";
      button.type = "button";
      button.textContent = downloadsEnabled ? "♫  Prepare temporary audio" : "♫  Temporary audio unavailable";
      button.disabled = !downloadsEnabled;
      if (!downloadsEnabled) button.title = "The server administrator must enable this feature.";
      button.addEventListener("click", () => {
        pendingSong = result.song;
        audioError.textContent = "";
        audioKey.value = "";
        dialog.showModal();
        audioKey.focus();
      });
      actions.append(button);
    }
    bubble.append(actions);
  } else if (result.kind === "graph") {
    const graph = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    graph.setAttribute("viewBox", "0 0 380 175");
    graph.setAttribute("class", "graph");
    graph.setAttribute("role", "img");
    graph.setAttribute("aria-label", "Sample graph of x squared from zero to nine");
    const grid = document.createElementNS(graph.namespaceURI, "path");
    grid.setAttribute("d", "M35 20V145H355 M35 115H355 M35 85H355 M35 55H355");
    grid.setAttribute("fill", "none");
    grid.setAttribute("stroke", "#e0e7f6");
    const line = document.createElementNS(graph.namespaceURI, "polyline");
    line.setAttribute("points", "35,145 70,143 105,139 140,132 175,123 210,111 245,96 280,78 315,58 350,35");
    line.setAttribute("fill", "none");
    line.setAttribute("stroke", "#7288f2");
    line.setAttribute("stroke-width", "3");
    line.setAttribute("stroke-linecap", "round");
    line.setAttribute("stroke-linejoin", "round");
    graph.append(grid, line);
    bubble.append(graph);
  }
  scrollToBottom();
}

function renderQueue() {
  queuedMessages.replaceChildren();
  messageQueue.forEach((item, index) => {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = `Queued: ${item.text}`;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Cancel";
    remove.setAttribute("aria-label", `Cancel queued message ${index + 1}`);
    remove.addEventListener("click", () => { messageQueue.splice(index, 1); renderQueue(); });
    const retry = document.createElement("button");
    retry.type = "button";
    retry.textContent = "Send now";
    retry.disabled = Boolean(pendingMessage);
    retry.addEventListener("click", () => {
      messageQueue.splice(index, 1);
      renderQueue();
      submitMessage(item.text, item);
    });
    row.append(label, retry, remove);
    queuedMessages.append(row);
  });
}

function cancelReply() {
  if (pendingMessage || pendingTranscription || pendingSpeech || recorder?.state === "recording" || messageQueue.length || !speechPlayer.paused) {
    window.priyaActivity("reply.cancelled", "Stopped the current reply, audio, microphone work and queued messages in this tab.");
  }
  generation++;
  if (pendingMessage) pendingMessage.abort();
  pendingMessage = null;
  messageQueue.length = 0;
  renderQueue();
  stopReply.hidden = true;
  if (currentReply) {
    if (currentReply.classList.contains("typing") || !currentReply.textContent) currentReply.textContent = "Stopped.";
    else currentReply.append(document.createTextNode("\n\n[Stopped before completion]"));
    currentReply.classList.remove("typing");
    currentReply = null;
  }
  stopSpeech();
  waitingForSong = false;
  if (recorder && recorder.state !== "inactive") recorder.stop();
  if (pendingTranscription) pendingTranscription.abort();
  document.querySelectorAll("audio").forEach((player) => player.pause());
  feedback.textContent = "Stopped. Queued messages were cancelled.";
}
stopReply.addEventListener("click", cancelReply);

async function readReplyStream(response, bubble, controller, currentGeneration) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let text = "";
  let result = null;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newline;
      while ((newline = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (controller.signal.aborted || currentGeneration !== generation) return null;
        if (event.type === "token") {
          if (!text) window.priyaActivity("reply.first_token", "First streamed text appeared in this tab.", "ok");
          text += event.text;
          bubble.classList.remove("typing");
          bubble.textContent = text;
          scrollToBottom();
        } else if (event.type === "done") {
          result = event;
        } else if (event.type === "error") {
          throw new Error(event.error);
        }
      }
      if (done) break;
    }
    if (!result || buffer.trim()) throw new Error("The reply stream ended before completion. Please retry.");
    return result;
  } finally {
    reader.releaseLock();
  }
}

async function submitMessage(text, queuedItem = null) {
  const value = text.trim();
  if (!value) return;
  if (/^(?:priya[,\s]+)?(?:stop|exit|quit)[.!?]*$/i.test(value)) {
    input.value = "";
    cancelReply();
    return;
  }
  if (value.length > 500) {
    input.value = value;
    feedback.textContent = "Messages must be 500 characters or fewer. Your text remains in the input.";
    return;
  }
  if (pendingMessage) {
    if (messageQueue.length >= 5) {
      if (input.value.trim() !== value) input.value = input.value ? `${input.value}\n${value}` : value;
      feedback.textContent = "The queue is full. Your text remains in the input; split long drafts before sending.";
      return;
    }
    messageQueue.push({ text: value, grounded: grounding.checked, id: crypto.randomUUID() });
    window.priyaActivity("message.queued", `${messageQueue.length} message(s) waiting; message text is not logged.`);
    if (input.value.trim() === value) input.value = "";
    renderQueue();
    feedback.textContent = "Your message is queued, not discarded.";
    return;
  }
  if (waitingForSong && value.toLowerCase() === "cancel") {
    waitingForSong = false;
    addMessage("user", value);
    if (!queuedItem && input.value.trim() === value) input.value = "";
    addMessage("assistant", "Okay, I won't search for a song.");
    return;
  }
  const command = waitingForSong ? `play ${value}` : value;
  waitingForSong = false;
  addMessage("user", value);
  if (!queuedItem && input.value.trim() === value) input.value = "";
  suggestions.hidden = true;
  stopReply.hidden = false;
  const currentGeneration = generation;
  const controller = new AbortController();
  pendingMessage = controller;
  const loading = addMessage("assistant", "Thinking");
  currentReply = loading;
  let failed = false;
  loading.classList.add("typing");
  loading.textContent = "";
  for (let i = 0; i < 3; i++) loading.append(document.createElement("i"));
  try {
    const response = await window.priyaApi("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: command, history: aiHistory, stream: true,
        grounded: queuedItem ? queuedItem.grounded : grounding.checked,
        action_id: queuedItem ? queuedItem.id : crypto.randomUUID(),
      }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Unable to process your message.");
    }
    const result = response.headers.get("Content-Type")?.includes("application/x-ndjson")
      ? await readReplyStream(response, loading, controller, currentGeneration)
      : await response.json();
    if (result && currentGeneration === generation) {
      if (result.kind === "ai") {
        aiHistory.push({ role: "user", content: command }, { role: "assistant", content: result.reply.slice(0, 1500) });
        aiHistory = aiHistory.slice(-6);
      }
      showReply(result, loading);
      currentReply = null;
    }
  } catch (error) {
    if (error.name !== "AbortError" && currentGeneration === generation) {
      failed = true;
      if (loading.classList.contains("typing")) loading.textContent = `Sorry, ${error.message}`;
      else loading.append(document.createTextNode(`\n\nReply incomplete: ${error.message}`));
      loading.classList.remove("typing");
      currentReply = null;
      if (!input.value) input.value = value;
      renderQueue();
      feedback.textContent = "The request failed. Your message is available to retry; queued messages remain below.";
    }
  } finally {
    if (pendingMessage === controller) {
      pendingMessage = null;
      stopReply.hidden = true;
      const next = failed ? null : messageQueue.shift();
      renderQueue();
      if (next && currentGeneration === generation) queueMicrotask(() => {
        if (currentGeneration === generation) submitMessage(next.text, next);
      });
    }
  }
}

function newConversation() {
  cancelReply();
  if (pendingAudio) pendingAudio.abort();
  pendingMessage = null;
  pendingAudio = null;
  send.disabled = false;
  audioSubmit.disabled = false;
  waitingForSong = false;
  aiHistory = [];
  pendingSong = "";
  if (dialog.open) dialog.close();
  audioKey.value = "";
  if (recorder && recorder.state !== "inactive") recorder.stop();
  if (pendingTranscription) pendingTranscription.abort();
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  document.querySelectorAll("audio").forEach((player) => player.pause());
  objectUrls.forEach((url) => URL.revokeObjectURL(url));
  objectUrls.clear();
  messages.replaceChildren();
  suggestions.hidden = false;
  input.value = "";
  feedback.textContent = "Local AI can make mistakes. Check important information.";
  addMessage("assistant", "", true);
  input.focus();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessage(input.value);
});
suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-command]");
  if (button) submitMessage(button.dataset.command);
});
document.getElementById("new-chat").addEventListener("click", newConversation);
document.getElementById("mobile-new").addEventListener("click", newConversation);

function setVoiceEnabled(enabled) {
  voiceEnabled = enabled;
  voiceToggle.setAttribute("aria-pressed", String(voiceEnabled));
  voiceToggle.querySelector("span").textContent = voiceEnabled ? "Voice on" : "Voice off";
  voiceToggle.title = voiceEnabled ? "Turn spoken replies off" : "Turn spoken replies on";
  if (!voiceEnabled) {
    stopSpeech();
    feedback.textContent = "Voice is off.";
  }
}

voiceToggle.addEventListener("click", () => {
  setVoiceEnabled(!voiceEnabled);
  if (voiceEnabled) say("Hello Naveen. I'm Priya, your assistant.");
});

if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
  mic.disabled = true;
  mic.title = "Microphone recording requires a supported browser and HTTPS (or localhost). You can still type.";
} else {
  mic.addEventListener("click", async () => {
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
      return;
    }
    const currentGeneration = generation;
    let stream = null;
    mic.disabled = true;
    stopSpeech();
    try {
      window.priyaActivity("microphone.requested", "Requesting browser microphone access.");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (currentGeneration !== generation) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      const recording = new MediaRecorder(stream);
      recorder = recording;
      const chunks = [];
      let recordingFailed = false;
      recording.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recording.onerror = () => {
        recordingFailed = true;
        feedback.textContent = "Microphone recording failed. Check your microphone and try again.";
        stream.getTracks().forEach((track) => track.stop());
        if (recording.state !== "inactive") recording.stop();
      };
      recording.start();
      window.priyaActivity("recording.started", "Recording locally, with a 30-second limit.");
      const timer = setTimeout(() => {
        if (recording.state !== "inactive") recording.stop();
      }, 30000);
      recording.onstop = async () => {
        window.priyaActivity("recording.stopped", "Recording stopped; microphone tracks are being released.");
        clearTimeout(timer);
        stream.getTracks().forEach((track) => track.stop());
        recorder = null;
        mic.classList.remove("listening");
        mic.title = "Use microphone";
        if (recordingFailed || currentGeneration !== generation) return;
        mic.disabled = true;
        const controller = new AbortController();
        pendingTranscription = controller;
        feedback.textContent = "Transcribing on Priya's server...";
        try {
          const response = await window.priyaApi("/api/transcribe", {
            method: "POST",
            body: new Blob(chunks, { type: recording.mimeType }),
            signal: controller.signal,
          });
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || "Voice recognition failed.");
          if (currentGeneration !== generation) return;
          feedback.textContent = "Voice captured.";
          submitMessage(result.text);
        } catch (error) {
          if (error.name !== "AbortError" && currentGeneration === generation) {
            feedback.textContent = `Voice input unavailable: ${error.message}`;
          }
        } finally {
          if (pendingTranscription === controller) pendingTranscription = null;
          mic.disabled = false;
        }
      };
      mic.classList.add("listening");
      mic.title = "Stop recording";
      feedback.textContent = "Listening... Click the microphone again to send (maximum 30 seconds). Audio is processed on Priya's server.";
    } catch (error) {
      if (stream) stream.getTracks().forEach((track) => track.stop());
      window.priyaActivity("recording.failed", "Microphone permission or recording initialization failed.", "error");
      feedback.textContent = `Could not record voice: ${error.message}. Allow microphone access and try again.`;
    } finally {
      mic.disabled = false;
    }
  });
}

document.getElementById("audio-cancel").addEventListener("click", () => {
  if (pendingAudio) pendingAudio.abort();
  audioKey.value = "";
  dialog.close();
});
dialog.addEventListener("cancel", () => {
  if (pendingAudio) pendingAudio.abort();
  audioKey.value = "";
});
audioForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pendingAudio) return;
  const currentGeneration = generation;
  const song = pendingSong;
  const controller = new AbortController();
  pendingAudio = controller;
  audioSubmit.disabled = true;
  audioError.textContent = "Preparing audio. This can take a minute...";
  try {
    const response = await window.priyaApi("/api/audio", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Priya-Download-Key": audioKey.value },
      body: JSON.stringify({ song }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Audio preparation failed.");
    }
    const audio = await response.blob();
    if (currentGeneration !== generation) return;
    const url = URL.createObjectURL(audio);
    objectUrls.add(url);
    dialog.close();
    audioKey.value = "";
    const bubble = addMessage("assistant", `Your temporary audio for "${song}" is ready. Press play to listen.`);
    const player = document.createElement("audio");
    player.controls = true;
    player.className = "audio-player";
    player.src = url;
    bubble.append(player);
    scrollToBottom();
  } catch (error) {
    if (error.name !== "AbortError" && currentGeneration === generation) {
      audioError.textContent = error.message;
    }
  } finally {
    if (pendingAudio === controller) {
      pendingAudio = null;
      audioSubmit.disabled = false;
    }
  }
});

newConversation();

async function checkServices() {
  const status = document.getElementById("service-status");
  status.disabled = true;
  try {
    const response = await window.priyaApi("/api/status");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Status check failed.");
    status.textContent = result.status === "ok" ? (result.ai === "disabled" ? "AI disabled" : "Ready to help") : "AI unavailable";
    status.title = `Tasks: ${result.tasks}. AI: ${result.ai}. Microphone: ${result.transcription}. Click to check again.`;
  } catch (error) {
    status.textContent = "Check connection";
    status.title = error.message;
    feedback.textContent = `Service check failed: ${error.message}`;
  } finally {
    status.disabled = false;
  }
}
document.getElementById("service-status").addEventListener("click", checkServices);
checkServices();

document.getElementById("show-updates").addEventListener("click", () => submitMessage("show updates"));
document.getElementById("mobile-updates").addEventListener("click", () => submitMessage("show updates"));

async function announceUpdates() {
  try {
    const release = document.body.dataset.release;
    if (sessionStorage.getItem("priya.updates.seen") === release) return;
    const response = await window.priyaApi("/api/updates");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Updates could not be loaded.");
    showReply(result);
    sessionStorage.setItem("priya.updates.seen", release);
  } catch (error) {
    feedback.textContent = `Update notice could not be loaded or remembered: ${error.message}. Use What's new to view it.`;
  }
}
announceUpdates();
