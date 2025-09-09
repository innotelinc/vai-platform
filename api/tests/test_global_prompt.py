"""Tests for global prompt functionality in workflow engine."""

from unittest.mock import Mock

import pytest
from pipecat.services.openai.llm import OpenAILLMContext

from api.services.workflow.dto import (
    EdgeDataDTO,
    NodeDataDTO,
    NodeType,
    ReactFlowDTO,
    RFEdgeDTO,
    RFNodeDTO,
)
from api.services.workflow.pipecat_engine import PipecatEngine
from api.services.workflow.workflow import WorkflowGraph


class TestGlobalPrompt:
    """Test suite for global prompt feature."""

    @pytest.fixture
    def workflow_with_global_node(self):
        """Create a workflow with a global node and test nodes."""
        nodes = [
            RFNodeDTO(
                id="global",
                type=NodeType.globalNode,
                position={"x": 0, "y": 0},
                data=NodeDataDTO(
                    name="Global Node",
                    prompt="This is the global context: {{company_name}}",
                    is_static=False,
                ),
            ),
            RFNodeDTO(
                id="start",
                type=NodeType.startNode,
                position={"x": 100, "y": 100},
                data=NodeDataDTO(
                    name="Start Call",
                    prompt="Welcome to our service!",
                    is_static=False,
                    is_start=True,
                    add_global_prompt=True,  # Enable global prompt
                ),
            ),
            RFNodeDTO(
                id="agent1",
                type=NodeType.agentNode,
                position={"x": 200, "y": 200},
                data=NodeDataDTO(
                    name="Agent 1",
                    prompt="How can I help you today?",
                    add_global_prompt=False,  # Disable global prompt
                ),
            ),
            RFNodeDTO(
                id="agent2",
                type=NodeType.agentNode,
                position={"x": 300, "y": 300},
                data=NodeDataDTO(
                    name="Agent 2",
                    prompt="Please provide your details.",
                    add_global_prompt=True,  # Enable global prompt
                ),
            ),
            RFNodeDTO(
                id="end",
                type=NodeType.endNode,
                position={"x": 400, "y": 400},
                data=NodeDataDTO(
                    name="End Call",
                    prompt="Thank you for calling!",
                    is_static=True,
                    is_end=True,
                    add_global_prompt=True,  # Enable global prompt (but static)
                ),
            ),
        ]

        edges = [
            RFEdgeDTO(
                id="e1",
                source="start",
                target="agent1",
                data=EdgeDataDTO(label="Next", condition="Continue to agent"),
            ),
            RFEdgeDTO(
                id="e2",
                source="agent1",
                target="agent2",
                data=EdgeDataDTO(label="Details", condition="Get user details"),
            ),
            RFEdgeDTO(
                id="e3",
                source="agent2",
                target="end",
                data=EdgeDataDTO(label="Finish", condition="End the call"),
            ),
        ]

        flow_dto = ReactFlowDTO(nodes=nodes, edges=edges)
        return WorkflowGraph(flow_dto)

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for PipecatEngine initialization."""
        return {
            "task": Mock(),
            "llm": Mock(),
            "context": Mock(spec=OpenAILLMContext),
            "tts": Mock(),
            "transport": Mock(),
            "call_context_vars": {"company_name": "Dograh Inc"},
        }

    @pytest.fixture
    def engine(self, mock_dependencies, workflow_with_global_node):
        """Create a PipecatEngine instance with test workflow."""
        mock_dependencies["workflow"] = workflow_with_global_node
        return PipecatEngine(**mock_dependencies)

    @pytest.mark.asyncio
    async def test_global_prompt_enabled(self, engine):
        """Test that global prompt is prepended when add_global_prompt is True."""
        # Test with start node (add_global_prompt=True)
        start_node = engine.workflow.nodes["start"]
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(start_node)

        # Global prompt should be included
        expected_content = (
            "This is the global context: Dograh Inc\n\nWelcome to our service!"
        )
        assert system_message["content"] == expected_content
        assert system_message["role"] == "system"

    @pytest.mark.asyncio
    async def test_global_prompt_disabled(self, engine):
        """Test that global prompt is not prepended when add_global_prompt is False."""
        # Test with agent1 node (add_global_prompt=False)
        agent1_node = engine.workflow.nodes["agent1"]
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(agent1_node)

        # Global prompt should NOT be included
        expected_content = "How can I help you today?"
        assert system_message["content"] == expected_content
        assert "global context" not in system_message["content"]

    @pytest.mark.asyncio
    async def test_global_prompt_with_static_node(self, engine):
        """Test that static nodes don't use global prompt in engine (even if enabled)."""
        # Static nodes are handled differently - they use TTSSpeakFrame directly
        # This test verifies the compose_system_message behavior for completeness
        end_node = engine.workflow.nodes["end"]

        # Even though add_global_prompt=True, static nodes handle prompts differently
        # The _compose_system_message_functions_for_node is still called for consistency
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(end_node)

        # For static nodes, the global prompt would still be composed if enabled
        expected_content = (
            "This is the global context: Dograh Inc\n\nThank you for calling!"
        )
        assert system_message["content"] == expected_content

    @pytest.mark.asyncio
    async def test_global_prompt_variable_substitution(self, engine):
        """Test that variables in global prompt are properly substituted."""
        agent2_node = engine.workflow.nodes["agent2"]
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(agent2_node)

        # Verify variable substitution in global prompt
        assert "Dograh Inc" in system_message["content"]
        assert "{{company_name}}" not in system_message["content"]

        # Full expected content
        expected_content = (
            "This is the global context: Dograh Inc\n\nPlease provide your details."
        )
        assert system_message["content"] == expected_content

    @pytest.mark.asyncio
    async def test_no_global_node_scenario(self, engine):
        """Test behavior when there's no global node in the workflow."""
        # Remove global node from workflow
        engine.workflow.global_node_id = None

        start_node = engine.workflow.nodes["start"]
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(start_node)

        # Should only have the node's own prompt
        assert system_message["content"] == "Welcome to our service!"

    @pytest.mark.asyncio
    async def test_empty_global_prompt(self, engine):
        """Test behavior when global prompt is empty."""
        # Set global prompt to empty string
        engine.workflow.nodes["global"].prompt = ""

        start_node = engine.workflow.nodes["start"]
        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(start_node)

        # Should only have the node's own prompt (empty global prompt is filtered out)
        assert system_message["content"] == "Welcome to our service!"

    def test_default_add_global_prompt_value(self):
        """Test that add_global_prompt defaults to True in NodeDataDTO."""
        node_data = NodeDataDTO(name="Test", prompt="Test prompt")
        assert node_data.add_global_prompt is True

    @pytest.mark.asyncio
    async def test_multiple_prompts_concatenation(self, engine):
        """Test proper concatenation of global and node prompts."""
        # Test with agent2 node that has global prompt enabled
        agent2_node = engine.workflow.nodes["agent2"]

        (
            system_message,
            functions,
        ) = await engine._compose_system_message_functions_for_node(agent2_node)

        # Should have global and node prompts concatenated with double newlines
        # (extraction prompt is no longer included in system message)
        expected_parts = [
            "This is the global context: Dograh Inc",
            "Please provide your details.",
        ]
        expected_content = "\n\n".join(expected_parts)
        assert system_message["content"] == expected_content
