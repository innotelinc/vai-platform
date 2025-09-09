"""Engine Pre-Aggregator Processor

This processor sits before the user context aggregator in the pipeline and handles
engine-specific callbacks for frames that need to be processed before aggregation.
This ensures the engine can update context before the aggregator generates LLM frames.
"""

from typing import Awaitable, Callable, Optional

from loguru import logger

from api.services.pipecat.exceptions import VoicemailDetectedException
from pipecat.frames.frames import (
    Frame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class EnginePreAggregatorProcessor(FrameProcessor):
    """
    Processor that handles engine callbacks before user context aggregation.

    This processor is positioned before the user context aggregator to ensure
    the engine can update LLM context before aggregation occurs.
    """

    def __init__(
        self,
        user_started_speaking_callback: Optional[Callable[[], Awaitable[None]]] = None,
        user_stopped_speaking_callback: Optional[Callable[[], Awaitable[None]]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._user_started_speaking_callback = user_started_speaking_callback
        self._user_stopped_speaking_callback = user_stopped_speaking_callback

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Handle frames that need engine processing before aggregation
        if isinstance(frame, UserStartedSpeakingFrame):
            await self._handle_user_started_speaking()
        elif isinstance(frame, UserStoppedSpeakingFrame):
            try:
                await self._handle_user_stopped_speaking()
            except VoicemailDetectedException:
                # We have detected voicemail, lets not
                # forward the UserStoppedSpeakingFrame, so that
                # we don't issue an llm call from user context
                # aggregator
                logger.debug("Voicemail detected, not pushing UserStoppedSpeakingFrame")
                return

        # Always push the frame downstream
        await self.push_frame(frame, direction)

    async def _handle_user_started_speaking(self):
        """Handle UserStartedSpeakingFrame before aggregation."""
        if self._user_started_speaking_callback:
            # logger.debug("Engine pre-aggregator: User started speaking")
            await self._user_started_speaking_callback()

    async def _handle_user_stopped_speaking(self):
        """Handle UserStoppedSpeakingFrame before aggregation."""
        if self._user_stopped_speaking_callback:
            # logger.debug("Engine pre-aggregator: User stopped speaking")
            await self._user_stopped_speaking_callback()
