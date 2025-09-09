"""Redis communication protocol for distributed ARI architecture.

Defines message formats and helpers for ARI Manager <-> Worker communication.
"""

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    """Types of events sent from ARI Manager to Workers."""

    STASIS_START = "stasis_start"
    STASIS_END = "stasis_end"
    CHANNEL_UPDATE = "channel_update"
    ERROR = "error"


class CommandType(str, Enum):
    """Types of commands sent from Workers to ARI Manager."""

    DISCONNECT = "disconnect"
    TRANSFER = "transfer"
    UPDATE_STATE = "update_state"
    SOCKET_CLOSED = "socket_closed"


@dataclass
class BaseWorkerToARIManagerCommand:
    """Base class for all commands sent from Workers to ARI Manager."""

    type: str
    channel_id: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str):
        return cls(**json.loads(data))


@dataclass
class StasisStartEvent:
    """Event sent when a new call is bridged and ready."""

    type: str = EventType.STASIS_START
    channel_id: str = ""
    caller_channel_id: str = ""
    em_channel_id: Optional[str] = None
    bridge_id: Optional[str] = None
    local_addr: List[Any] = None  # [host, port]
    remote_addr: Optional[List[Any]] = None  # [host, port] with UNICASTRTP_LOCAL_PORT
    call_context_vars: Dict[str, Any] = None

    def __post_init__(self):
        if self.local_addr is None:
            self.local_addr = []
        if self.call_context_vars is None:
            self.call_context_vars = {}

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "StasisStartEvent":
        return cls(**json.loads(data))


@dataclass
class StasisEndEvent:
    """Event sent when a call ends."""

    type: str = EventType.STASIS_END
    channel_id: str = ""
    reason: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "StasisEndEvent":
        return cls(**json.loads(data))


@dataclass
class DisconnectCommand(BaseWorkerToARIManagerCommand):
    """Command to disconnect a call."""

    type: str = CommandType.DISCONNECT
    reason: str = "worker_requested"


@dataclass
class TransferCommand(BaseWorkerToARIManagerCommand):
    """Command to transfer a call."""

    type: str = CommandType.TRANSFER
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass
class SocketClosedCommand(BaseWorkerToARIManagerCommand):
    """Command to notify that RTP sockets have been closed."""

    type: str = CommandType.SOCKET_CLOSED


class RedisChannels:
    """Redis channel naming conventions."""

    @staticmethod
    def worker_events(worker_id: str) -> str:
        """Channel for events sent to a specific worker."""
        return f"ari:events:worker:{worker_id}"

    @staticmethod
    def channel_commands(channel_id: str) -> str:
        """Channel for commands related to a specific call channel."""
        return f"ari:commands:{channel_id}"

    @staticmethod
    def channel_updates(channel_id: str) -> str:
        """Channel for state updates about a specific call."""
        return f"ari:updates:{channel_id}"


class RedisKeys:
    """Redis key naming conventions for worker registration and discovery."""

    @staticmethod
    def worker_active(worker_id: str) -> str:
        """Key for active worker status and metadata."""
        return f"workers:active:{worker_id}"

    @staticmethod
    def workers_set() -> str:
        """Set containing all registered worker IDs."""
        return "workers:set"

    @staticmethod
    def round_robin_index() -> str:
        """Counter for round-robin worker selection."""
        return "workers:round_robin:index"


def parse_event(data: str) -> Any:
    """Parse a Redis event message."""
    try:
        parsed = json.loads(data)
        event_type = parsed.get("type")

        if event_type == EventType.STASIS_START:
            return StasisStartEvent(**parsed)
        elif event_type == EventType.STASIS_END:
            return StasisEndEvent(**parsed)
        else:
            return parsed
    except Exception:
        return None


def parse_command(data: str) -> Any:
    """Parse a Redis command message."""
    try:
        parsed = json.loads(data)
        cmd_type = parsed.get("type")

        if cmd_type == CommandType.DISCONNECT:
            return DisconnectCommand(**parsed)
        elif cmd_type == CommandType.TRANSFER:
            return TransferCommand(**parsed)
        elif cmd_type == CommandType.SOCKET_CLOSED:
            return SocketClosedCommand(**parsed)
        else:
            return parsed
    except Exception:
        return None
