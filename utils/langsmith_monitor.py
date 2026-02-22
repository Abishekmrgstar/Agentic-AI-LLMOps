import logging
import os
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, Optional

import requests
from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


@dataclass
class AlertConfig:
    latency_seconds: float
    token_threshold: int
    notify_mode: str
    webhook_url: str
    webhook_timeout_seconds: float
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    smtp_to: str
    smtp_use_tls: bool

    @classmethod
    def from_env(cls) -> "AlertConfig":
        return cls(
            latency_seconds=float(os.getenv("ALERT_LATENCY_SECONDS", "5")),
            token_threshold=int(os.getenv("ALERT_TOKEN_THRESHOLD", "50")),
            notify_mode=os.getenv("ALERT_NOTIFY_MODE", "log").lower(),
            webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
            webhook_timeout_seconds=float(os.getenv("ALERT_WEBHOOK_TIMEOUT_SECONDS", "5")),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", ""),
            smtp_to=os.getenv("SMTP_TO", ""),
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"},
        )


class LangSmithAlertHandler(BaseCallbackHandler):
    def __init__(self, config: Optional[AlertConfig] = None) -> None:
        self.config = config or AlertConfig.from_env()
        self._start_times: Dict[str, float] = {}

    def on_llm_start(self, serialized: Dict[str, Any], prompts: Any, **kwargs: Any) -> None:
        run_id = kwargs.get("run_id")
        if run_id:
            self._start_times[str(run_id)] = time.perf_counter()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        duration = self._pop_duration(run_id)
        total_tokens = self._extract_total_tokens(response)

        if duration is not None and duration >= self.config.latency_seconds:
            self._alert("Latency threshold exceeded", duration, total_tokens)

        if total_tokens is not None and total_tokens >= self.config.token_threshold:
            self._alert("Token threshold exceeded", duration, total_tokens)

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        duration = self._pop_duration(run_id)
        self._alert(f"LLM error: {error}", duration, None)

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        run_id = str(kwargs.get("run_id", ""))
        duration = self._pop_duration(run_id)
        self._alert(f"Chain error: {error}", duration, None)

    def _pop_duration(self, run_id: str) -> Optional[float]:
        if run_id in self._start_times:
            return time.perf_counter() - self._start_times.pop(run_id)
        return None

    def _extract_total_tokens(self, response: Any) -> Optional[int]:
        llm_output = getattr(response, "llm_output", None) or {}
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
            total = usage.get("total_tokens") if isinstance(usage, dict) else None
            if isinstance(total, int):
                return total

        generations = getattr(response, "generations", None) or []
        for generation_group in generations:
            for generation in generation_group:
                message = getattr(generation, "message", None)
                usage_metadata = getattr(message, "usage_metadata", None)
                if isinstance(usage_metadata, dict):
                    total = usage_metadata.get("total_tokens")
                    if isinstance(total, int):
                        return total

        return None

    def _alert(self, reason: str, duration: Optional[float], total_tokens: Optional[int]) -> None:
        logger.warning("LangSmith alert: %s", reason)
        payload = self._build_payload(reason, duration, total_tokens)
        mode = self.config.notify_mode

        if mode == "webhook":
            self._send_webhook(payload)
            return

        if mode == "smtp":
            if not self._smtp_configured():
                return
            self._send_email(payload["title"], payload["body"])
            return

    def _build_payload(
        self,
        reason: str,
        duration: Optional[float],
        total_tokens: Optional[int],
    ) -> Dict[str, str]:
        title = f"LangSmith alert: {reason}"
        lines = [f"Reason: {reason}"]
        if duration is not None:
            lines.append(f"Latency: {duration:.2f}s")
        if total_tokens is not None:
            lines.append(f"Total tokens: {total_tokens}")
        body = "\n".join(lines)
        return {"title": title, "body": body}

    def _smtp_configured(self) -> bool:
        required = [self.config.smtp_host, self.config.smtp_from, self.config.smtp_to]
        if not all(required):
            logger.warning("SMTP not configured; skipping email alert.")
            return False
        return True

    def _send_email(self, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.smtp_from
        message["To"] = self.config.smtp_to
        message.set_content(body)

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as smtp:
            if self.config.smtp_use_tls:
                smtp.starttls()
            if self.config.smtp_username and self.config.smtp_password:
                smtp.login(self.config.smtp_username, self.config.smtp_password)
            smtp.send_message(message)

    def _send_webhook(self, payload: Dict[str, str]) -> None:
        if not self.config.webhook_url:
            logger.warning("Webhook URL not configured; skipping webhook alert.")
            return

        data = {
            "title": payload["title"],
            "body": payload["body"],
        }
        try:
            response = requests.post(
                self.config.webhook_url,
                json=data,
                timeout=self.config.webhook_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Webhook alert failed: %s", exc)


def build_langsmith_callbacks() -> list[BaseCallbackHandler]:
    return [LangSmithAlertHandler()]
