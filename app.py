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
    """Força uma verificação imediata dos e-mails."""
    result = monitor.check_emails()
    status = monitor.get_status()
    return jsonify({
        "result": result,
        "status": status
    })


@app.route("/api/reload-env", methods=["POST"])
def reload_env():
    """Recarrega as credenciais do arquivo .env sem reiniciar o servidor."""
    load_dotenv(override=True)
    new_user = os.getenv("EMAIL_USER", "")
    new_pass = os.getenv("EMAIL_PASS", "")
    monitor.update_credentials(new_user, new_pass)
    result = monitor.check_emails()
    return jsonify({
        "success": True,
        "message": "Configurações recarregadas com sucesso do .env!",
        "configured": monitor.is_configured(),
        "check_result": result
    })


@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    """Limpa o código ativo e o histórico."""
    with monitor.lock:
        monitor.active_code = None
        monitor.code_history = []
        monitor._save_storage()
    return jsonify({
        "success": True,
        "message": "Histórico e códigos limpos com sucesso!"
    })


@app.route("/api/simulate-code", methods=["POST"])
def simulate_code():
    """
    Endpoint para testar e demonstrar o funcionamento do sistema
    sem precisar esperar um código real da Disney.
    """
    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(minutes=monitor.expiration_minutes)
    
    # Gera um código de demonstração
    import random
    sample_code = f"{random.randint(100000, 999999)}"
    
    simulated_info = {
        "code": sample_code,
        "sender": "disneyplus@mail.disneyplus.com",
        "subject": "Seu código de acesso único da Disney+ (Simulação)",
        "received_at": now_utc.isoformat(),
        "received_at_formatted": now_utc.strftime("%d/%m/%Y %H:%M:%S UTC"),
        "expires_at": expires_at.isoformat(),
        "time_left_seconds": monitor.expiration_minutes * 60,
        "is_expired": False,
        "detected_at": now_utc.isoformat(),
        "is_simulated": True
    }

    with monitor.lock:
        monitor.active_code = simulated_info
        monitor.code_history.insert(0, simulated_info)
        monitor.code_history = monitor.code_history[:20]
        monitor._save_storage()

    return jsonify({
        "success": True,
        "message": f"Código simulado {sample_code} criado com sucesso!",
        "code": simulated_info
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"[INFO] Servidor ConectaEmail iniciado na porta {port}")
    print(f"[INFO] Acesse no seu navegador: http://localhost:{port}")
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    finally:
        monitor.stop()
