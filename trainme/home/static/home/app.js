const startBtn = document.getElementById("startBtn");
const output = document.getElementById("output");
const statusText = document.getElementById("status");

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

let recognition;
let isListening = false;

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
            recognition.start();
        } else {
            recognition.stop();
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

        for (let i = 0; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                final += event.results[i][0].transcript;
            } else {
                interim += event.results[i][0].transcript;
                sendToBackend(interim);
            }
        }

        output.innerHTML = final + "<span style='opacity:0.5'>" + interim + "</span>";

        if (final.trim() !== "") {
            
        }
    };

    recognition.onerror = (event) => {
        console.error("❌ ERROR:", event.error);
        statusText.textContent = "Błąd: " + event.error;
    };

    recognition.onend = () => {
        console.log("🛑 END");

        isListening = false;
        startBtn.textContent = "Start Talking";
        startBtn.classList.remove("listening");
        statusText.textContent = "Kliknij i zacznij mówić";
    };
}


function sendToBackend(text_value) {
    fetch("/speech/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ text: text_value })
    });
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