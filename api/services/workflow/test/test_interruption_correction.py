from unittest.mock import AsyncMock, Mock

import pytest
from pipecat.frames.frames import StartInterruptionFrame
from pipecat.processors.aggregators.llm_response import LLMAssistantAggregatorParams
from pipecat.services.openai.llm import (
    OpenAIAssistantContextAggregator,
    OpenAILLMContext,
)


class TestInterruptionCorrection:
    """Test that TTS aggregation correction works during interruptions."""

    @pytest.mark.asyncio
    async def test_openai_interruption_with_correction(self):
        """Test OpenAI assistant context aggregator applies correction during interruption."""
        # Create mock context
        mock_context = Mock(spec=OpenAILLMContext)
        mock_context.get_messages.return_value = []
        mock_context.add_message = Mock()

        # Create correction callback
        def correction_callback(text: str) -> str:
            # Simulate fixing corrupted text
            if text == "Hello world  how are  you":
                return "Hello world, how are you"
            return text

        # Create aggregator with correction callback
        params = LLMAssistantAggregatorParams(
            expect_stripped_words=True, correct_aggregation_callback=correction_callback
        )

        aggregator = OpenAIAssistantContextAggregator(
            context=mock_context, params=params
        )

        # Set up aggregation state
        aggregator._aggregation = "Hello world  how are  you"
        aggregator._current_llm_response_id = "test-id"
        aggregator._response_function_messages = {}
        aggregator._function_calls_in_progress = {}
        aggregator._started = 1

        # Mock push_context_frame and reset methods
        aggregator.push_context_frame = AsyncMock()
        aggregator.reset = AsyncMock()

        # Process interruption
        interruption_frame = StartInterruptionFrame()
        await aggregator._handle_interruptions(interruption_frame)

        # Verify the corrected text was added to context
        mock_context.add_message.assert_called_once()
        added_message = mock_context.add_message.call_args[0][0]
        assert added_message["role"] == "assistant"
        assert (
            added_message["content"]
            == "Hello world, how are you <<interrupted_by_user>>"
        )

    @pytest.mark.asyncio
    async def test_google_interruption_with_correction(self):
        """Test Google assistant context aggregator applies correction during interruption."""
        from pipecat.services.google.llm import (
            Content,
            GoogleAssistantContextAggregator,
        )

        # Create mock context
        mock_context = Mock(spec=OpenAILLMContext)
        mock_context.get_messages.return_value = []
        mock_context.add_message = Mock()

        # Create correction callback
        def correction_callback(text: str) -> str:
            # Simulate fixing corrupted text
            if text == "I am  here to  help":
                return "I am here to help"
            return text

        # Create aggregator with correction callback
        params = LLMAssistantAggregatorParams(
            expect_stripped_words=True, correct_aggregation_callback=correction_callback
        )

        aggregator = GoogleAssistantContextAggregator(
            context=mock_context, params=params
        )

        # Set up aggregation state
        aggregator._aggregation = "I am  here to  help"
        aggregator._current_llm_response_id = "test-id"
        aggregator._response_function_messages = {}
        aggregator._function_calls_in_progress = {}
        aggregator._started = 1

        # Mock push_context_frame and reset methods
        aggregator.push_context_frame = AsyncMock()
        aggregator.reset = AsyncMock()

        # Process interruption
        interruption_frame = StartInterruptionFrame()
        await aggregator._handle_interruptions(interruption_frame)

        # Verify the corrected text was added to context
        mock_context.add_message.assert_called_once()
        added_content = mock_context.add_message.call_args[0][0]

        # Google uses Content objects
        assert isinstance(added_content, Content)
        assert added_content.role == "model"
        assert len(added_content.parts) == 1
        assert (
            added_content.parts[0].text == "I am here to help <<interrupted_by_user>>"
        )

    @pytest.mark.asyncio
    async def test_interruption_correction_error_handling(self):
        """Test that interruption handling continues even if correction callback fails."""
        # Create mock context
        mock_context = Mock(spec=OpenAILLMContext)
        mock_context.get_messages.return_value = []
        mock_context.add_message = Mock()

        # Create correction callback that raises error
        def failing_callback(text: str) -> str:
            raise ValueError("Correction failed")

        # Create aggregator with failing callback
        params = LLMAssistantAggregatorParams(
            expect_stripped_words=True, correct_aggregation_callback=failing_callback
        )

        aggregator = OpenAIAssistantContextAggregator(
            context=mock_context, params=params
        )

        # Set up aggregation state
        aggregator._aggregation = "Some text"
        aggregator._current_llm_response_id = "test-id"
        aggregator._response_function_messages = {}
        aggregator._function_calls_in_progress = {}
        aggregator._started = 1

        # Mock push_context_frame and reset methods
        aggregator.push_context_frame = AsyncMock()
        aggregator.reset = AsyncMock()

        # Process interruption - should not raise
        interruption_frame = StartInterruptionFrame()
        await aggregator._handle_interruptions(interruption_frame)

        # Verify the original text was still added (fallback behavior)
        mock_context.add_message.assert_called_once()
        added_message = mock_context.add_message.call_args[0][0]
        assert added_message["role"] == "assistant"
        assert added_message["content"] == "Some text <<interrupted_by_user>>"
