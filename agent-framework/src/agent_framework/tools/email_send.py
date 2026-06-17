"""Email send tool — sends email via SMTP (Gmail/Outlook/custom) or Mailgun API."""
from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class EmailSendTool:
    name = "email_send"
    description = (
        "Send an email message. Supports plain text and HTML. "
        "Uses SMTP (Gmail, Outlook, or custom server) configured via environment variables "
        "SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD. "
        "Also supports Mailgun API via MAILGUN_API_KEY + MAILGUN_DOMAIN."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient email address (or comma-separated list)",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line",
            },
            "body": {
                "type": "string",
                "description": "Email body — plain text or HTML",
            },
            "from_addr": {
                "type": "string",
                "description": (
                    "Sender address (defaults to SMTP_USER env var). "
                    "Override only if your server allows arbitrary from addresses."
                ),
            },
            "html": {
                "type": "boolean",
                "default": False,
                "description": "Set true if body is HTML",
            },
            "cc": {
                "type": "string",
                "description": "CC addresses (comma-separated)",
            },
        },
        "required": ["to", "subject", "body"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        to: str = arguments["to"]
        subject: str = arguments["subject"]
        body: str = arguments["body"]
        html: bool = bool(arguments.get("html", False))
        cc: str = arguments.get("cc", "")

        try:
            from agent_framework.config.settings import settings as _s
        except Exception:
            _s = None  # type: ignore[assignment]

        # Try Mailgun first if configured
        mailgun_key = getattr(_s, "mailgun_api_key", "") if _s else ""
        mailgun_domain = getattr(_s, "mailgun_domain", "") if _s else ""
        if mailgun_key and mailgun_domain:
            return await self._mailgun(to, subject, body, html, cc, mailgun_key, mailgun_domain)

        # Fall back to SMTP
        smtp_host = getattr(_s, "smtp_host", "") if _s else ""
        smtp_port = int(getattr(_s, "smtp_port", 587) if _s else 587)
        smtp_user = getattr(_s, "smtp_user", "") if _s else ""
        smtp_pass = getattr(_s, "smtp_password", "") if _s else ""
        from_addr = arguments.get("from_addr") or smtp_user

        if not smtp_host or not smtp_user:
            raise ToolError(
                self.name,
                "Email not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD "
                "(and optionally SMTP_PORT) in .env, or MAILGUN_API_KEY + MAILGUN_DOMAIN.",
            )

        return self._smtp(to, subject, body, html, cc, from_addr, smtp_host, smtp_port,
                          smtp_user, smtp_pass)

    def _smtp(
        self, to: str, subject: str, body: str, html: bool, cc: str,
        from_addr: str, host: str, port: int, user: str, password: str,
    ) -> str:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to
        if cc:
            msg["Cc"] = cc

        part = MIMEText(body, "html" if html else "plain", "utf-8")
        msg.attach(part)

        recipients = [a.strip() for a in to.split(",")]
        if cc:
            recipients += [a.strip() for a in cc.split(",")]

        try:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.ehlo()
                if port != 465:
                    server.starttls()
                server.login(user, password)
                server.sendmail(from_addr, recipients, msg.as_string())
            return f"Email sent to {to} via SMTP ({host}:{port})"
        except smtplib.SMTPException as exc:
            raise ToolError(self.name, f"SMTP error: {exc}") from exc

    async def _mailgun(
        self, to: str, subject: str, body: str, html: bool, cc: str,
        api_key: str, domain: str,
    ) -> str:
        import httpx

        data: dict[str, str] = {
            "from": f"apathy <mailgun@{domain}>",
            "to": to,
            "subject": subject,
            ("html" if html else "text"): body,
        }
        if cc:
            data["cc"] = cc

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.mailgun.net/v3/{domain}/messages",
                auth=("api", api_key),
                data=data,
            )
        if resp.status_code not in (200, 202):
            raise ToolError(self.name, f"Mailgun error {resp.status_code}: {resp.text[:200]}")
        return f"Email sent to {to} via Mailgun (domain={domain})"
