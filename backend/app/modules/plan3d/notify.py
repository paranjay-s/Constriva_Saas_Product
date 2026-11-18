"""Tell the owner when a long build (Medium, High, Ultra) finishes or fails: one email and
one in-app notification per outcome. The email has no plan contents, only a link to the job,
which needs a sign-in.

Settings (all optional; with no host, the email is written to the log instead of sent):
    EMAIL_SMTP_HOST, EMAIL_SMTP_PORT (587: STARTTLS; 465: TLS), EMAIL_SMTP_USER,
    EMAIL_SMTP_PASSWORD, EMAIL_FROM

Kept in this process: the watched builds (with the owner's address, never stored in a table),
the in-app notifications (the last 50 per user) and the per-user email toggle (on by
default). A restart forgets them: a build that finishes while the API is down is not
announced.
"""

import asyncio
import logging
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage
from functools import lru_cache
from typing import Any, Protocol

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config import settings as app_settings

logger = logging.getLogger("construtiva.plan3d.notify")

LONG_BUILDS = ("medium", "high", "ultra")
POLL_S = 20.0
MAX_EVENTS = 50


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EMAIL_", env_file=("../.env", ".env"), extra="ignore"
    )

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    sender: str = Field("", validation_alias=AliasChoices("EMAIL_FROM", "sender"))


@lru_cache
def email_settings() -> EmailSettings:
    return EmailSettings()


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class LogMailer:
    """No SMTP server set up: the email is logged (without the address in full) instead of sent."""

    def send(self, to: str, subject: str, body: str) -> None:
        masked = to[:2] + "***" + to[to.find("@") :] if "@" in to else "***"
        logger.info("email (not sent, no SMTP set up) to %s: %s | %s", masked, subject, body)


class SmtpMailer:
    def __init__(self, s: EmailSettings) -> None:
        self.s = s

    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.s.sender or self.s.smtp_user, to, subject
        msg.set_content(body)
        context = ssl.create_default_context()
        if self.s.smtp_port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                self.s.smtp_host, 465, context=context, timeout=30
            )
        else:
            server = smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30)
            server.starttls(context=context)
        with server:
            if self.s.smtp_user:
                server.login(self.s.smtp_user, self.s.smtp_password.get_secret_value())
            server.send_message(msg)


_mailer: Mailer | None = None


def get_mailer() -> Mailer:
    global _mailer
    if _mailer is None:
        s = email_settings()
        _mailer = SmtpMailer(s) if s.smtp_host else LogMailer()
    return _mailer


def set_mailer(mailer: Mailer | None) -> None:
    """Tests put a fake mailer here."""
    global _mailer
    _mailer = mailer


@dataclass
class Watch:
    job_id: str
    user_id: str
    email: str
    quality: str


@dataclass
class State:
    watches: dict[str, Watch] = field(default_factory=dict)
    told: set[tuple[str, str]] = field(default_factory=set)  # (job, outcome) already announced
    events: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    email_off: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)
    poller: asyncio.Task | None = None


STATE = State()


def reset() -> None:
    """Forget everything (tests)."""
    global STATE
    STATE = State()


def watch(job_id: str, user_id: str, email: str, quality: str) -> None:
    """A build was started: announce its outcome if it is a long one."""
    if quality not in LONG_BUILDS:
        return
    with STATE.lock:
        STATE.watches[job_id] = Watch(job_id, str(user_id), email or "", quality)
        STATE.told.discard((job_id, "done"))
        STATE.told.discard((job_id, "failed"))


def set_email(user_id: str, on: bool) -> None:
    with STATE.lock:
        (STATE.email_off.discard if on else STATE.email_off.add)(str(user_id))


def email_on(user_id: str) -> bool:
    return str(user_id) not in STATE.email_off


def events(user_id: str) -> list[dict[str, Any]]:
    return list(reversed(STATE.events.get(str(user_id), [])))


def observe(job_id: str, service: dict[str, Any] | None) -> bool:
    """A job's status was seen: announce a finished or failed long build once. True if it did."""
    w = STATE.watches.get(job_id)
    stage = (service or {}).get("stage")
    if w is None or stage not in ("done", "failed"):
        return False
    with STATE.lock:
        if (job_id, stage) in STATE.told or job_id not in STATE.watches:
            return False
        STATE.told.add((job_id, stage))
        del STATE.watches[job_id]
    ok = stage == "done"
    title = "Your 3D house is ready" if ok else "Your 3D house could not be built"
    link = f"{app_settings.frontend_origin.rstrip('/')}/3d/{job_id}"
    text = (
        f"{title}.\n\nOpen it here (you will be asked to sign in): {link}\n"
        if ok
        else f"{title}. You can open the plan, check it and build again: {link}\n"
    )
    with STATE.lock:
        lst = STATE.events.setdefault(w.user_id, [])
        lst.append(
            {
                "job_id": job_id,
                "outcome": stage,
                "quality": w.quality,
                "title": title,
                "at": datetime.now(UTC).isoformat(),
            }
        )
        del lst[:-MAX_EVENTS]
    if w.email and email_on(w.user_id):
        try:
            get_mailer().send(w.email, title, text)
        except Exception as e:  # noqa: BLE001 - an email failure must not break the status call
            logger.warning(
                "could not send the build email for job %s: %s", job_id, type(e).__name__
            )
    return True


def start_poller(client: Any) -> None:
    """Poll watched jobs in the background: an outcome is announced even with no page open."""
    if STATE.poller is not None and not STATE.poller.done():
        return

    async def loop() -> None:
        while STATE.watches:
            for job_id in list(STATE.watches):
                try:
                    observe(job_id, await client.job(job_id))
                except Exception as e:  # noqa: BLE001 - keep polling the others
                    logger.debug("poll of job %s failed: %s", job_id, type(e).__name__)
            await asyncio.sleep(POLL_S)

    STATE.poller = asyncio.get_running_loop().create_task(loop())
