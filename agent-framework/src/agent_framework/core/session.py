from __future__ import annotations

import dataclasses
import json
import uuid
from dataclasses import dataclass, field

from agent_framework.core.messages import Message


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    messages: list[Message] = field(default_factory=list)

    def append(self, message: Message) -> None:
        self.messages.append(message)

    def to_transcript_json(self) -> str:
        return json.dumps(
            [dataclasses.asdict(m) for m in self.messages],
            indent=2,
            default=str,
        )

    @classmethod
    def with_system_prompt(cls, system_prompt: str) -> Session:
        s = cls()
        s.append(Message(role="system", content=system_prompt))
        return s
