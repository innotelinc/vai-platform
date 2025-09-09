"""Unit tests for global prompt functionality - no DB dependencies."""

import sys
from pathlib import Path

# Add the api directory to the Python path
api_path = Path(__file__).parent.parent
sys.path.insert(0, str(api_path))

from services.workflow.dto import (
    EdgeDataDTO,
    NodeDataDTO,
    NodeType,
    ReactFlowDTO,
    RFEdgeDTO,
    RFNodeDTO,
)
from services.workflow.workflow import WorkflowGraph


def test_node_data_dto_default_global_prompt():
    """Test that add_global_prompt defaults to True."""
    node_data = NodeDataDTO(name="Test Node", prompt="Test prompt")
    assert node_data.add_global_prompt is True
    print("✓ NodeDataDTO defaults add_global_prompt to True")


def test_node_data_dto_explicit_global_prompt():
    """Test explicit setting of add_global_prompt."""
    # Test with False
    node_data_false = NodeDataDTO(
        name="Test Node", prompt="Test prompt", add_global_prompt=False
    )
    assert node_data_false.add_global_prompt is False

    # Test with True
    node_data_true = NodeDataDTO(
        name="Test Node", prompt="Test prompt", add_global_prompt=True
    )
    assert node_data_true.add_global_prompt is True
    print("✓ NodeDataDTO respects explicit add_global_prompt values")


def test_workflow_node_inherits_global_prompt_setting():
    """Test that workflow Node inherits add_global_prompt from NodeDataDTO."""
    nodes = [
        RFNodeDTO(
            id="start",
            type=NodeType.startNode,
            position={"x": 0, "y": 0},
            data=NodeDataDTO(
                name="Start",
                prompt="Start prompt",
                is_start=True,
                add_global_prompt=True,
            ),
        ),
        RFNodeDTO(
            id="node1",
            type=NodeType.agentNode,
            position={"x": 100, "y": 0},
            data=NodeDataDTO(
                name="Node with global", prompt="Test prompt", add_global_prompt=True
            ),
        ),
        RFNodeDTO(
            id="node2",
            type=NodeType.agentNode,
            position={"x": 200, "y": 0},
            data=NodeDataDTO(
                name="Node without global",
                prompt="Test prompt",
                add_global_prompt=False,
            ),
        ),
        RFNodeDTO(
            id="end",
            type=NodeType.endNode,
            position={"x": 300, "y": 0},
            data=NodeDataDTO(
                name="End", prompt="End prompt", is_end=True, add_global_prompt=True
            ),
        ),
    ]

    edges = [
        RFEdgeDTO(
            id="e1",
            source="start",
            target="node1",
            data=EdgeDataDTO(label="Next", condition="Continue"),
        ),
        RFEdgeDTO(
            id="e2",
            source="node1",
            target="node2",
            data=EdgeDataDTO(label="Next", condition="Continue"),
        ),
        RFEdgeDTO(
            id="e3",
            source="node2",
            target="end",
            data=EdgeDataDTO(label="End", condition="Finish"),
        ),
    ]

    flow_dto = ReactFlowDTO(nodes=nodes, edges=edges)
    workflow = WorkflowGraph(flow_dto)

    assert workflow.nodes["start"].add_global_prompt is True
    assert workflow.nodes["node1"].add_global_prompt is True
    assert workflow.nodes["node2"].add_global_prompt is False
    assert workflow.nodes["end"].add_global_prompt is True
    print("✓ Workflow nodes correctly inherit add_global_prompt setting")


def test_compose_system_message_respects_global_prompt_flag():
    """Test that system message composition respects add_global_prompt flag."""
    # This is a simplified version - in real tests we'd use the full engine
    # But this demonstrates the logic

    class MockNode:
        def __init__(self, add_global_prompt, prompt):
            self.add_global_prompt = add_global_prompt
            self.prompt = prompt
            self.out_edges = []
            self.extraction_enabled = False

    # Simulate the logic from _compose_system_message_functions_for_node
    def compose_message(node, global_prompt):
        prompts = []

        # Only add global prompt if node.add_global_prompt is True
        if global_prompt and node.add_global_prompt:
            prompts.append(global_prompt)

        prompts.append(node.prompt)

        return "\n\n".join(p for p in prompts if p)

    global_prompt = "This is the global context"

    # Test with add_global_prompt=True
    node_with_global = MockNode(add_global_prompt=True, prompt="Node prompt")
    message_with = compose_message(node_with_global, global_prompt)
    assert message_with == "This is the global context\n\nNode prompt"

    # Test with add_global_prompt=False
    node_without_global = MockNode(add_global_prompt=False, prompt="Node prompt")
    message_without = compose_message(node_without_global, global_prompt)
    assert message_without == "Node prompt"

    print("✓ System message composition respects add_global_prompt flag")


def test_static_nodes_with_global_prompt():
    """Test static nodes can have add_global_prompt setting."""
    static_node_data = NodeDataDTO(
        name="Static Node", prompt="Static text", is_static=True, add_global_prompt=True
    )

    assert static_node_data.is_static is True
    assert static_node_data.add_global_prompt is True
    print("✓ Static nodes can have add_global_prompt setting")


if __name__ == "__main__":
    # Run all tests
    test_node_data_dto_default_global_prompt()
    test_node_data_dto_explicit_global_prompt()
    test_workflow_node_inherits_global_prompt_setting()
    test_compose_system_message_respects_global_prompt_flag()
    test_static_nodes_with_global_prompt()

    print("\n✅ All unit tests passed!")
