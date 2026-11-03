import os
import sys

# Configura encoding do console para evitar erros no Windows cp1252
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from email_monitor import DisneyEmailMonitor

# Carrega variáveis do arquivo .env
load_dotenv(override=True)

app = Flask(__name__)

# Configurações do ambiente
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
CODE_EXPIRATION_MINUTES = int(os.getenv("CODE_EXPIRATION_MINUTES", "15"))

# Instância do monitor
monitor = DisneyEmailMonitor(
    imap_server=IMAP_SERVER,
    imap_port=IMAP_PORT,
    email_user=EMAIL_USER,
    email_pass=EMAIL_PASS,
    poll_interval=POLL_INTERVAL,
    expiration_minutes=CODE_EXPIRATION_MINUTES,
    storage_file="data/saved_codes.json"
)

# Inicia thread em background
monitor.start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def get_status():
    status = monitor.get_status()
    return jsonify(status)


@app.route("/api/check-now", methods=["POST"])
def check_now():
    """Solicita verificação respeitando intervalo mínimo de segurança (cooldown de 8s)."""
    should_check = True
    if monitor.last_checked_at:
        try:
            last_dt = datetime.fromisoformat(monitor.last_checked_at)
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < 8:
                should_check = False
        except Exception:
            pass

    if should_check:
        monitor.check_emails()

    return jsonify({
        "status": monitor.get_status()
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[INFO] Servidor ConectaEmail iniciado na porta {port}")
    print(f"[INFO] Acesse no seu navegador: http://localhost:{port}")
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    finally:
        monitor.stop()
