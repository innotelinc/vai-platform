from typing import Optional

from loguru import logger

from api.db import db_client
from api.services.campaign.call_dispatcher import campaign_call_dispatcher
from api.services.pipecat.audio_transcript_buffers import (
    InMemoryAudioBuffer,
    InMemoryTranscriptBuffer,
)
from api.services.pipecat.pipeline_metrics_aggregator import PipelineMetricsAggregator
from api.services.workflow.disposition_mapper import (
    apply_disposition_mapping,
    get_organization_id_from_workflow_run,
)
from api.services.workflow.pipecat_engine import PipecatEngine
from api.tasks.arq import enqueue_job
from api.tasks.function_names import FunctionNames
from pipecat.pipeline.task import PipelineTask
from pipecat.transports.base_transport import BaseTransport
from pipecat.utils.enums import EndTaskReason


def register_transport_event_handlers(
    transport,
    workflow_run_id,
    audio_buffer,
    task: PipelineTask,
    engine: PipecatEngine,
    usage_metrics_aggregator: PipelineMetricsAggregator,
    audio_synchronizer=None,
    audio_config=None,
):
    """Register event handlers for transport events"""

    # Initialize in-memory buffers with proper audio configuration
    sample_rate = audio_config.pipeline_sample_rate if audio_config else 16000
    num_channels = 1  # Pipeline audio is always mono

    logger.debug(
        f"Initializing audio buffer for workflow {workflow_run_id} "
        f"with sample_rate={sample_rate}Hz, channels={num_channels}"
    )

    in_memory_audio_buffer = InMemoryAudioBuffer(
        workflow_run_id=workflow_run_id,
        sample_rate=sample_rate,
        num_channels=num_channels,
    )
    in_memory_transcript_buffer = InMemoryTranscriptBuffer(workflow_run_id)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, participant):
        logger.debug("In on_client_connected callback handler - initializing workflow")
        await audio_buffer.start_recording()
        if audio_synchronizer:
            await audio_synchronizer.start_recording()
        await engine.initialize()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(
        transport: BaseTransport,
        participant,
        transport_disconnect_reason: Optional[str] = None,
    ):
        logger.debug(
            f"In on_client_disconnected callback handler, disconnect_reason: {transport_disconnect_reason}"
        )

        workflow_run = await db_client.get_workflow_run_by_id(workflow_run_id)

        # First priority: Check if engine has a disconnect reason (local disconnect)
        engine_call_disposition = engine.get_call_disposition()
        gathered_context = engine.get_gathered_context()

        # also consider existing gathered context in workflow_run
        gathered_context = {**gathered_context, **workflow_run.gathered_context}

        if engine_call_disposition:
            # Engine has set a disconnect reason - this takes priority
            call_disposition = engine_call_disposition
            logger.debug(f"Engine disposition detected, code: {call_disposition}")
        elif transport_disconnect_reason:
            # TODO: Make this more generic using some DSL or equivalent. This is currently
            # configured to work for Kapil's bot
            call_duration = usage_metrics_aggregator.get_call_duration()
            if transport_disconnect_reason == EndTaskReason.USER_HANGUP.value:
                if call_duration < 10:
                    call_disposition = "HU"
                else:
                    call_disposition = "NIBP"
            else:
                # Transport provided a disconnect reason (remote hangup)
                call_disposition = transport_disconnect_reason
            logger.debug(
                f"Remote disconnect detected, reason: {call_disposition} duration: {call_duration}"
            )
        else:
            # No reason provided - assume user hangup
            call_disposition = EndTaskReason.UNKNOWN.value
            logger.debug("No disposition found from either engine or transport")

        # Cancel task only when no engine disconnect reason (remote disconnect)
        if not engine_call_disposition:
            await task.cancel()

        organization_id = await get_organization_id_from_workflow_run(workflow_run_id)
        mapped_call_disposition = await apply_disposition_mapping(
            call_disposition, organization_id
        )

        gathered_context.update({"mapped_call_disposition": mapped_call_disposition})

        if in_memory_transcript_buffer:
            call_tags = gathered_context.get("call_tags", [])

            try:
                has_user_speech = in_memory_transcript_buffer.contains_user_speech()
            except Exception:
                has_user_speech = False

            if has_user_speech and "user_speech" not in call_tags:
                call_tags.append("user_speech")

            # Append any keys from gathered_context that start with 'tag_' to call_tags
            for key in gathered_context:
                if key.startswith("tag_") and key not in call_tags:
                    call_tags.append(gathered_context[key])

            gathered_context["call_tags"] = call_tags

        # Clean up engine resources (including voicemail detector)
        await engine.cleanup()

        await audio_buffer.stop_recording()
        if audio_synchronizer:
            await audio_synchronizer.stop_recording()

        # ------------------------------------------------------------------
        # Close Smart-Turn WebSocket if the transport's analyzer supports it
        # ------------------------------------------------------------------
        try:
            turn_analyzer = None

            # Most transports store their params (with turn_analyzer) directly.
            if hasattr(transport, "_params") and transport._params:
                turn_analyzer = getattr(transport._params, "turn_analyzer", None)

            # Fallback: some transports expose params through input() instance.
            if turn_analyzer is None and hasattr(transport, "input"):
                try:
                    input_transport = transport.input()
                    if input_transport and hasattr(input_transport, "_params"):
                        turn_analyzer = getattr(
                            input_transport._params, "turn_analyzer", None
                        )
                except Exception:
                    pass

            if turn_analyzer and hasattr(turn_analyzer, "close"):
                await turn_analyzer.close()
                logger.debug("Closed turn analyzer websocket")
        except Exception as exc:
            logger.warning(f"Failed to close Smart-Turn analyzer gracefully: {exc}")

        usage_info = usage_metrics_aggregator.get_all_usage_metrics_serialized()

        logger.debug(f"Usage metrics: {usage_info}")

        await db_client.update_workflow_run(
            run_id=workflow_run_id,
            usage_info=usage_info,
            gathered_context=gathered_context,
            is_completed=True,
        )

        # Release concurrent slot for campaign calls
        if workflow_run and workflow_run.campaign_id:
            await campaign_call_dispatcher.release_call_slot(workflow_run_id)

        # Write buffers to temp files and enqueue S3 upload
        try:
            # Only upload if buffers have content
            if not in_memory_audio_buffer.is_empty:
                audio_temp_path = await in_memory_audio_buffer.write_to_temp_file()
                await enqueue_job(
                    FunctionNames.UPLOAD_AUDIO_TO_S3, workflow_run_id, audio_temp_path
                )
            else:
                logger.debug("Audio buffer is empty, skipping upload")

            if not in_memory_transcript_buffer.is_empty:
                transcript_temp_path = (
                    await in_memory_transcript_buffer.write_to_temp_file()
                )
                await enqueue_job(
                    FunctionNames.UPLOAD_TRANSCRIPT_TO_S3,
                    workflow_run_id,
                    transcript_temp_path,
                )
            else:
                logger.debug("Transcript buffer is empty, skipping upload")

        except Exception as e:
            logger.error(f"Error preparing buffers for S3 upload: {e}", exc_info=True)

        await enqueue_job(FunctionNames.CALCULATE_WORKFLOW_RUN_COST, workflow_run_id)
        await enqueue_job(
            FunctionNames.RUN_INTEGRATIONS_POST_WORKFLOW_RUN, workflow_run_id
        )

    # Return the buffers so they can be passed to other handlers
    return in_memory_audio_buffer, in_memory_transcript_buffer


def register_audio_data_handler(
    audio_synchronizer, workflow_run_id, in_memory_buffer: InMemoryAudioBuffer
):
    """Register event handler for audio data"""
    logger.info(f"Registering audio data handler for workflow run {workflow_run_id}")

    @audio_synchronizer.event_handler("on_merged_audio")
    async def on_merged_audio(_, pcm, sample_rate, num_channels):
        if not pcm:
            return

        # Use in-memory buffer
        try:
            await in_memory_buffer.append(pcm)
        except MemoryError as e:
            logger.error(f"Memory buffer full: {e}")
            # Could implement overflow to disk here if needed


def register_transcript_handler(
    transcript, workflow_run_id, in_memory_buffer: InMemoryTranscriptBuffer
):
    """Register event handler for transcript updates"""

    @transcript.event_handler("on_transcript_update")
    async def on_transcript_update(processor, frame):
        transcript_text = ""
        for msg in frame.messages:
            timestamp = f"[{msg.timestamp}] " if msg.timestamp else ""
            line = f"{timestamp}{msg.role}: {msg.content}\n"
            transcript_text += line

        # Use in-memory buffer
        await in_memory_buffer.append(transcript_text)
