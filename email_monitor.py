import email
import email.header
import email.message
import email.utils
import imaplib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DisneyEmailMonitor")


def decode_mime_header(header_value: str) -> str:
    """Decodifica cabeçalhos de e-mail com múltiplos charsets (RFC 2047)."""
    if not header_value:
        return ""
    try:
        decoded_slices = email.header.decode_header(header_value)
        result = []
        for content, encoding in decoded_slices:
            if isinstance(content, bytes):
                encoding = encoding or "utf-8"
                try:
                    result.append(content.decode(encoding, errors="replace"))
                except Exception:
                    result.append(content.decode("latin1", errors="replace"))
            else:
                result.append(str(content))
        return "".join(result)
    except Exception as e:
        logger.debug(f"Erro ao decodificar cabeçalho: {e}")
        return str(header_value)


def extract_email_body(msg: email.message.Message) -> tuple[str, str]:
    """Retorna o corpo em texto puro e em HTML."""
    plain_text = ""
    html_text = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                charset = part.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace")
                except Exception:
                    decoded = payload.decode("latin1", errors="replace")

                if content_type == "text/plain":
                    plain_text += "\n" + decoded
                elif content_type == "text/html":
                    html_text += "\n" + decoded
            except Exception as e:
                logger.debug(f"Erro ao extrair parte do e-mail: {e}")
    else:
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                try:
                    decoded = payload.decode(charset, errors="replace")
                except Exception:
                    decoded = payload.decode("latin1", errors="replace")

                if msg.get_content_type() == "text/html":
                    html_text = decoded
                else:
                    plain_text = decoded
        except Exception as e:
            logger.debug(f"Erro ao extrair payload único: {e}")

    return plain_text.strip(), html_text.strip()


def extract_disney_code(plain_text: str, html_text: str, subject: str = "") -> str | None:
    """
    Extrai o código de 6 dígitos enviado pela Disney/Disney+.
    Prioriza contexto de palavras-chave como 'código', 'passcode', etc.
    """
    full_text = f"{subject}\n{plain_text}"

    # Se temos HTML, podemos extrair texto limpo com BeautifulSoup
    if html_text:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            # Tenta encontrar tags de destaque (ex: td, div, h1, span com números de 6 dígitos)
            for tag in soup.find_all(["h1", "h2", "h3", "b", "strong", "span", "td", "div"]):
                tag_text = tag.get_text().strip()
                if re.fullmatch(r"\d{6}", tag_text):
                    return tag_text
            clean_html_text = soup.get_text(separator=" ")
            full_text += f"\n{clean_html_text}"
        except Exception as e:
            logger.debug(f"Erro ao parsear HTML: {e}")

    # Regex 1: Código após palavras-chave conhecidas (português e inglês)
    keyword_patterns = [
        r"(?:código(?:\s+de\s+(?:acesso|uso|segurança|verificação))?(?:\s+único)?|passcode|one-time passcode|verification code)[^\d\w]{1,40}(\d{6})\b",
        r"(\d{6})\s+(?:é\s+o\s+seu\s+código|is\s+your\s+code|is\s+your\s+passcode)",
        r"(?:seu\s+código(?:\s+é)?|your\s+code\s+is)[\s:\r\n]+(\d{6})\b",
    ]

    for pattern in keyword_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1)

    # Regex 2: Qualquer sequência de 6 dígitos isolados
    all_6_digits = re.findall(r"\b(\d{6})\b", full_text)
    if all_6_digits:
        return all_6_digits[0]

    return None


class DisneyEmailMonitor:
    def __init__(
        self,
        imap_server: str = "imap.gmail.com",
        imap_port: int = 993,
        email_user: str = "",
        email_pass: str = "",
        poll_interval: int = 10,
        expiration_minutes: int = 15,
        storage_file: str = "data/saved_codes.json"
    ):
        self.imap_server = imap_server
        self.imap_port = int(imap_port)
        self.email_user = email_user.strip()
        self.email_pass = email_pass.strip().replace(" ", "")  # Senha de app do Gmail pode vir com espaços
        self.poll_interval = max(5, int(poll_interval))
        self.expiration_minutes = int(expiration_minutes)
        self.storage_file = storage_file

        self.lock = threading.Lock()
        self.running = False
        self.thread = None

        # Estado
        self.is_connected = False
        self.last_checked_at = None
        self.last_error = None
        self.active_code = None
        self.code_history = []

        self._load_storage()

    def update_credentials(self, email_user: str, email_pass: str):
        """Atualiza credenciais em tempo de execução."""
        with self.lock:
            self.email_user = email_user.strip()
            self.email_pass = email_pass.strip().replace(" ", "")
            self.last_error = None

    def is_configured(self) -> bool:
        return bool(self.email_user and self.email_pass and "@" in self.email_user)

    def _load_storage(self):
        """Carrega códigos salvos para persistência."""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active_code = data.get("active_code")
                    self.code_history = data.get("code_history", [])
                    # Recalcula status do active_code
                    self._refresh_active_code_status()
        except Exception as e:
            logger.warning(f"Erro ao carregar storage: {e}")

    def _save_storage(self):
        """Salva códigos no arquivo JSON."""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump({
                    "active_code": self.active_code,
                    "code_history": self.code_history[:20]
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Erro ao salvar storage: {e}")

    def _refresh_active_code_status(self):
        """Calcula se o código ativo ainda é válido com base na expiração."""
        if not self.active_code:
            return

        expires_at_iso = self.active_code.get("expires_at")
        if not expires_at_iso:
            self.active_code = None
            return

        try:
            expires_at = datetime.fromisoformat(expires_at_iso)
            now = datetime.now(timezone.utc)
            seconds_left = int((expires_at - now).total_seconds())

            if seconds_left > 0:
                self.active_code["time_left_seconds"] = seconds_left
                self.active_code["is_expired"] = False
            else:
                self.active_code["time_left_seconds"] = 0
                self.active_code["is_expired"] = True
        except Exception as e:
            logger.debug(f"Erro ao calcular tempo restante: {e}")

    def check_emails(self) -> dict:
        """
        Conecta ao servidor IMAP e procura e-mails recentes da Disney.
        Retorna o status da verificação.
        """
        if not self.is_configured():
            with self.lock:
                self.is_connected = False
                self.last_error = "Credenciais não configuradas. Preencha o arquivo .env com seu e-mail e senha de app."
            return {"success": False, "message": self.last_error}

        now_utc = datetime.now(timezone.utc)
        mail = None

        try:
            logger.info(f"Conectando a {self.imap_server}:{self.imap_port}...")
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, timeout=15)
            mail.login(self.email_user, self.email_pass)

            with self.lock:
                self.is_connected = True
                self.last_error = None

            # Seleciona INBOX em modo somente leitura (para não marcar como lido nem apagar nada)
            mail.select("INBOX", readonly=True)

            # 1. Pega os últimos 60 e-mails do INBOX diretamente
            status, all_messages = mail.search(None, "ALL")
            candidate_ids = set()
            if status == "OK" and all_messages[0]:
                for mid in all_messages[0].split()[-60:]:
                    try:
                        candidate_ids.add(int(mid))
                    except ValueError:
                        pass

            # 2. Também faz buscas direcionadas por termos específicos
            for term in ['(FROM "disney")', '(FROM "disneyplus")', '(SUBJECT "código")', '(SUBJECT "passcode")']:
                try:
                    s, m = mail.search(None, term)
                    if s == "OK" and m[0]:
                        for mid in m[0].split()[-25:]:
                            try:
                                candidate_ids.add(int(mid))
                            except ValueError:
                                pass
                except Exception:
                    pass

            # Ordena os IDs numericamente
            sorted_ids = [str(x).encode() for x in sorted(candidate_ids)]
            logger.info(f"Analisando {len(sorted_ids)} e-mails potenciais recentes...")

            found_code = None
            found_email_info = None

            # Analisa do mais recente para o mais antigo
            for msg_id in reversed(sorted_ids):
                try:
                    # Busca rápida apenas dos cabeçalhos para não sobrecarregar
                    res, hdr_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if res != "OK" or not hdr_data or not hdr_data[0]:
                        continue

                    raw_header = hdr_data[0][1]
                    hdr_msg = email.message_from_bytes(raw_header)

                    from_hdr = decode_mime_header(hdr_msg.get("From", ""))
                    subject_hdr = decode_mime_header(hdr_msg.get("Subject", ""))
                    date_hdr = hdr_msg.get("Date", "")

                    # Verifica se o e-mail é da Disney ou de código de acesso
                    is_disney = (
                        "disney" in from_hdr.lower()
                        or "disney" in subject_hdr.lower()
                        or "disneyplus" in from_hdr.lower()
                        or "disneyplus" in subject_hdr.lower()
                        or "código de acesso" in subject_hdr.lower()
                        or "passcode" in subject_hdr.lower()
                    )

                    if not is_disney:
                        continue

                    # Converte a data do e-mail
                    email_dt_utc = None
                    try:
                        parsed_date = email.utils.parsedate_to_datetime(date_hdr)
                        if parsed_date.tzinfo is None:
                            email_dt_utc = parsed_date.replace(tzinfo=timezone.utc)
                        else:
                            email_dt_utc = parsed_date.astimezone(timezone.utc)
                    except Exception:
                        email_dt_utc = now_utc

                    # Baixa o corpo completo para extração do código
                    res, body_data = mail.fetch(msg_id, "(RFC822)")
                    if res != "OK" or not body_data or not body_data[0]:
                        continue

                    full_msg = email.message_from_bytes(body_data[0][1])
                    plain_text, html_text = extract_email_body(full_msg)
                    code = extract_disney_code(plain_text, html_text, subject_hdr)

                    if code:
                        found_code = code
                        # Calcula expiração com base no horário de recebimento do e-mail
                        expires_at = email_dt_utc + timedelta(minutes=self.expiration_minutes)
                        seconds_left = int((expires_at - now_utc).total_seconds())

                        found_email_info = {
                            "code": code,
                            "sender": from_hdr,
                            "subject": subject_hdr,
                            "received_at": email_dt_utc.isoformat(),
                            "received_at_formatted": email_dt_utc.strftime("%d/%m/%Y %H:%M:%S UTC"),
                            "expires_at": expires_at.isoformat(),
                            "time_left_seconds": max(0, seconds_left),
                            "is_expired": seconds_left <= 0,
                            "detected_at": now_utc.isoformat()
                        }
                        # O mais recente encontrado encerra a busca prioritária
                        break
                except Exception as e:
                    logger.warning(f"Erro ao processar e-mail id {msg_id}: {e}")
                    continue

            with self.lock:
                self.last_checked_at = now_utc.isoformat()
                if found_email_info:
                    # Se for um código novo ou atualizado
                    if not self.active_code or self.active_code.get("code") != found_code or self.active_code.get("received_at") != found_email_info["received_at"]:
                        logger.info(f"[NOVO CODIGO] Código Disney detectado: {found_code} (Expira em {found_email_info['time_left_seconds']}s)")
                        self.active_code = found_email_info

                        # Adiciona ao histórico se ainda não estiver
                        history_codes = [h.get("code") for h in self.code_history]
                        if found_code not in history_codes or (self.code_history and self.code_history[0].get("received_at") != found_email_info["received_at"]):
                            self.code_history.insert(0, found_email_info)
                            self.code_history = self.code_history[:20]

                        self._save_storage()
                    else:
                        # Atualiza apenas o tempo restante
                        self.active_code["time_left_seconds"] = found_email_info["time_left_seconds"]
                        self.active_code["is_expired"] = found_email_info["is_expired"]
                else:
                    self._refresh_active_code_status()

            return {
                "success": True,
                "code_found": bool(found_code),
                "code": found_code,
                "message": f"Verificação concluída. {'Código encontrado: ' + found_code if found_code else 'Nenhum novo código nos últimos minutos.'}"
            }

        except imaplib.IMAP4.error as e:
            err_msg = str(e)
            logger.error(f"Erro de autenticação IMAP: {err_msg}")
            friendly_msg = "Falha de autenticação no Gmail. Verifique se a Senha de Aplicativo (16 letras) está correta e se o acesso IMAP está ativado no Gmail."
            with self.lock:
                self.is_connected = False
                self.last_error = friendly_msg
            return {"success": False, "message": friendly_msg, "error": err_msg}

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Erro geral no monitor IMAP: {err_msg}")
            friendly_msg = f"Erro de conexão com o servidor de e-mail: {err_msg}"
            with self.lock:
                self.is_connected = False
                self.last_error = friendly_msg
            return {"success": False, "message": friendly_msg, "error": err_msg}

        finally:
            if mail:
                try:
                    mail.close()
                except Exception:
                    pass
                try:
                    mail.logout()
                except Exception:
                    pass

    def get_status(self) -> dict:
        """Retorna o estado completo para o frontend."""
        self.ensure_running()
        with self.lock:
            self._refresh_active_code_status()
            
            # Mascara o e-mail para exibição segura na tela
            masked_email = ""
            if self.email_user and "@" in self.email_user:
                parts = self.email_user.split("@")
                name = parts[0]
                masked_name = name[:2] + "***" + (name[-1] if len(name) > 2 else "")
                masked_email = f"{masked_name}@{parts[1]}"

            return {
                "configured": self.is_configured(),
                "email_user_masked": masked_email,
                "connected": self.is_connected,
                "last_checked_at": self.last_checked_at,
                "last_error": self.last_error,
                "poll_interval": self.poll_interval,
                "expiration_minutes": self.expiration_minutes,
                "active_code": self.active_code,
                "history": self.code_history
            }

    def _loop(self):
        """Loop de monitoramento em segundo plano."""
        logger.info(f"Iniciando monitoramento automático a cada {self.poll_interval} segundos...")
        while self.running:
            try:
                if self.is_configured():
                    self.check_emails()
                else:
                    with self.lock:
                        self.is_connected = False
                        self.last_error = "Aguardando credenciais válidas no .env"
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {e}")

            # Intervalo de espera
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

    def ensure_running(self):
        """Garante que a thread de monitoramento está ativa no processo worker atual (pós-fork do Gunicorn)."""
        if not self.running or self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            logger.info(f"Thread de monitoramento iniciada no processo PID={os.getpid()}.")

    def start(self):
        """Inicia a thread de monitoramento."""
        self.ensure_running()

    def stop(self):
        """Para a thread de monitoramento."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)
        logger.info("Thread de monitoramento finalizada.")
