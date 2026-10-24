/**
 * ConectaEmail - Disney+ Code Stream Frontend Controller (Modo Simplificado)
 */

// Estado da Aplicação
const state = {
    soundEnabled: localStorage.getItem("disney_sound_enabled") !== "false",
    lastKnownCode: null,
    activeCode: null,
    countdownInterval: null,
    pollInterval: null,
    audioContext: null
};

// Elementos DOM
const dom = {
    // Header
    btnSoundToggle: document.getElementById("btnSoundToggle"),
    soundIcon: document.getElementById("soundIcon"),

    // Hero Section
    heroStatusTitle: document.getElementById("heroStatusTitle"),

    // State 1: Active Code
    activeCodeContainer: document.getElementById("activeCodeContainer"),
    timerBarFill: document.getElementById("timerBarFill"),
    countdownDisplay: document.getElementById("countdownDisplay"),
    expirationTimeText: document.getElementById("expirationTimeText"),
    btnCopyCode: document.getElementById("btnCopyCode"),
    copyIcon: document.getElementById("copyIcon"),
    copyText: document.getElementById("copyText"),
    metaReceivedAt: document.getElementById("metaReceivedAt"),

    // State 2: Expired Code
    expiredCodeContainer: document.getElementById("expiredCodeContainer"),
    btnCopyExpiredCode: document.getElementById("btnCopyExpiredCode"),
    copyExpiredIcon: document.getElementById("copyExpiredIcon"),
    copyExpiredText: document.getElementById("copyExpiredText"),
    expiredReceivedAt: document.getElementById("expiredReceivedAt"),

    // State 3: Waiting / Radar
    waitingContainer: document.getElementById("waitingContainer"),

    // Toast Container
    toastContainer: document.getElementById("toastContainer")
};

// Sintetizador de Som com Web Audio API
function playNotificationChime() {
    if (!state.soundEnabled) return;
    try {
        if (!state.audioContext) {
            state.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (state.audioContext.state === "suspended") {
            state.audioContext.resume();
        }

        const now = state.audioContext.currentTime;

        // Nota 1 (E5)
        const osc1 = state.audioContext.createOscillator();
        const gain1 = state.audioContext.createGain();
        osc1.type = "sine";
        osc1.frequency.setValueAtTime(659.25, now);
        gain1.gain.setValueAtTime(0.18, now);
        gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
        osc1.connect(gain1);
        gain1.connect(state.audioContext.destination);
        osc1.start(now);
        osc1.stop(now + 0.6);

        // Nota 2 (G#5)
        const osc2 = state.audioContext.createOscillator();
        const gain2 = state.audioContext.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(830.61, now + 0.12);
        gain2.gain.setValueAtTime(0.2, now + 0.12);
        gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.9);
        osc2.connect(gain2);
        gain2.connect(state.audioContext.destination);
        osc2.start(now + 0.12);
        osc2.stop(now + 0.9);

        // Nota 3 (B5 - Disney magic spark)
        const osc3 = state.audioContext.createOscillator();
        const gain3 = state.audioContext.createGain();
        osc3.type = "sine";
        osc3.frequency.setValueAtTime(987.77, now + 0.24);
        gain3.gain.setValueAtTime(0.22, now + 0.24);
        gain3.gain.exponentialRampToValueAtTime(0.001, now + 1.2);
        osc3.connect(gain3);
        gain3.connect(state.audioContext.destination);
        osc3.start(now + 0.24);
        osc3.stop(now + 1.2);
    } catch (e) {
        console.warn("Audio chime error:", e);
    }
}

// Toasts
function showToast(message, type = "info") {
    if (!dom.toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let icon = "fa-circle-info";
    if (type === "success") icon = "fa-circle-check";
    if (type === "error") icon = "fa-circle-exclamation";

    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${message}</span>
    `;

    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(100%)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Formatação de Tempo Restante MM:SS
function formatTime(seconds) {
    if (seconds <= 0) return "00:00";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// Formatação de Hora
function formatLocalTime(isoString) {
    if (!isoString) return "--:--";
    try {
        const d = new Date(isoString);
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
        return "--:--";
    }
}

// Atualização dos Dígitos na Tela
function renderDigits(codeStr, prefix = "digit-") {
    const clean = String(codeStr || "------").padEnd(6, "-");
    for (let i = 0; i < 6; i++) {
        const el = document.getElementById(`${prefix}${i}`);
        if (el) {
            el.textContent = clean[i] || "-";
        }
    }
}

// Inicia o Contador Local de 1 Segundo
function startCountdown(totalSeconds, maxWindowSeconds = 900) {
    if (state.countdownInterval) {
        clearInterval(state.countdownInterval);
    }

    let remaining = totalSeconds;

    const tick = () => {
        if (remaining <= 0) {
            clearInterval(state.countdownInterval);
            transitionToState("expired");
            return;
        }

        if (dom.countdownDisplay) {
            dom.countdownDisplay.textContent = formatTime(remaining);
        }

        // Barra de progresso (calculada em cima do tempo máximo, padrão 15 min = 900s)
        const pct = Math.max(0, Math.min(100, (remaining / maxWindowSeconds) * 100));
        if (dom.timerBarFill) {
            dom.timerBarFill.style.width = `${pct}%`;

            if (remaining <= 120) {
                dom.timerBarFill.classList.add("warning");
                dom.countdownDisplay.classList.add("warning");
            } else {
                dom.timerBarFill.classList.remove("warning");
                dom.countdownDisplay.classList.remove("warning");
            }
        }

        remaining--;
    };

    tick();
    state.countdownInterval = setInterval(tick, 1000);
}

// Transição entre os 3 estados visuais
function transitionToState(view) {
    if (dom.activeCodeContainer) dom.activeCodeContainer.classList.add("hidden");
    if (dom.expiredCodeContainer) dom.expiredCodeContainer.classList.add("hidden");
    if (dom.waitingContainer) dom.waitingContainer.classList.add("hidden");

    if (view === "active") {
        if (dom.activeCodeContainer) dom.activeCodeContainer.classList.remove("hidden");
        if (dom.heroStatusTitle) dom.heroStatusTitle.textContent = "Código Detectado";
    } else if (view === "expired") {
        if (dom.expiredCodeContainer) dom.expiredCodeContainer.classList.remove("hidden");
        if (dom.heroStatusTitle) dom.heroStatusTitle.textContent = "Código Expirado";
    } else {
        if (dom.waitingContainer) dom.waitingContainer.classList.remove("hidden");
        if (dom.heroStatusTitle) dom.heroStatusTitle.textContent = "Aguardando Código";
    }
}

// Processa a resposta da API de Status
function handleStatusData(data) {
    const active = data.active_code;
    const expirationSeconds = (data.expiration_minutes || 15) * 60;

    if (active && active.code) {
        // Verifica se é um código recém-chegado (tocar alerta sonoro)
        if (state.lastKnownCode !== active.code) {
            state.lastKnownCode = active.code;
            playNotificationChime();
            showToast(`✨ Novo código recebido: ${active.code}`, "success");
        }

        if (active.time_left_seconds > 0 && !active.is_expired) {
            // Código Válido e Ativo!
            transitionToState("active");
            renderDigits(active.code, "digit-");
            startCountdown(active.time_left_seconds, expirationSeconds);

            if (dom.metaReceivedAt) {
                dom.metaReceivedAt.textContent = formatLocalTime(active.received_at);
            }
            if (dom.expirationTimeText) {
                dom.expirationTimeText.textContent = `Válido até ${formatLocalTime(active.expires_at)}`;
            }
        } else {
            // Código Expirado
            transitionToState("expired");
            renderDigits(active.code, "expired-digit-");
            if (dom.expiredReceivedAt) {
                dom.expiredReceivedAt.textContent = formatLocalTime(active.received_at);
            }
            if (state.countdownInterval) clearInterval(state.countdownInterval);
        }
    } else {
        // Aguardando novo código
        transitionToState("waiting");
        if (state.countdownInterval) clearInterval(state.countdownInterval);
    }
}

// Busca o status do servidor
async function fetchStatus() {
    try {
        const response = await fetch("/api/status");
        if (!response.ok) throw new Error("Falha na comunicação");
        const data = await response.json();
        handleStatusData(data);
    } catch (err) {
        console.error("Erro ao buscar status:", err);
    }
}

// Copia o código atual para a área de transferência
function copyCodeToClipboard(isExpired = false) {
    let code = "";
    const prefix = isExpired ? "expired-digit-" : "digit-";
    for (let i = 0; i < 6; i++) {
        const el = document.getElementById(`${prefix}${i}`);
        if (el && el.textContent !== "-") {
            code += el.textContent;
        }
    }

    // Fallback se não achou no prefixo tentado
    if (!code || code.length < 6) {
        const altPrefix = isExpired ? "digit-" : "expired-digit-";
        code = "";
        for (let i = 0; i < 6; i++) {
            const el = document.getElementById(`${altPrefix}${i}`);
            if (el && el.textContent !== "-") {
                code += el.textContent;
            }
        }
    }

    if (!code || code.length < 6) return;

    navigator.clipboard.writeText(code).then(() => {
        const btn = isExpired ? dom.btnCopyExpiredCode : dom.btnCopyCode;
        const icon = isExpired ? dom.copyExpiredIcon : dom.copyIcon;
        const text = isExpired ? dom.copyExpiredText : dom.copyText;

        if (btn) btn.classList.add("copied");
        if (icon) icon.className = "fa-solid fa-check";
        if (text) text.textContent = "Copiado com Sucesso!";
        showToast(`Código ${code} copiado!`, "success");

        setTimeout(() => {
            if (btn) btn.classList.remove("copied");
            if (icon) icon.className = "fa-regular fa-copy";
            if (text) text.textContent = isExpired ? "Copiar Código Anterior" : "Copiar Código";
        }, 2200);
    }).catch(err => {
        console.error("Erro ao copiar:", err);
        showToast("Não foi possível copiar automaticamente.", "error");
    });
}

// Alterna Som
function toggleSound() {
    state.soundEnabled = !state.soundEnabled;
    localStorage.setItem("xandmails_sound_enabled", state.soundEnabled);
    updateSoundButton();
    if (state.soundEnabled) {
        playNotificationChime();
        showToast("Som ativado", "info");
    } else {
        showToast("Som desativado", "info");
    }
}

function updateSoundButton() {
    if (!dom.soundIcon || !dom.btnSoundToggle) return;
    if (state.soundEnabled) {
        dom.soundIcon.className = "fa-solid fa-volume-high";
        dom.btnSoundToggle.classList.add("active");
    } else {
        dom.soundIcon.className = "fa-solid fa-volume-xmark";
        dom.btnSoundToggle.classList.remove("active");
    }
}

// Event Listeners
function setupEvents() {
    if (dom.btnCopyCode) dom.btnCopyCode.addEventListener("click", () => copyCodeToClipboard(false));
    if (dom.btnCopyExpiredCode) dom.btnCopyExpiredCode.addEventListener("click", () => copyCodeToClipboard(true));
    if (dom.btnSoundToggle) dom.btnSoundToggle.addEventListener("click", toggleSound);
}

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
    updateSoundButton();
    setupEvents();
    fetchStatus();

    // Consulta periódica em segundo plano (a cada 3 segundos)
    state.pollInterval = setInterval(fetchStatus, 3000);
});
