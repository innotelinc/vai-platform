from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator


class NodeType(str, Enum):
    startNode = "startCall"
    endNode = "endCall"
    agentNode = "agentNode"
    globalNode = "globalNode"


class Position(BaseModel):
    x: float
    y: float


class VariableType(str, Enum):
    string = "string"
    number = "number"
    boolean = "boolean"


class ExtractionVariableDTO(BaseModel):
    name: str = Field(..., min_length=1)
    type: VariableType
    prompt: Optional[str] = None


class NodeDataDTO(BaseModel):
    name: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    is_static: bool = False
    is_start: bool = False
    is_end: bool = False
    allow_interrupt: bool = False
    extraction_enabled: bool = False
    extraction_prompt: Optional[str] = None
    extraction_variables: Optional[list[ExtractionVariableDTO]] = None
    add_global_prompt: bool = True
    wait_for_user_response: bool = False
    wait_for_user_response_timeout: Optional[float] = None
    detect_voicemail: bool = True
    delayed_start: bool = False
    delayed_start_duration: Optional[float] = None


class RFNodeDTO(BaseModel):
    id: str
    type: NodeType = Field(default=NodeType.agentNode)
    position: Position
    data: NodeDataDTO


class EdgeDataDTO(BaseModel):
    label: str = Field(..., min_length=1)
    condition: str = Field(..., min_length=1)


class RFEdgeDTO(BaseModel):
    id: str
    source: str
    target: str
    data: EdgeDataDTO


class ReactFlowDTO(BaseModel):
    nodes: List[RFNodeDTO]
    edges: List[RFEdgeDTO]

    @model_validator(mode="after")
    def _referential_integrity(self):
        node_ids = {n.id for n in self.nodes}
        line_errors: list[dict[str, str]] = []

        for idx, edge in enumerate(self.edges):
            for endpoint in (edge.source, edge.target):
                if endpoint not in node_ids:
                    line_errors.append(
                        dict(
                            loc=("edges", idx),
                            type="missing_node",
                            msg="Edge references missing node",
                            input=edge.model_dump(mode="python"),
                            ctx={"edge_id": edge.id, "endpoint": endpoint},
                        )
                    )

        if line_errors:
            raise ValidationError.from_exception_data(
                title="ReactFlowDTO validation failed",
                line_errors=line_errors,
            )

        return self
