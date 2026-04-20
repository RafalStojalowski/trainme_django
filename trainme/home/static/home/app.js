const startBtn = document.getElementById("startBtn");
const output = document.getElementById("output");
const statusText = document.getElementById("status");

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition;
let isListening = false;
let mediaRecorder;
let audioChunks = [];
let audioContext;
let mediaStream;
let finalTranscription = "";

// Audio recording setup
async function setupAudioRecording() {
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        mediaRecorder = new MediaRecorder(mediaStream);
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        console.log("✅ Audio recording setup complete");
    } catch (error) {
        console.error("❌ Audio setup error:", error);
        statusText.textContent = "Błąd: Brak dostępu do mikrofonu";
    }
}

// Initialize audio recording setup
setupAudioRecording();

if (!SpeechRecognition) {
    alert("Twoja przeglądarka nie wspiera rozpoznawania mowy");
} else {
    recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "pl-PL";
    recognition.maxAlternatives = 1;

    startBtn.onclick = () => {
        console.log("KLIK");

        if (!isListening) {
            finalTranscription = "";
            audioChunks = [];
            recognition.start();
            if (mediaRecorder) {
                mediaRecorder.start();
                console.log("🎙️ Recording started");
            }
        } else {
            recognition.stop();
            if (mediaRecorder && mediaRecorder.state !== "inactive") {
                mediaRecorder.stop();
                console.log("🛑 Recording stopped");
            }
        }
    };

    recognition.onstart = () => {
        console.log("🎤 START");

        isListening = true;
        startBtn.textContent = "Stop";
        startBtn.classList.add("listening");
        statusText.innerHTML = "Nasłuchiwanie <span class='pulse'></span>";
    };

    recognition.onresult = (event) => {
        let final = "";
        let interim = "";

        // Only process results from the current event to avoid duplicates
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                final += event.results[i][0].transcript + " ";
                finalTranscription += event.results[i][0].transcript + " ";
            } else {
                interim += event.results[i][0].transcript;
            }
        }

        output.innerHTML = final + "<span style='opacity:0.5'>" + interim + "</span>";

        if (final.trim() !== "") {
            console.log("Final:", final);
        }
    };

    recognition.onerror = (event) => {
        console.error("❌ ERROR:", event.error);
        statusText.textContent = "Błąd: " + event.error;
    };

    recognition.onend = async () => {
        console.log("🛑 END");

        isListening = false;
        startBtn.textContent = "Start Talking";
        startBtn.classList.remove("listening");
        statusText.textContent = "Kliknij i zacznij mówić";
        
        // Send final transcription with audio
        if (finalTranscription.trim() !== "") {
            // Convert audio to WAV and send
            await sendFinalTranscription(finalTranscription.trim());
        }
    };
}

async function sendFinalTranscription(text) {
    console.log("📤 Sending final transcription...");
    console.log("📝 Text:", text);
    
    try {
        // Convert audio blob to base64
        let audioBase64 = null;
        if (audioChunks.length > 0) {
            console.log(`🎵 Converting ${audioChunks.length} audio chunks to WAV...`);
            const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
            console.log(`📦 Audio blob size: ${audioBlob.size} bytes`);
            audioBase64 = await blobToBase64(audioBlob);
            console.log(`✅ Audio converted to base64: ${audioBase64.length} characters`);
        } else {
            console.warn("⚠️ No audio chunks recorded");
        }
        
        const payload = {
            text: text,
            audio: audioBase64,
            is_session_end: true
        };
        console.log("📤 Payload prepared, sending...");
        
        const response = await fetch("/speech/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify(payload)
        });
        
        console.log(`📥 Response status: ${response.status}`);
        const data = await response.json();
        
        if (data.status === "session_complete") {
            statusText.innerHTML = `✅ Sesja ukończona! <br> ID: ${data.transcription_id} <br> Zdań: ${data.sentence_count}`;
            console.log("✅ Session complete:", data);
        } else if (data.status === "error") {
            console.error("❌ Server error:", data.message);
            statusText.textContent = `Błąd serwera: ${data.message}`;
        } else {
            console.warn("⚠️ Unexpected response:", data);
            statusText.textContent = "Błąd: Nieznana odpowiedź serwera";
        }
    } catch (error) {
        console.error("❌ Error sending transcription:", error);
        statusText.textContent = `Błąd: ${error.message || 'Nie udało się wysłać transkrypcji'}`;
    }
}

function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");

        for (let cookie of cookies) {
            cookie = cookie.trim();

            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }

    return cookieValue;
}

// Convert Blob to Base64
function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
            const base64 = reader.result.split(",")[1];
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}
