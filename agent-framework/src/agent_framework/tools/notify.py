"""Notification tool — send messages to Slack, Discord, Teams, Telegram, and webhooks."""
from __future__ import annotations

from typing import Any

import httpx

from agent_framework.core.errors import ToolError
from agent_framework.core.tool import ToolContext


class NotifyTool:
    name = "notify"
    description = (
        "Send a notification message to an external service. "
        "Supported channels: slack, discord, teams, telegram, "
        "or a direct HTTPS webhook URL. "
        "Reads webhook URLs from environment variables when channel is a service name."
    )
    requires_permission = True
    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Message text to send",
            },
            "channel": {
                "type": "string",
                "description": (
                    "Where to send: 'slack', 'discord', 'teams', 'telegram', "
                    "or a direct webhook URL starting with https://"
                ),
                "default": "slack",
            },
            "title": {
                "type": "string",
                "description": "Optional title / subject for the message",
            },
            "color": {
                "type": "string",
                "description": "Color accent: 'good', 'warning', 'danger', or hex '#ff0000'",
                "default": "good",
            },
        },
        "required": ["message"],
    }

    async def run(self, arguments: dict[str, Any], *, context: ToolContext) -> str:
        message: str = arguments["message"]
        channel: str = arguments.get("channel", "slack")
        title: str = arguments.get("title", "")
        color: str = arguments.get("color", "good")

        try:
            settings = self._load_settings()
        except Exception:
            settings = {}

        # Resolve channel to a webhook URL or special handler
        if channel.startswith("https://"):
            webhook_url = channel
            service = self._detect_service(webhook_url)
        elif channel == "slack":
            webhook_url = settings.get("slack_webhook_url", "")
            service = "slack"
        elif channel == "discord":
            webhook_url = settings.get("discord_webhook_url", "")
            service = "discord"
        elif channel == "teams":
            webhook_url = settings.get("teams_webhook_url", "")
            service = "teams"
        elif channel == "telegram":
            return await self._telegram(message, title, settings)
        else:
            raise ToolError(self.name, f"Unknown channel: {channel!r}")

        if not webhook_url:
            raise ToolError(
                self.name,
                f"No webhook URL configured for {channel!r}. "
                f"Set the {channel.upper()}_WEBHOOK_URL environment variable.",
            )

        if service == "slack":
            payload = self._slack_payload(message, title, color)
        elif service == "discord":
            payload = self._discord_payload(message, title, color)
        elif service == "teams":
            payload = self._teams_payload(message, title, color)
        else:
            payload = {"text": f"**{title}**\n{message}" if title else message}

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolError(self.name, f"Notification failed: {exc}") from exc

        return f"Notification sent to {channel} ✓"

    # ------------------------------------------------------------------
    # Service detection from URL
    # ------------------------------------------------------------------

    def _detect_service(self, url: str) -> str:
        if "hooks.slack.com" in url:
            return "slack"
        if "discord.com/api/webhooks" in url:
            return "discord"
        if "outlook.office.com/webhook" in url or "office.com/webhook" in url:
            return "teams"
        return "generic"

    # ------------------------------------------------------------------
    # Payload builders
    # ------------------------------------------------------------------

    def _slack_payload(self, message: str, title: str, color: str) -> dict:
        if title:
            return {
                "attachments": [
                    {
                        "title": title,
                        "text": message,
                        "color": color,
                        "mrkdwn_in": ["text"],
                    }
                ]
            }
        return {"text": message}

    def _discord_payload(self, message: str, title: str, color: str) -> dict:
        # Discord uses integer colors
        color_map = {"good": 0x2ECC71, "warning": 0xF39C12, "danger": 0xE74C3C}
        int_color = color_map.get(color, 0x7289DA)
        if color.startswith("#"):
            try:
                int_color = int(color[1:], 16)
            except ValueError:
                int_color = 0x7289DA
        # Use embeds whenever we have a title or a custom color
        use_embed = bool(title) or color.startswith("#") or color in ("good", "warning", "danger")
        if use_embed:
            embed: dict = {"description": message, "color": int_color}
            if title:
                embed["title"] = title
            return {"embeds": [embed]}
        return {"content": message}

    def _teams_payload(self, message: str, title: str, color: str) -> dict:
        color_map = {"good": "2ECC71", "warning": "F39C12", "danger": "E74C3C"}
        hex_color = color_map.get(color, "7289DA")
        if color.startswith("#"):
            hex_color = color[1:]
        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": hex_color,
            "summary": title or message[:80],
            "sections": [
                {
                    "activityTitle": title or "apathy notification",
                    "activityText": message,
                }
            ],
        }

    # ------------------------------------------------------------------
    # Telegram (different API pattern)
    # ------------------------------------------------------------------

    async def _telegram(self, message: str, title: str, settings: dict) -> str:
        token = settings.get("telegram_bot_token", "")
        chat_id = settings.get("telegram_chat_id", "")
        if not token or not chat_id:
            raise ToolError(
                self.name,
                "Telegram requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.",
            )
        text = f"*{title}*\n{message}" if title else message
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolError(self.name, f"Telegram error: {exc}") from exc
        return "Notification sent to Telegram ✓"

    def _load_settings(self) -> dict:
        from agent_framework.config.settings import settings

        return {
            "slack_webhook_url": settings.slack_webhook_url,
            "discord_webhook_url": settings.discord_webhook_url,
            "teams_webhook_url": settings.teams_webhook_url,
            "telegram_bot_token": settings.telegram_bot_token,
            "telegram_chat_id": settings.telegram_chat_id,
        }
