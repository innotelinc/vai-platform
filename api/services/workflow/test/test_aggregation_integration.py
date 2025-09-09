from unittest.mock import Mock

import pytest
from pipecat.processors.aggregators.llm_response import LLMAssistantAggregatorParams
from pipecat.services.openai.llm import OpenAILLMContext

from api.services.workflow.pipecat_engine import PipecatEngine
from api.services.workflow.pipecat_engine_callbacks import (
    create_generation_started_callback,
)


class TestAggregationIntegration:
    """Integration tests for the TTS aggregation correction flow."""

    @pytest.mark.asyncio
    async def test_engine_reference_text_tracking(self):
        """Test that the engine properly tracks LLM reference text."""
        # Create mock dependencies
        mock_task = Mock()
        mock_llm = Mock()
        mock_context = Mock(spec=OpenAILLMContext)
        mock_tts = Mock()
        mock_workflow = Mock()
        mock_workflow.start_node_id = "start"
        mock_workflow.nodes = {
            "start": Mock(is_start=True, is_static=True, is_end=False, out_edges=[])
        }

        # Create engine
        engine = PipecatEngine(
            task=mock_task,
            llm=mock_llm,
            context=mock_context,
            tts=mock_tts,
            workflow=mock_workflow,
            call_context_vars={},
            workflow_run_id=1,
        )

        # Test initial state
        assert engine._current_llm_reference_text == ""

        # Test accumulating LLM text
        await engine.handle_llm_text_frame("Hello ")
        assert engine._current_llm_reference_text == "Hello "

        await engine.handle_llm_text_frame("world!")
        assert engine._current_llm_reference_text == "Hello world!"

        # Test generation started callback clears reference text
        callback = create_generation_started_callback(engine)
        await callback()
        assert engine._current_llm_reference_text == ""

    @pytest.mark.asyncio
    async def test_aggregation_correction_callback_creation(self):
        """Test creating the aggregation correction callback."""
        # Create mock engine
        mock_task = Mock()
        mock_llm = Mock()
        mock_context = Mock(spec=OpenAILLMContext)
        mock_workflow = Mock()

        engine = PipecatEngine(
            task=mock_task,
            llm=mock_llm,
            context=mock_context,
            workflow=mock_workflow,
            call_context_vars={},
            workflow_run_id=1,
        )

        # Set reference text
        engine._current_llm_reference_text = "Hello, world! How are you?"

        # Create correction callback
        callback = engine.create_aggregation_correction_callback()

        # Test correction - note that trailing punctuation might be stripped if not in corrupted text
        corrected = callback("Hello world How are you")
        assert corrected == "Hello, world! How are you"

    def test_llm_assistant_aggregator_params_with_callback(self):
        """Test that LLMAssistantAggregatorParams accepts correction callback."""

        def mock_callback(text: str) -> str:
            return text.upper()

        params = LLMAssistantAggregatorParams(
            expect_stripped_words=True, correct_aggregation_callback=mock_callback
        )

        assert params.expect_stripped_words is True
        assert params.correct_aggregation_callback is not None
        assert params.correct_aggregation_callback("hello") == "HELLO"

    @pytest.mark.asyncio
    async def test_pipeline_callbacks_processor_llm_text_frame(self):
        """Test that PipelineEngineCallbacksProcessor handles LLMTextFrame."""
        from pipecat.frames.frames import LLMTextFrame
        from pipecat.processors.frame_processor import FrameDirection

        from api.services.pipecat.pipeline_engine_callbacks_processor import (
            PipelineEngineCallbacksProcessor,
        )

        # Track callback invocations
        callback_invoked = False
        callback_text = None

        async def mock_llm_text_callback(text: str):
            nonlocal callback_invoked, callback_text
            callback_invoked = True
            callback_text = text

        # Create processor with callback
        processor = PipelineEngineCallbacksProcessor(
            llm_text_frame_callback=mock_llm_text_callback
        )

        # Process LLMTextFrame
        frame = LLMTextFrame(text="Hello world")
        await processor.process_frame(frame, FrameDirection.DOWNSTREAM)

        # Verify callback was invoked
        assert callback_invoked is True
        assert callback_text == "Hello world"
