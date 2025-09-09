import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pipecat.frames.frames import (
    EndFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TTSSpeakFrame,
)
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContextFrame
from pipecat.services.openai.llm import OpenAILLMContext

from api.services.workflow.dto import EdgeDataDTO, NodeDataDTO
from api.services.workflow.pipecat_engine import PipecatEngine
from api.services.workflow.workflow import Edge, Node, WorkflowGraph


class TestPipecatEngineSetNode:
    """Test cases for PipecatEngine.set_node method refactoring."""

    @pytest.fixture
    def mock_workflow(self):
        """Create a mock workflow with various node types."""
        workflow = Mock(spec=WorkflowGraph)
        workflow.nodes = {}
        workflow.start_node_id = "start_node"
        workflow.global_node_id = None
        return workflow

    @pytest.fixture
    def mock_dependencies(self, mock_workflow):
        """Create mock dependencies for PipecatEngine initialization."""
        task = AsyncMock()
        task.queue_frames = AsyncMock()
        task.queue_frame = AsyncMock()

        llm = AsyncMock()
        llm.register_function = Mock()
        llm.push_frame = AsyncMock()

        context = Mock(spec=OpenAILLMContext)
        context.set_node_name = Mock()

        return {
            "task": task,
            "llm": llm,
            "context": context,
            "tts": Mock(),
            "transport": Mock(),
            "workflow": mock_workflow,
            "call_context_vars": {"test_var": "test_value"},
        }

    @pytest.fixture
    def engine(self, mock_dependencies):
        """Create a PipecatEngine instance."""
        # Add audio_buffer and workflow_run_id to dependencies
        mock_dependencies["audio_buffer"] = None
        mock_dependencies["workflow_run_id"] = 123
        engine = PipecatEngine(**mock_dependencies)
        # Mock the builtin function registration
        engine._register_builtin_functions = AsyncMock()
        return engine

    def create_node(self, node_id, **kwargs):
        """Helper to create a node with default values."""
        defaults = {
            "name": f"Node {node_id}",
            "prompt": f"Prompt for {node_id}",
            "is_static": False,
            "is_start": False,
            "is_end": False,
            "allow_interrupt": True,
            "extraction_enabled": False,
            "extraction_prompt": "",
            "extraction_variables": [],
            "add_global_prompt": True,
            "wait_for_user_response": False,
            "detect_voicemail": False,
        }
        defaults.update(kwargs)

        data = Mock(spec=NodeDataDTO)
        for key, value in defaults.items():
            setattr(data, key, value)

        node = Mock(spec=Node)
        node.id = node_id
        node.data = data
        node.out_edges = []

        # Copy attributes from data to node
        for key, value in defaults.items():
            setattr(node, key, value)

        return node

    def create_edge(
        self, source, target, label="Continue", condition="Always continue"
    ):
        """Helper to create an edge."""
        data = Mock(spec=EdgeDataDTO)
        data.label = label
        data.condition = condition

        edge = Mock(spec=Edge)
        edge.source = source
        edge.target = target
        edge.data = data
        edge.get_function_name = Mock(return_value=label.lower().replace(" ", "_"))

        return edge

    # ===== START NODE TESTS =====

    @pytest.mark.asyncio
    async def test_start_node_static_immediate_execution(self, engine, mock_workflow):
        """Test: Basic static start node executes immediately."""
        # Setup
        start_node = self.create_node(
            "start_node",
            is_start=True,
            is_static=True,
            prompt="Welcome to our service!",
        )
        next_node = self.create_node("next_node", is_static=False)

        edge = self.create_edge("start_node", "next_node")
        start_node.out_edges = [edge]

        mock_workflow.nodes = {"start_node": start_node, "next_node": next_node}

        # Execute
        await engine.set_node("start_node")

        # Verify
        # Should queue TTS immediately
        engine.task.queue_frames.assert_called_once()
        frames = engine.task.queue_frames.call_args[0][0]
        assert len(frames) == 3
        assert isinstance(frames[0], LLMFullResponseStartFrame)
        assert isinstance(frames[1], TTSSpeakFrame)
        assert frames[1].text == "Welcome to our service!"
        assert isinstance(frames[2], LLMFullResponseEndFrame)

        # Static start nodes now set pending transition after context push
        assert engine._pending_control_transition_after_context_push is not None

        # Should not have set detect_voicemail for static start without it
        assert not engine._detect_voicemail

    @pytest.mark.asyncio
    async def test_start_node_with_detect_voicemail_no_audio_buffer(
        self, engine, mock_workflow
    ):
        """Test: Start node with voicemail detection but no audio buffer logs warning."""
        # Setup
        start_node = self.create_node(
            "start_node",
            is_start=True,
            is_static=True,
            detect_voicemail=True,
            prompt="Hello, this is a business call.",
        )

        mock_workflow.nodes = {"start_node": start_node}

        # Engine has no audio buffer (None)
        assert engine._audio_buffer is None

        # Execute
        await engine.set_node("start_node")

        # Verify
        # Should NOT set voicemail detection flag since no audio buffer
        assert engine._detect_voicemail is False
        assert engine._voicemail_detector is None

        # Should queue TTS immediately
        engine.task.queue_frames.assert_called_once()
        frames = engine.task.queue_frames.call_args[0][0]
        assert isinstance(frames[1], TTSSpeakFrame)
        assert frames[1].text == "Hello, this is a business call."

    @pytest.mark.asyncio
    async def test_start_node_non_static_with_detect_voicemail(
        self, engine, mock_workflow
    ):
        """Test: Non-static start node with voicemail detection without audio buffer."""
        # Setup
        start_node = self.create_node(
            "start_node",
            is_start=True,
            is_static=False,  # Non-static
            detect_voicemail=True,
            prompt="You are an AI assistant. Start the conversation.",
        )

        mock_workflow.nodes = {"start_node": start_node}

        # Mock the context update method
        engine._update_llm_context = AsyncMock()
        engine._compose_system_message_functions_for_node = AsyncMock(
            return_value=({"role": "system", "content": "Test prompt"}, [])
        )

        # Execute
        await engine.set_node("start_node")

        # Verify
        # Should NOT set voicemail detection flags (no audio buffer)
        assert engine._detect_voicemail is False
        assert engine._voicemail_detector is None

        # Should update LLM context for non-static node
        engine._update_llm_context.assert_called_once()

        # Should queue context frame
        engine.task.queue_frame.assert_called_once()
        frame = engine.task.queue_frame.call_args[0][0]
        assert isinstance(frame, OpenAILLMContextFrame)

    @pytest.mark.asyncio
    async def test_start_node_static_with_wait_for_user_response(
        self, engine, mock_workflow
    ):
        """Test: Static start node with wait_for_user_response."""
        # Setup
        start_node = self.create_node(
            "start_node",
            is_start=True,
            is_static=True,
            wait_for_user_response=True,
            prompt="Please tell me your name.",
        )
        next_node = self.create_node("next_node")

        edge = self.create_edge("start_node", "next_node")
        start_node.out_edges = [edge]

        mock_workflow.nodes = {"start_node": start_node, "next_node": next_node}

        # Execute
        await engine.set_node("start_node")

        # Verify
        # Should queue TTS immediately
        engine.task.queue_frames.assert_called_once()

        # Should have a pending control transition that will start the timer
        assert engine._pending_control_transition_after_context_push is not None

        # Timer task should not exist yet
        assert (
            not hasattr(engine, "_user_response_timeout_task")
            or engine._user_response_timeout_task is None
        )

        # Simulate context push to start the timer
        await engine.flush_pending_transitions(source="context_push")

        # Now the timeout task should be created
        assert engine._user_response_timeout_task is not None
        assert not engine._user_response_timeout_task.done()

        # Clean up the task
        engine._user_response_timeout_task.cancel()

    @pytest.mark.asyncio
    async def test_start_node_non_static(self, engine, mock_workflow):
        """Test: Non-static start node sends context to LLM."""
        # Setup
        start_node = self.create_node(
            "start_node",
            is_start=True,
            is_static=False,
            prompt="You are a helpful assistant. Greet the user.",
        )

        mock_workflow.nodes = {"start_node": start_node}

        # Mock the context update method
        engine._update_llm_context = AsyncMock()
        engine._compose_system_message_functions_for_node = AsyncMock(
            return_value=({"role": "system", "content": "Test prompt"}, [])
        )

        # Execute
        await engine.set_node("start_node")

        # Verify
        # Should set context name
        engine.context.set_node_name.assert_called_once_with("Node start_node")

        # Should update LLM context
        engine._update_llm_context.assert_called_once()

        # Should queue context frame
        engine.task.queue_frame.assert_called_once()
        frame = engine.task.queue_frame.call_args[0][0]
        assert isinstance(frame, OpenAILLMContextFrame)

    # ===== AGENT NODE TESTS =====

    @pytest.mark.asyncio
    async def test_agent_node_static(self, engine, mock_workflow):
        """Test: Static agent node plays TTS and transitions."""
        # Setup
        agent_node = self.create_node(
            "agent_node", is_static=True, prompt="Processing your request..."
        )
        next_node = self.create_node("next_node")

        edge = self.create_edge("agent_node", "next_node")
        agent_node.out_edges = [edge]

        mock_workflow.nodes = {"agent_node": agent_node, "next_node": next_node}

        # Execute
        await engine.set_node("agent_node")

        # Verify
        # Should queue TTS
        engine.task.queue_frames.assert_called_once()
        frames = engine.task.queue_frames.call_args[0][0]
        assert isinstance(frames[1], TTSSpeakFrame)
        assert frames[1].text == "Processing your request..."

        # Should have pending transition
        assert engine._pending_control_transition_after_context_push is not None

    @pytest.mark.asyncio
    async def test_agent_node_non_static(self, engine, mock_workflow):
        """Test: Non-static agent node sends context to LLM."""
        # Setup
        agent_node = self.create_node(
            "agent_node",
            is_static=False,
            prompt="Analyze the user's request and respond appropriately.",
        )
        decision_node = self.create_node("decision_node")

        edge = self.create_edge("agent_node", "decision_node", "analyze_complete")
        agent_node.out_edges = [edge]

        mock_workflow.nodes = {"agent_node": agent_node, "decision_node": decision_node}

        # Mock methods
        engine._update_llm_context = AsyncMock()
        engine._compose_system_message_functions_for_node = AsyncMock(
            return_value=(
                {"role": "system", "content": "Test"},
                [{"name": "test_func"}],
            )
        )

        # Execute
        await engine.set_node("agent_node")

        # Verify
        # Should register transition function
        engine.llm.register_function.assert_called_once()
        call_args = engine.llm.register_function.call_args
        assert call_args[0][0] == "analyze_complete"
        assert callable(call_args[0][1])  # Check it's a function
        assert call_args[1]["cancel_on_interruption"] is True

        # Should update context and send frame
        engine._update_llm_context.assert_called_once()
        engine.task.queue_frame.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_node_with_interruption_control(self, engine, mock_workflow):
        """Test: Agent node respects allow_interrupt flag."""
        # Setup
        no_interrupt_node = self.create_node(
            "no_interrupt",
            is_static=True,
            allow_interrupt=False,
            prompt="Please wait while I process...",
        )

        mock_workflow.nodes = {"no_interrupt": no_interrupt_node}

        # Execute
        await engine.set_node("no_interrupt")

        # Verify current node is set (for STT mute callback)
        assert engine._current_node == no_interrupt_node
        assert engine._current_node.allow_interrupt is False

    # ===== END NODE TESTS =====

    @pytest.mark.asyncio
    async def test_end_node_static(self, engine, mock_workflow):
        """Test: Static end node plays final message and schedules end task."""
        # Setup
        end_node = self.create_node(
            "end_node",
            is_static=True,
            is_end=True,
            prompt="Thank you for calling. Goodbye!",
        )

        mock_workflow.nodes = {"end_node": end_node}

        # Execute
        await engine.set_node("end_node")

        # Verify
        # Should queue TTS
        engine.task.queue_frames.assert_called_once()
        frames = engine.task.queue_frames.call_args[0][0]
        assert frames[1].text == "Thank you for calling. Goodbye!"

        # Should have pending end task
        assert engine._pending_control_transition_after_context_push is not None

        # Execute the pending transition
        await engine._pending_control_transition_after_context_push()

        # Should have sent EndFrame via task.queue_frame
        # The second call should be the EndFrame (first was TTS frames)
        assert engine.task.queue_frame.call_count >= 1
        end_frame = engine.task.queue_frame.call_args[0][0]
        assert isinstance(end_frame, EndFrame)

    @pytest.mark.asyncio
    async def test_end_node_with_extraction(self, engine, mock_workflow):
        """Test: End node with variable extraction."""
        # Setup
        end_node = self.create_node(
            "end_node",
            is_end=True,
            is_static=False,
            extraction_enabled=True,
            extraction_variables=["user_name", "satisfaction_level"],
            extraction_prompt="Extract user name and satisfaction",
        )

        mock_workflow.nodes = {"end_node": end_node}

        # Mock the extraction manager
        engine._variable_extraction_manager = Mock()
        engine._perform_variable_extraction_if_needed = AsyncMock()

        # Mock context update and composition methods
        engine._update_llm_context = AsyncMock()
        engine._compose_system_message_functions_for_node = AsyncMock(
            return_value=({"role": "system", "content": "Test"}, [])
        )

        # Execute
        await engine.set_node("end_node")

        # Verify
        # Should trigger extraction
        engine._perform_variable_extraction_if_needed.assert_called_once_with(end_node)

        # Should have pending end task
        assert engine._pending_control_transition_after_context_push is not None

    # ===== CALLBACK INTEGRATION TESTS =====

    @pytest.mark.asyncio
    async def test_user_stopped_speaking_during_response_wait(
        self, engine, mock_workflow
    ):
        """Test: User stops speaking triggers transition during wait_for_response."""
        # Setup
        start_node = self.create_node(
            "start_node", is_start=True, is_static=True, wait_for_user_response=True
        )
        next_node = self.create_node("next_node")

        edge = self.create_edge("start_node", "next_node")
        start_node.out_edges = [edge]

        mock_workflow.nodes = {"start_node": start_node, "next_node": next_node}

        # Set current node to start node
        engine._current_node = start_node
        engine._user_response_timeout_task = asyncio.create_task(asyncio.sleep(3))

        # Create callback and execute
        callback = engine.create_user_stopped_speaking_callback()

        # Mock set_node to avoid recursion
        with patch.object(engine, "set_node", new=AsyncMock()) as mock_set_node:
            await callback()

        # Verify
        mock_set_node.assert_called_once_with("next_node")
        assert engine._queue_context_frame is False  # Should be set to False

    @pytest.mark.asyncio
    async def test_context_push_callback_executes_pending_transitions(self, engine):
        """Test: flush_pending_transitions executes deferred transitions."""
        # Setup pending transitions
        mock_generated_transition = AsyncMock()
        mock_control_transition = AsyncMock()

        engine._pending_generated_transition_after_context_push = (
            mock_generated_transition
        )
        engine._pending_control_transition_after_context_push = mock_control_transition

        # Execute
        await engine.flush_pending_transitions(source="context_push")

        # Verify both transitions were executed
        mock_generated_transition.assert_called_once()
        mock_control_transition.assert_called_once()

        # Verify they were cleared
        assert engine._pending_generated_transition_after_context_push is None
        assert engine._pending_control_transition_after_context_push is None

    # ===== COMPLEX SCENARIO TESTS =====


# Add helper for testing with real async behavior
def ANY(cls=None):
    """Helper for matching any argument in mock calls."""

    class AnyMatcher:
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, other):
            if self.cls:
                return isinstance(other, self.cls)
            return True

    return AnyMatcher(cls)
