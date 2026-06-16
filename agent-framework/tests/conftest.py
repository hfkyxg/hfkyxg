import pytest

from agent_framework.core.permissions import always_allow
from agent_framework.core.provider import ModelProvider, ProviderResponse
from agent_framework.core.tool import ToolRegistry


class FakeModelProvider(ModelProvider):
    """Cycles through preset responses."""

    def __init__(self, responses: list[ProviderResponse]):
        super().__init__(model="fake/model")
        self._responses = list(responses)
        self._idx = 0

    async def complete(self, messages, tools, **kw) -> ProviderResponse:
        resp = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return resp


@pytest.fixture
def tmp_workspace(tmp_path):
    return tmp_path


@pytest.fixture
def simple_registry():
    return ToolRegistry()


@pytest.fixture
def allow_gate():
    return always_allow()
