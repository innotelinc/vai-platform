"""Stasis RTP connection for worker processes.

This connection works without direct ARI access and communicates with
the ARI Manager via Redis for all control operations.
"""

from typing import Optional, Tuple

import redis.asyncio as aioredis
from loguru import logger
from pipecat.utils.base_object import BaseObject
from pipecat.utils.enums import EndTaskReason

from api.services.telephony.stasis_event_protocol import (
    DisconnectCommand,
    RedisChannels,
    SocketClosedCommand,
    TransferCommand,
)


class StasisRTPConnection(BaseObject):
    """Worker-side connection that communicates with ARI Manager via Redis.

    This class provides the same API as the original StasisRTPConnection but
    without direct ARI client access. All channel operations are delegated
    to the ARI Manager process via Redis.
    """

    _SUPPORTED_EVENTS = [
        "connecting",
        "connected",
        "disconnected",
        "closed",
        "failed",
        "new",
    ]

    def __init__(
        self,
        redis_client: aioredis.Redis,
        channel_id: str,
        caller_channel_id: str,
        em_channel_id: Optional[str],
        bridge_id: Optional[str],
        local_addr: Optional[Tuple[str, int]],
        remote_addr: Optional[Tuple[str, int]],
        workflow_run_id: Optional[int] = None,
    ):
        """Initialize distributed connection with pre-established details.

        Args:
            redis_client: Redis client for communication
            channel_id: Primary channel ID for this connection
            caller_channel_id: Caller's channel ID
            em_channel_id: External media channel ID
            bridge_id: Bridge ID (already created by ARI Manager)
            local_addr: Local RTP address (host, port)
            remote_addr: Remote RTP address with UNICASTRTP_LOCAL_PORT
            workflow_run_id: Workflow run ID for logging context
        """
        super().__init__()

        self.redis = redis_client
        self.channel_id = channel_id
        self.caller_channel_id = caller_channel_id
        self.em_channel_id = em_channel_id
        self.bridge_id = bridge_id
        self.workflow_run_id = workflow_run_id

        # RTP addressing (same as StasisRTPConnection)
        self.local_addr = local_addr
        self.remote_addr = remote_addr

        # State tracking
        # self._closed_by_stasis_end should only be set True after we get
        # StasisEnd from the transport
        self._closed_by_stasis_end = False

        self._connect_invoked = False

        # Register event handlers
        for evt in self._SUPPORTED_EVENTS:
            self._register_event_handler(evt)

        logger.debug(
            f"channelID: {channel_id} StasisRTPConnection created: "
            f"bridgeID: {bridge_id}, local_addr={local_addr}, remote_addr={remote_addr}"
        )

    async def connect(self):
        """Signal readiness to start the call.

        Since the bridge is already established by ARI Manager,
        we can immediately trigger the connected event.
        """
        self._connect_invoked = True
        if self.is_connected():
            await self._call_event_handler("connected")
        else:
            logger.warning(
                "StasisRTPConnection is not connected - did not call connected handler"
            )

    async def disconnect(self, reason: str):
        """Request disconnection via Redis command to ARI Manager. Usually called
        when there is a disconnect triggered by workflow"""
        # If we have already received user hangup via StasisEnd, lets
        # return
        if self._closed_by_stasis_end:
            return

        logger.info(f"channelID: {self.channel_id} Requesting disconnect: {reason}")

        # Send disconnect command to ARI Manager
        command = DisconnectCommand(channel_id=self.channel_id, reason=reason)
        channel = RedisChannels.channel_commands(self.channel_id)
        await self.redis.publish(channel, command.to_json())

    async def transfer(self, call_transfer_context: dict):
        """Request call transfer via Redis command to ARI Manager."""
        # If we have already received user hangup via StasisEnd, lets
        # return
        if self._closed_by_stasis_end:
            return

        logger.info(f"channelID: {self.channel_id} Requesting transfer")

        # Send transfer command to ARI Manager
        command = TransferCommand(
            channel_id=self.channel_id, context=call_transfer_context
        )
        channel = RedisChannels.channel_commands(self.channel_id)
        await self.redis.publish(channel, command.to_json())

    async def notify_sockets_closed(self):
        """Notify ARI Manager that RTP sockets have been closed."""
        logger.info(
            f"channelID: {self.channel_id} Notifying ARI Manager that sockets are closed"
        )

        # Send socket_closed command to ARI Manager
        command = SocketClosedCommand(channel_id=self.channel_id)
        channel = RedisChannels.channel_commands(self.channel_id)
        await self.redis.publish(channel, command.to_json())

    def is_connected(self) -> bool:
        """Check if connection is established.

        Returns True once connect() has been called and connection is not closed.
        """
        return self._connect_invoked and not self._closed_by_stasis_end

    async def handle_remote_disconnect(self, reason: str = EndTaskReason.UNKNOWN.value):
        """Handle disconnection initiated by ARI Manager. Is called when the user hangs up."""
        if self._closed_by_stasis_end:
            return

        self._closed_by_stasis_end = True

        if self._connect_invoked:
            # Unless self._connect_invoked is True, the event handlers won't be registered. We only
            # register the event handler of client when the transports are initiated during pipeline
            # initialisation. Any caller must check and wait for _connect_invoked before
            # calling the method
            await self._call_event_handler("disconnected", reason)
        else:
            logger.warning(
                f"ChannelID: {self.channel_id} Got remote disconnect before connection was invoked"
            )

        logger.info(
            f"channelID: {self.channel_id} StasisRTPConnection disconnected: {reason}"
        )

    def __repr__(self):
        """String representation of connection."""
        return (
            f"<StasisRTPConnection id={self.id} channel={self.channel_id} "
            f"caller={self.caller_channel_id} em={self.em_channel_id} "
            f"state={'closed' if self._closed_by_stasis_end else 'open'}>"
        )
