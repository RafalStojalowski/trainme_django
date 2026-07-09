// ── DOM refs ──────────────────────────────────────────────────────────────────
const accountBtn      = document.getElementById("accountBtn");
const accountDropdown = document.getElementById("accountDropdown");
const startBtn        = document.getElementById("startBtn");
const statusText      = document.getElementById("status");
const messagesEl      = document.getElementById("messages");
const interimText     = document.getElementById("interimText");
const hamburgerBtn    = document.getElementById("hamburgerBtn");
const drawer          = document.getElementById("drawer");
const drawerOverlay   = document.getElementById("drawerOverlay");
const drawerCloseBtn  = document.getElementById("drawerCloseBtn");
const newConvBtn      = document.getElementById("newConvBtn");
const convList        = document.getElementById("convList");

// ── Speech state ──────────────────────────────────────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;
let isListening       = false;
let mediaStream;
let wavRecorder       = null;
let currentAudioBlob  = null;
let finalTranscription = "";
let silenceTimer      = null;
const SILENCE_TIMEOUT = 2000;

// ── Conversation lifecycle — auto-end on inactivity or tab close ──────────────
// The persona only learns from a conversation once it's "ended" (new_conversation),
// so an idle chat or a closed tab must trigger that too, not just the explicit button.
const IDLE_CONVERSATION_TIMEOUT = 5 * 60 * 1000; // 5 min of no new turns
let idleConversationTimer = null;

function resetIdleConversationTimer() {
    if (idleConversationTimer) clearTimeout(idleConversationTimer);
    idleConversationTimer = setTimeout(endConversationSilently, IDLE_CONVERSATION_TIMEOUT);
}

function endConversationSilently() {
    if (idleConversationTimer) { clearTimeout(idleConversationTimer); idleConversationTimer = null; }
    fetch("/conversations/new/", {
        method:  "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    }).catch(() => {});
}

// Best-effort finalize on tab close/refresh — fetch is unreliable during unload,
// sendBeacon is fire-and-forget and survives page teardown.
window.addEventListener("pagehide", () => {
    const body = new URLSearchParams({ csrfmiddlewaretoken: getCookie("csrftoken") || "" });
    navigator.sendBeacon("/conversations/new/", body);
});

// ── WavRecorder — real 16-bit PCM WAV via AudioContext ────────────────────────
class WavRecorder {
    constructor() {
        this.audioCtx  = null;
        this.processor = null;
        this.source    = null;
        this.chunks    = [];
        this.sampleRate = 0;
    }

    start(stream) {
        this.chunks   = [];
        this.audioCtx = new AudioContext();
        this.sampleRate = this.audioCtx.sampleRate;
        this.source   = this.audioCtx.createMediaStreamSource(stream);
        this.processor = this.audioCtx.createScriptProcessor(4096, 1, 1);

        this.processor.onaudioprocess = (e) => {
            this.chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
        };

        this.source.connect(this.processor);
        this.processor.connect(this.audioCtx.destination);
    }

    stop() {
        if (this.processor) { this.processor.disconnect(); this.processor = null; }
        if (this.source)    { this.source.disconnect();    this.source    = null; }
        if (this.audioCtx)  { this.audioCtx.close();       this.audioCtx  = null; }
        return this._buildWav();
    }

    _buildWav() {
        const totalLen = this.chunks.reduce((s, c) => s + c.length, 0);
        const pcm      = new Float32Array(totalLen);
        let   off      = 0;
        for (const c of this.chunks) { pcm.set(c, off); off += c.length; }

        const int16 = new Int16Array(pcm.length);
        for (let i = 0; i < pcm.length; i++) {
            int16[i] = Math.max(-32768, Math.min(32767, pcm[i] * 32768));
        }

        const dataLen = int16.byteLength;
        const buf     = new ArrayBuffer(44 + dataLen);
        const v       = new DataView(buf);
        const sr      = this.sampleRate;
        const wr      = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };

        wr(0,  "RIFF"); v.setUint32(4,  36 + dataLen, true); wr(8,  "WAVE");
        wr(12, "fmt "); v.setUint32(16, 16, true);
        v.setUint16(20, 1, true); v.setUint16(22, 1, true);
        v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true);
        v.setUint16(32, 2, true); v.setUint16(34, 16, true);
        wr(36, "data"); v.setUint32(40, dataLen, true);
        new Uint8Array(buf, 44).set(new Uint8Array(int16.buffer));

        return new Blob([buf], { type: "audio/wav" });
    }
}

// ── Audio setup — microphone stream only ─────────────────────────────────────
async function setupAudioRecording() {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
        statusText.textContent = "Błąd: brak dostępu do mikrofonu";
        console.error(err);
    }
}

setupAudioRecording();

// ── Message rendering ─────────────────────────────────────────────────────────
function appendBotMessage(html, audioUrl) {
    const row = document.createElement("div");
    row.className = "msg-row bot";

    const audioBtn = audioUrl
        ? `<button class="audio-btn bot-audio-btn" title="Odtwórz odpowiedź">▶</button>`
        : "";

    row.innerHTML = `<div class="bubble bot-bubble">${html}${audioBtn}</div>`;

    if (audioUrl) {
        const audio = new Audio(audioUrl);
        audio.play().catch(() => {});
        row.querySelector(".bot-audio-btn").addEventListener("click", () => audio.play());
    }

    messagesEl.appendChild(row);
    scrollToBottom();
}

// audioSource: Blob | string URL | null
function appendUserMessage(text, audioSource) {
    const row = document.createElement("div");
    row.className = "msg-row user";

    const audioBtn = audioSource
        ? `<button class="audio-btn" title="Odtwórz nagranie">▶</button>`
        : "";

    row.innerHTML = `
        <div class="bubble user-bubble">
            <span class="bubble-text">${text}</span>
            ${audioBtn}
        </div>`;

    if (audioSource) {
        const src   = audioSource instanceof Blob
            ? URL.createObjectURL(audioSource)
            : audioSource;
        const audio = new Audio(src);
        row.querySelector(".audio-btn").addEventListener("click", () => audio.play());
    }

    messagesEl.appendChild(row);
    scrollToBottom();
}

function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ── Speech recognition ────────────────────────────────────────────────────────
if (!SpeechRecognition) {
    alert("Twoja przeglądarka nie wspiera rozpoznawania mowy");
} else {
    recognition = new SpeechRecognition();
    recognition.continuous      = true;
    recognition.interimResults  = true;
    recognition.lang            = "pl-PL";
    recognition.maxAlternatives = 1;

    function stopRecording() {
        if (wavRecorder) {
            currentAudioBlob = wavRecorder.stop();
            wavRecorder      = null;
        }
    }

    startBtn.onclick = () => {
        if (!isListening) {
            currentAudioBlob   = null;
            finalTranscription = "";
            recognition.start();
            if (mediaStream) {
                wavRecorder = new WavRecorder();
                wavRecorder.start(mediaStream);
            }
        } else {
            recognition.stop();
            stopRecording();
        }
    };

    function resetSilenceTimer() {
        if (silenceTimer) clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
            if (!isListening) return;
            recognition.stop();
            stopRecording();
        }, SILENCE_TIMEOUT);
    }

    recognition.onstart = () => {
        isListening = true;
        startBtn.classList.add("listening");
        startBtn.querySelector(".mic-label").textContent = "Stop";
        statusText.textContent = "Nasłuchuję...";
        resetSilenceTimer();
    };

    recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                finalTranscription += event.results[i][0].transcript + " ";
            } else {
                interim += event.results[i][0].transcript;
            }
        }
        interimText.textContent = interim;
        resetSilenceTimer();
    };

    recognition.onerror = (event) => {
        statusText.textContent = "Błąd: " + event.error;
        console.error(event.error);
    };

    recognition.onend = async () => {
        if (silenceTimer) clearTimeout(silenceTimer);
        stopRecording();
        isListening = false;
        startBtn.classList.remove("listening");
        startBtn.querySelector(".mic-label").textContent = "Mów";
        statusText.textContent = "Kliknij i zacznij mówić";
        interimText.textContent = "";

        if (finalTranscription.trim()) {
            await sendFinalTranscription(finalTranscription.trim());
        }
    };
}

// ── Send to backend ───────────────────────────────────────────────────────────
async function sendFinalTranscription(text) {
    const audioBlob   = currentAudioBlob;
    const audioBase64 = audioBlob ? await blobToBase64(audioBlob) : null;

    appendUserMessage(text, audioBlob);
    statusText.textContent = "Przetwarzam...";

    try {
        const res  = await fetch("/speech/", {
            method:  "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken":  getCookie("csrftoken"),
            },
            body: JSON.stringify({ text, audio: audioBase64, is_session_end: true }),
        });

        const data = await res.json();

        if (data.status === "session_complete") {
            statusText.textContent = "Kliknij i zacznij mówić";
            if (data.bot_response) appendBotMessage(data.bot_response, data.bot_audio_url || null);
            console.log(`✅ Conv #${data.conversation_id} | msg #${data.message_number}`);
            resetIdleConversationTimer();
        } else if (data.status === "error") {
            statusText.textContent = "Błąd: " + data.message;
        }
    } catch (err) {
        statusText.textContent = "Błąd połączenia";
        console.error(err);
    }
}

// ── Drawer ────────────────────────────────────────────────────────────────────
let drawerOpen = false;

function openDrawer() {
    drawerOpen = true;
    drawer.classList.add("open");
    drawerOverlay.classList.add("open");
    hamburgerBtn.classList.add("open");
    loadConversations();
}

function closeDrawer() {
    drawerOpen = false;
    drawer.classList.remove("open");
    drawerOverlay.classList.remove("open");
    hamburgerBtn.classList.remove("open");
}

hamburgerBtn.addEventListener("click", () => drawerOpen ? closeDrawer() : openDrawer());
drawerOverlay.addEventListener("click", closeDrawer);
drawerCloseBtn.addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && drawerOpen) closeDrawer(); });

// Edge-drag to open (mouse + touch)
let dragStartX = null;

document.addEventListener("mousedown", (e) => {
    if (e.clientX < 24) dragStartX = e.clientX;
});
document.addEventListener("mousemove", (e) => {
    if (dragStartX !== null && e.clientX - dragStartX > 50) { openDrawer(); dragStartX = null; }
});
document.addEventListener("mouseup", () => { dragStartX = null; });

document.addEventListener("touchstart", (e) => {
    if (e.touches[0].clientX < 24) dragStartX = e.touches[0].clientX;
}, { passive: true });
document.addEventListener("touchmove", (e) => {
    if (dragStartX !== null && e.touches[0].clientX - dragStartX > 50) { openDrawer(); dragStartX = null; }
}, { passive: true });
document.addEventListener("touchend", () => { dragStartX = null; });

// ── Conversation list ─────────────────────────────────────────────────────────
const AVATAR_GRADIENTS = [
    ["#FF52A2", "#ff8cc8"],
    ["#6366f1", "#a5b4fc"],
    ["#10b981", "#6ee7b7"],
    ["#f59e0b", "#fcd34d"],
    ["#ef4444", "#fca5a5"],
    ["#8b5cf6", "#c4b5fd"],
    ["#0ea5e9", "#7dd3fc"],
];

function avatarGradient(id) {
    const [a, b] = AVATAR_GRADIENTS[id % AVATAR_GRADIENTS.length];
    return `linear-gradient(135deg, ${a}, ${b})`;
}

function formatTime(iso) {
    const d    = new Date(iso);
    const now  = new Date();
    const diff = Math.floor((now - d) / 86400000);
    if (diff === 0) return d.toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });
    if (diff === 1) return "wczoraj";
    if (diff < 7)  return d.toLocaleDateString("pl-PL", { weekday: "long" });
    return d.toLocaleDateString("pl-PL", { day: "numeric", month: "short" });
}

function groupConversations(convs) {
    const groups = [
        { label: "Dzisiaj",     items: [] },
        { label: "Wczoraj",     items: [] },
        { label: "Ten tydzień", items: [] },
        { label: "Wcześniej",   items: [] },
    ];
    const now = new Date();
    for (const c of convs) {
        const diff = Math.floor((now - new Date(c.created_at)) / 86400000);
        if      (diff === 0) groups[0].items.push(c);
        else if (diff === 1) groups[1].items.push(c);
        else if (diff < 7)  groups[2].items.push(c);
        else                groups[3].items.push(c);
    }
    return groups.filter(g => g.items.length > 0);
}

function memoryDotsHtml(count) {
    const filled = Math.min(count, 5);
    return '<div class="conv-dots">' +
        Array.from({ length: 5 }, (_, i) =>
            `<div class="conv-dot ${i < filled ? "filled" : ""}"></div>`
        ).join("") +
        '</div>';
}

async function loadConversations() {
    convList.innerHTML = '<div class="conv-empty">Ładowanie...</div>';
    try {
        const res  = await fetch("/conversations/");
        const data = await res.json();
        renderConversations(data.conversations);
    } catch {
        convList.innerHTML = '<div class="conv-empty">Błąd ładowania</div>';
    }
}

function renderConversations(convs) {
    if (!convs.length) {
        convList.innerHTML = '<div class="conv-empty">Brak rozmów.<br>Zacznij mówić!</div>';
        return;
    }

    const groups = groupConversations(convs);
    let html  = "";
    let index = 0;

    for (const group of groups) {
        html += `<div class="conv-group-label">${group.label}</div>`;
        for (const c of group.items) {
            const preview     = c.preview || "Pusta rozmowa";
            const activeClass = c.active ? " active" : "";
            html += `
                <div class="conv-item${activeClass}" data-id="${c.id}" style="--delay:${index * 45}ms">
                    <div class="conv-avatar" style="background:${avatarGradient(c.id)}">#${c.id}</div>
                    <div class="conv-info">
                        <div class="conv-time">${formatTime(c.created_at)}</div>
                        <div class="conv-preview">${preview}</div>
                    </div>
                    ${memoryDotsHtml(c.message_count)}
                    <button class="conv-delete-btn" data-id="${c.id}" title="Usuń rozmowę">
                        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
                            <path d="M3 4h10M6.5 4V2.5h3V4M4.5 4l.6 9a1 1 0 0 0 1 .9h3.8a1 1 0 0 0 1-.9l.6-9"/>
                        </svg>
                    </button>
                </div>`;
            index++;
        }
    }

    convList.innerHTML = html;
    convList.querySelectorAll(".conv-item").forEach(el => {
        el.addEventListener("click", () => switchConversation(parseInt(el.dataset.id)));
    });
    convList.querySelectorAll(".conv-delete-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            deleteConversation(parseInt(btn.dataset.id));
        });
    });
}

async function deleteConversation(id) {
    if (!confirm("Usunąć tę rozmowę?")) return;

    try {
        const res = await fetch(`/conversations/${id}/delete/`, {
            method:  "POST",
            headers: { "X-CSRFToken": getCookie("csrftoken") },
        });
        if (!res.ok) throw new Error(`delete failed: ${res.status}`);

        const wasActive = convList
            .querySelector(`.conv-item[data-id="${id}"]`)
            ?.classList.contains("active");

        await loadConversations();

        if (wasActive) {
            messagesEl.innerHTML = "";
            appendBotMessage('Cześć. Jestem Train<strong>.me</strong>. Słucham cię — im więcej mówisz, tym bardziej staję się tobą.');
        }
    } catch (err) {
        console.error("Błąd usuwania rozmowy:", err);
    }
}

async function switchConversation(id) {
    try {
        const res  = await fetch(`/conversations/${id}/messages/`);
        const data = await res.json();

        messagesEl.innerHTML = "";
        appendBotMessage('Cześć. Jestem Train<strong>.me</strong>. Słucham cię — im więcej mówisz, tym bardziej staję się tobą.');

        for (const msg of data.messages) {
            if (msg.from_user) {
                appendUserMessage(msg.text, msg.audio_url || null);
            } else {
                appendBotMessage(msg.text);
            }
        }

        closeDrawer();
    } catch (err) {
        console.error("Błąd ładowania rozmowy:", err);
    }
}

newConvBtn.addEventListener("click", async () => {
    if (idleConversationTimer) { clearTimeout(idleConversationTimer); idleConversationTimer = null; }
    await fetch("/conversations/new/", {
        method:  "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    });
    messagesEl.innerHTML = "";
    appendBotMessage('Cześć. Jestem Train<strong>.me</strong>. Słucham cię — im więcej mówisz, tym bardziej staję się tobą.');
    closeDrawer();
});

// ── Account dropdown ─────────────────────────────────────────────────────────
let accountOpen = false;

accountBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    accountOpen = !accountOpen;
    accountDropdown.classList.toggle("open", accountOpen);
    if (drawerOpen) closeDrawer();
});

document.addEventListener("click", () => {
    if (accountOpen) {
        accountOpen = false;
        accountDropdown.classList.remove("open");
    }
});

accountDropdown.addEventListener("click", (e) => e.stopPropagation());

// ── Utils ─────────────────────────────────────────────────────────────────────
function getCookie(name) {
    for (const c of document.cookie.split(";")) {
        const t = c.trim();
        if (t.startsWith(name + "=")) return decodeURIComponent(t.slice(name.length + 1));
    }
    return null;
}

function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(",")[1]);
        reader.onerror   = reject;
        reader.readAsDataURL(blob);
    });
}
