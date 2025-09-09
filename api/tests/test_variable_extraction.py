import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from pipecat.services.openai.llm import OpenAILLMContext

from api.services.workflow.dto import ExtractionVariableDTO, VariableType
from api.services.workflow.pipecat_engine_variable_extractor import (
    VariableExtractionManager,
)


class DummyLLM:
    """A minimal stub that mimics the parts of an LLM service used by the extractor."""

    def __init__(self, streamed_response: str | None = None):
        # Optionally provide a pre-defined streaming response for _perform_extraction tests
        self._streamed_response = streamed_response or "{}"
        self.registered_functions: dict[str, AsyncMock] = {}

    # ------------------------------------------------------------------
    # API used by VariableExtractionManager
    # ------------------------------------------------------------------
    def register_function(self, name: str, func, cancel_on_interruption=True):  # noqa: D401 – simple delegate
        self.registered_functions[name] = func

    async def get_chat_completions(self, _context, _messages):
        """Return an async generator that yields a single chunk with the full response."""

        class _Delta:  # noqa: D401 – tiny helper classes for stub response
            def __init__(self, content):
                self.content = content

        class _Choice:
            def __init__(self, delta):
                self.delta = delta

        class _Chunk:
            def __init__(self, content):
                self.choices = [_Choice(_Delta(content))]

        async def _stream():
            yield _Chunk(self._streamed_response)

        return _stream()


class DummyEngine:
    """A bare-bones Engine stub exposing only what the extractor relies on."""

    def __init__(self, llm):
        self.llm = llm
        self.context = OpenAILLMContext()
        self._pending_function_calls = 0
        # VariableExtractionManager currently updates this private attribute
        self._gathered_context: dict = {}


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_perform_extraction_parses_json_correctly():
    """_perform_extraction should return the parsed JSON from the LLM stream."""
    # Set dummy OpenAI API key to prevent initialization errors
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        expected_payload = {"name": "Alice", "age": 30}
        llm = DummyLLM(json.dumps(expected_payload))
        engine = DummyEngine(llm)
        manager = VariableExtractionManager(engine)

        # Mock the AsyncOpenAI client and its response
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message = AsyncMock()
        mock_response.choices[0].message.content = json.dumps(expected_payload)

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "api.services.workflow.pipecat_engine_variable_extractor.AsyncOpenAI",
            return_value=mock_client,
        ):
            # Minimal set of variables to extract – the prompts themselves are irrelevant here
            extraction_variables = [
                ExtractionVariableDTO(
                    name="name", type=VariableType.string, prompt="user name"
                ),
                ExtractionVariableDTO(
                    name="age", type=VariableType.number, prompt="user age"
                ),
            ]

            result = await manager._perform_extraction(
                extraction_variables, parent_ctx=None, extraction_prompt=""
            )

            assert result == expected_payload


@pytest.mark.asyncio
async def test_perform_extraction_with_custom_system_prompt():
    """_perform_extraction should use the provided extraction_prompt as system prompt."""
    # Set dummy OpenAI API key to prevent initialization errors
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        expected_payload = {"color": "blue"}
        llm = DummyLLM(json.dumps(expected_payload))
        engine = DummyEngine(llm)
        manager = VariableExtractionManager(engine)

        # Mock the AsyncOpenAI client and its response
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock()]
        mock_response.choices[0].message = AsyncMock()
        mock_response.choices[0].message.content = json.dumps(expected_payload)

        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch(
            "api.services.workflow.pipecat_engine_variable_extractor.AsyncOpenAI",
            return_value=mock_client,
        ):
            extraction_variables = [
                ExtractionVariableDTO(
                    name="color", type=VariableType.string, prompt="favourite color"
                )
            ]

            # Call with a custom extraction prompt
            custom_prompt = "You are a color extraction specialist."
            result = await manager._perform_extraction(
                extraction_variables, parent_ctx=None, extraction_prompt=custom_prompt
            )

            assert result == expected_payload
