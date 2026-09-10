"""Email verification code retrieval via IMAP.

Used when an external ATS requires email verification during account creation.
Reads the candidate's mailbox over IMAP (stdlib only), finds the most recent
verification email, and extracts a numeric/alphanumeric code or a confirmation
link. Never stores the password in config files — it is read from .env at call
time via config.settings.
"""
import email
import imaplib
import logging
import re
import time
from email.header import decode_header
from typing import Optional, Tuple, List

from config.settings import settings

logger = logging.getLogger("EmailVerification")


def _decode_header_value(value) -> str:
    if value is None:
        return ""
    parts = decode_header(str(value))
    out = []
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(charset or "utf-8", errors="ignore"))
            except Exception:
                out.append(text.decode("utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def _extract_body(msg) -> str:
    """Return a concatenated plain-text body of the message."""
    bodies = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    bodies.append(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
                except Exception:
                    try:
                        bodies.append(part.get_payload(decode=True).decode("latin-1", errors="ignore"))
                    except Exception:
                        pass
            elif ctype == "text/html" and "attachment" not in disp:
                try:
                    html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    # crude tag strip
                    html = re.sub(r"<[^>]+>", " ", html)
                    bodies.append(html)
                except Exception:
                    pass
    else:
        try:
            bodies.append(msg.get_payload(decode=True).decode("utf-8", errors="ignore"))
        except Exception:
            bodies.append(str(msg.get_payload()))
    return "\n".join(bodies)


class EmailVerifier:
    """Poll the mailbox for a verification code / link.

    Reads its configuration from environment variables first (EMAIL_IMAP_*),
    falling back to config.settings.email_verification. This is required
    because pydantic-settings does not map env vars onto nested models.
    """

    def __init__(self):
        self.cfg = settings.email_verification

    def _get(self, env_key: str, cfg_attr: str, default: str = ""):
        import os
        return os.getenv(env_key) or getattr(self.cfg, cfg_attr) or default

    @property
    def is_configured(self) -> bool:
        import os
        host = self._get("EMAIL_IMAP_HOST", "imap_host")
        email_addr = self._get("EMAIL_IMAP_USERNAME", "username") or self._get("EMAIL_IMAP_USERNAME", "email")
        if not email_addr:
            email_addr = self.cfg.email
        password = self._get("EMAIL_IMAP_PASSWORD", "password")
        enabled = (self._get("EMAIL_VERIFICATION_ENABLED", "enabled", "false").lower() in ("1", "true", "yes", "on"))
        return bool(host and email_addr and password and (enabled or self.cfg.enabled))

    def _credentials(self):
        import os
        host = self._get("EMAIL_IMAP_HOST", "imap_host")
        username = self._get("EMAIL_IMAP_USERNAME", "username") or self._get("EMAIL_IMAP_USERNAME", "email")
        if not username:
            username = self.cfg.email
        password = self._get("EMAIL_IMAP_PASSWORD", "password") or os.getenv("EMAIL_IMAP_PASSWORD", "")
        return host, username, password

    def _connect(self):
        host, username, password = self._credentials()
        if not password:
            raise RuntimeError("EMAIL_IMAP_PASSWORD non défini — impossible de lire la boîte mail.")
        mail = imaplib.IMAP4_SSL(host or self.cfg.imap_host, self.cfg.imap_port)
        mail.login(username, password)
        return mail

    def fetch_recent(self, limit: int = 10) -> List[Tuple[str, str, str]]:
        """Return list of (subject, sender, body) for recent inbox messages."""
        mail = self._connect()
        try:
            mail.select("INBOX")
            status, data = mail.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                return []
            ids = data[0].split()
            # newest last
            ids = ids[-limit:]
            results = []
            for num in reversed(ids):
                try:
                    st, msg_data = mail.fetch(num, "(RFC822)")
                    if st != "OK" or not msg_data or not msg_data[0]:
                        continue
                    raw = msg_data[0][1]
                    if isinstance(raw, tuple):
                        raw = raw[1]
                    msg = email.message_from_bytes(bytes(raw))
                    subject = _decode_header_value(msg.get("Subject"))
                    sender = _decode_header_value(msg.get("From"))
                    body = _extract_body(msg)
                    results.append((subject, sender, body))
                except Exception as e:
                    logger.debug(f"fetch error: {e}")
            return results
        finally:
            try:
                mail.logout()
            except Exception:
                pass

    def extract_code(self, body: str, subject: str = "") -> Optional[str]:
        """Extract a verification code from the message text.

        Prioritizes explicit 'code' labels, then common 4-8 digit tokens,
        then 6-char alphanumeric tokens. Returns None if nothing found.
        """
        blob = f"{subject}\n{body}"
        # 1. Explicit patterns: "code: 123456", "code is 123456", "code 123456"
        patterns = [
            r"(?:code|code de v[ée]rification|verification code|one-time|otp|pin)\s*[:：]?\s*([A-Za-z0-9]{4,10})",
            r"\b(\d{6})\b",
            r"\b(\d{4})\b",
        ]
        for pat in patterns:
            m = re.search(pat, blob, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def extract_confirmation_link(self, body: str) -> Optional[str]:
        """Extract an https confirmation link from the message body."""
        m = re.search(r'https?://[^\s"\'<>]+(?:verify|confirm|activate|valider|confirmation)[^\s"\'<>]*', body, re.IGNORECASE)
        if m:
            return m.group(0)
        return None

    def wait_for_code(self, timeout_seconds: Optional[int] = None) -> Optional[str]:
        """Poll the inbox until a verification code appears (or timeout)."""
        timeout = timeout_seconds or self.cfg.code_timeout_seconds
        deadline = time.time() + timeout
        poll_interval = 10.0
        logger.info(f"Waiting up to {timeout}s for a verification email…")
        seen_first = None
        while time.time() < deadline:
            recent = self.fetch_recent(limit=6)
            for subject, sender, body in recent:
                code = self.extract_code(body, subject)
                if code:
                    return code
                link = self.extract_confirmation_link(body)
                if link:
                    return link
            if seen_first is None and recent:
                seen_first = recent[0][0]
            time.sleep(poll_interval)
        return None


email_verifier = EmailVerifier()
