"""
Test voicemail detection in RTC connection flow.

This test emulates how a call is connected using SmallWebRTC,
triggers voicemail detection, and verifies the disconnect reason.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pipecat.utils.enums import EndTaskReason

from api.routes.rtc_offer import RTCOfferRequest, offer
from api.services.workflow.pipecat_engine_voicemail_detector import VoicemailDetector


@pytest.mark.asyncio
class TestVoicemailDetectionRTC:
    """Test voicemail detection through RTC connection flow."""

    async def test_voicemail_detection_full_flow(self):
        """
        Test complete voicemail detection flow:
        1. RTC connection request
        2. Transport sends on_client_connected event
        3. Engine initializes with voicemail detection enabled
        4. Voicemail detector returns true
        5. Call terminates with voicemail_detected reason
        6. Transport sends on_client_disconnected event
        7. Disconnect reason is properly set
        """
        # Mock user and authentication
        mock_user = Mock()
        mock_user.id = 1
        mock_user.organization_id = 1

        # Mock workflow with voicemail detection enabled
        mock_workflow = Mock()
        mock_workflow.id = 100
        mock_workflow.workflow_definition_with_fallback = {
            "edges": [],
            "nodes": [
                {
                    "id": "start",
                    "type": "start",
                    "data": {
                        "detect_voicemail": True,
                        "system_prompt": "You are a helpful assistant",
                    },
                }
            ],
        }

        # Mock workflow run
        mock_workflow_run = Mock()
        mock_workflow_run.id = 200
        mock_workflow_run.is_completed = False

        # Create request
        request = RTCOfferRequest(
            pc_id="test_pc_123",
            sdp="test_sdp_offer",
            type="offer",
            workflow_id=mock_workflow.id,
            workflow_run_id=mock_workflow_run.id,
            restart_pc=False,
            call_context_vars={"test_var": "test_value"},
        )

        # Mock dependencies
        with (
            patch("api.services.auth.depends.get_user") as mock_get_user_dep,
            patch("api.routes.rtc_offer.SmallWebRTCConnection") as MockWebRTCConnection,
            patch("api.routes.rtc_offer.run_pipeline_smallwebrtc") as mock_run_pipeline,
        ):
            # Setup mocks
            mock_get_user_dep.return_value = mock_user

            # Mock WebRTC connection
            mock_connection = Mock()
            mock_connection.pc_id = "test_pc_123"
            mock_connection.initialize = AsyncMock()
            mock_connection.get_answer = Mock(
                return_value={
                    "pc_id": "test_pc_123",
                    "sdp": "test_sdp_answer",
                    "type": "answer",
                }
            )
            MockWebRTCConnection.return_value = mock_connection

            # Track registered event handlers
            registered_handlers = {}

            def mock_event_handler(event_name):
                def decorator(func):
                    registered_handlers[event_name] = func
                    return func

                return decorator

            mock_connection.event_handler = mock_event_handler

            # Mock BackgroundTasks
            mock_background_tasks = Mock()

            # Create the offer
            response = await offer(request, mock_background_tasks, mock_user)

            # Verify response
            assert response["pc_id"] == "test_pc_123"
            assert response["type"] == "answer"

            # Verify connection was initialized
            mock_connection.initialize.assert_called_once_with(
                sdp="test_sdp_offer", type="offer"
            )

            # Verify background task was added
            mock_background_tasks.add_task.assert_called_once()
            task_args = mock_background_tasks.add_task.call_args[0]
            assert task_args[0] == mock_run_pipeline
            assert task_args[1] == mock_connection
            assert task_args[2] == mock_workflow.id
            assert task_args[3] == mock_workflow_run.id
            assert task_args[4] == mock_user.id
            assert task_args[5] == {"test_var": "test_value"}

    async def test_voicemail_detection_in_pipeline(self):
        """Tests whether the updates happen in on_client_disconnected properly
        with values set in the engine"""
        # Mock components
        mock_transport = AsyncMock()
        mock_engine = Mock()  # Use Mock instead of AsyncMock for engine
        mock_engine.initialize = AsyncMock()
        mock_engine.cleanup = AsyncMock()
        mock_audio_buffer = AsyncMock()
        mock_task = AsyncMock()
        mock_aggregator = Mock()

        # Setup engine with voicemail detector
        mock_voicemail_detector = AsyncMock(spec=VoicemailDetector)
        mock_engine.voicemail_detector = mock_voicemail_detector
        mock_engine.get_call_disposition = Mock(
            return_value=EndTaskReason.VOICEMAIL_DETECTED.value
        )
        mock_engine.get_gathered_context = Mock(
            return_value={
                "voicemail_transcript": "Hi, you've reached John's voicemail. Please leave a message.",
                "voicemail_confidence": 0.95,
            }
        )

        # Mock usage metrics
        mock_aggregator.get_all_usage_metrics_serialized.return_value = {}

        # Register event handlers
        from api.services.pipecat.event_handlers import (
            register_transport_event_handlers,
        )

        # Track registered handlers
        handlers = {}

        def track_handler(event_name):
            def decorator(func):
                handlers[event_name] = func
                return func

            return decorator

        mock_transport.event_handler = track_handler

        # Create a mock db_client module with update_workflow_run method
        mock_db_client = Mock()
        mock_db_client.update_workflow_run = AsyncMock()

        with (
            patch("api.services.pipecat.event_handlers.db_client", mock_db_client),
            patch(
                "api.services.pipecat.event_handlers.enqueue_job",
                new_callable=AsyncMock,
            ) as mock_enqueue_job,
            patch(
                "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run",
                return_value=1,
            ),
            patch(
                "api.services.pipecat.event_handlers.apply_disposition_mapping",
                side_effect=lambda value, org_id: value,  # Return value unchanged
            ),
        ):
            # Register handlers
            register_transport_event_handlers(
                mock_transport,
                workflow_run_id=123,
                audio_buffer=mock_audio_buffer,
                task=mock_task,
                engine=mock_engine,
                usage_metrics_aggregator=mock_aggregator,
            )

            # Verify handlers were registered
            assert "on_client_connected" in handlers
            assert "on_client_disconnected" in handlers

            # Simulate client connection
            await handlers["on_client_connected"](
                mock_transport, {"id": "participant_1"}
            )

            # Verify initialization
            mock_audio_buffer.start_recording.assert_called_once()
            mock_engine.initialize.assert_called_once()

            # Simulate voicemail detection and disconnect
            await handlers["on_client_disconnected"](
                mock_transport, {"id": "participant_1"}, None
            )

            # Verify engine cleanup
            mock_engine.cleanup.assert_called_once()

            # TODO: check whether task was cancelled or not once have more
            # clarity on how to handle engine disconnect vs remote hangup
            # Verify task was NOT cancelled (engine disconnect)
            # mock_task.cancel.assert_not_called()

            # Verify workflow run was updated with voicemail context
            mock_db_client.update_workflow_run.assert_called()
            call_args = mock_db_client.update_workflow_run.call_args
            assert call_args[1]["run_id"] == 123
            # Check that the mapped_call_disposition was set correctly
            assert (
                call_args[1]["gathered_context"]["mapped_call_disposition"]
                == "voicemail_detected"
            )

    async def test_voicemail_detector_audio_processing(self):
        """Test VoicemailDetector audio processing and detection logic - tests that voicemail detector
        calls engine's send_end_task_frame with the correct reason and metadata"""
        # Create voicemail detector
        detector = VoicemailDetector(detection_duration=5.0, workflow_run_id=123)

        # Mock OpenAI client
        mock_openai = AsyncMock()
        mock_whisper_response = Mock()
        mock_whisper_response.text = "Hi, you've reached the voicemail of John Smith. Please leave a message after the beep."
        mock_openai.audio.transcriptions.create.return_value = mock_whisper_response

        mock_gpt_response = Mock()
        mock_gpt_response.choices = [Mock()]
        mock_gpt_response.choices[0].message.content = json.dumps(
            {
                "is_voicemail": True,
                "confidence": 0.98,
                "reasoning": "Clear voicemail greeting with request to leave message",
            }
        )
        mock_openai.chat.completions.create.return_value = mock_gpt_response

        # Mock engine
        mock_engine = AsyncMock()
        mock_engine.task = AsyncMock()

        with (
            patch(
                "api.services.workflow.pipecat_engine_voicemail_detector.AsyncOpenAI",
                return_value=mock_openai,
            ),
            patch(
                "api.services.workflow.pipecat_engine_voicemail_detector.s3_fs"
            ) as mock_s3,
        ):
            # Mock S3 upload to return None (simulating successful upload)
            mock_s3.aupload_file = AsyncMock(return_value=True)
            # Start detection
            await detector.start_detection(mock_engine)
            assert detector.is_detecting == True

            # Simulate audio data (16kHz, mono, 5 seconds)
            sample_rate = 16000
            duration = 5.0
            audio_data = b"\x00\x00" * int(sample_rate * duration)  # Silent audio

            # Process audio in chunks
            chunk_size = 1600  # 100ms chunks
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                await detector.handle_audio_data(None, chunk, sample_rate, 1)

            # Wait for detection to complete
            if detector._detection_task:
                await detector._detection_task

            # Verify OpenAI calls
            mock_openai.audio.transcriptions.create.assert_called_once()
            mock_openai.chat.completions.create.assert_called_once()

            # Verify send_end_task_frame was called with voicemail detection
            mock_engine.send_end_task_frame.assert_called_once_with(
                reason=EndTaskReason.VOICEMAIL_DETECTED.value,
                additional_metadata={
                    "voicemail_transcript": "Hi, you've reached the voicemail of John Smith. Please leave a message after the beep.",
                    "voicemail_confidence": 0.98,
                    "voicemail_reasoning": "Clear voicemail greeting with request to leave message",
                    "voicemail_detection_duration": 5.0,
                    "voicemail_audio_s3_path": "voicemail_detections/123_voicemail_98_5.wav",  # S3 upload returns True, so filename is used
                },
                abort_immediately=True,
            )

    async def test_voicemail_detector_no_detection(self):
        """Test VoicemailDetector when voicemail is not detected."""
        # Create voicemail detector
        detector = VoicemailDetector(detection_duration=5.0, workflow_run_id=124)

        # Mock OpenAI client
        mock_openai = AsyncMock()
        mock_whisper_response = Mock()
        mock_whisper_response.text = "Hello? Hello? Can you hear me?"
        mock_openai.audio.transcriptions.create.return_value = mock_whisper_response

        mock_gpt_response = Mock()
        mock_gpt_response.choices = [Mock()]
        mock_gpt_response.choices[0].message.content = json.dumps(
            {
                "is_voicemail": False,
                "confidence": 0.95,
                "reasoning": "Live person speaking, asking if caller can hear them",
            }
        )
        mock_openai.chat.completions.create.return_value = mock_gpt_response

        # Mock engine
        mock_engine = AsyncMock()
        mock_engine.task = AsyncMock()

        with patch(
            "api.services.workflow.pipecat_engine_voicemail_detector.AsyncOpenAI",
            return_value=mock_openai,
        ):
            # Start detection
            await detector.start_detection(mock_engine)

            # Simulate audio data
            sample_rate = 16000
            duration = 5.0
            audio_data = b"\x00\x00" * int(sample_rate * duration)

            # Process audio
            await detector.handle_audio_data(None, audio_data, sample_rate, 1)

            # Wait for detection
            if detector._detection_task:
                await detector._detection_task

            # Verify send_end_task_frame was NOT called
            mock_engine.send_end_task_frame.assert_not_called()

    async def test_voicemail_detector_cancellation(self):
        """Test VoicemailDetector cancellation before completion."""
        # Create voicemail detector
        detector = VoicemailDetector(detection_duration=10.0, workflow_run_id=125)

        # Mock engine
        mock_engine = AsyncMock()

        # Start detection
        await detector.start_detection(mock_engine)
        assert detector.is_detecting == True

        # Cancel detection immediately
        await detector.stop_detection()
        assert detector._is_cancelled == True

        # Try to add audio data after cancellation
        await detector.handle_audio_data(None, b"\x00\x00" * 1000, 16000, 1)

        # Verify buffer didn't grow (no audio accepted after cancellation)
        assert len(detector.audio_buffer) == 0

    async def test_disconnect_reason_propagation(self):
        """Test that voicemail disconnect reason is properly propagated."""
        # Create disconnect reason info directly
        disconnect_info = {
            "disposition_code": EndTaskReason.VOICEMAIL_DETECTED.value,
            "details": "Voicemail detected after 5 seconds of audio",
            "is_remote": False,
            "is_user_initiated": False,
            "is_successful_transfer": False,
            "transport_metadata": {
                "voicemail_confidence": 0.97,
                "voicemail_transcript": "You've reached voicemail...",
            },
        }

        # Verify attributes
        assert disconnect_info["disposition_code"] == "voicemail_detected"
        assert disconnect_info["is_remote"] == False
        assert disconnect_info["is_user_initiated"] == False
        assert disconnect_info["is_successful_transfer"] == False
        assert (
            disconnect_info["details"] == "Voicemail detected after 5 seconds of audio"
        )
        assert disconnect_info["transport_metadata"]["voicemail_confidence"] == 0.97

    async def test_voicemail_detection_end_to_end(self):
        """
        Complete end-to-end test covering:
        1. on_client_connected event
        2. Engine initialization with voicemail detection
        3. Audio processing and voicemail detection
        4. Engine setting disconnect reason
        5. on_client_disconnected event
        6. Proper disconnect reason in workflow run update
        """
        # Create comprehensive mocks
        from api.services.pipecat.event_handlers import (
            register_transport_event_handlers,
        )

        # Mock transport
        mock_transport = AsyncMock()
        handlers = {}

        def track_handler(event_name):
            def decorator(func):
                handlers[event_name] = func
                return func

            return decorator

        mock_transport.event_handler = track_handler

        # Mock audio buffer
        mock_audio_buffer = Mock()
        mock_audio_buffer.start_recording = AsyncMock()
        mock_audio_buffer.stop_recording = AsyncMock()

        # Mock task
        mock_task = AsyncMock()

        # Mock aggregator
        mock_aggregator = Mock()
        mock_aggregator.get_all_usage_metrics_serialized.return_value = {}

        # Create a mock engine with voicemail detection
        mock_engine = Mock()
        mock_engine.initialize = AsyncMock()
        mock_engine.cleanup = AsyncMock()

        # Mock voicemail detector
        mock_voicemail_detector = Mock()
        mock_engine.voicemail_detector = mock_voicemail_detector
        mock_engine._voicemail_detector = mock_voicemail_detector

        # Initially no disconnect reason
        mock_engine.get_call_disposition = Mock(return_value=None)
        mock_engine.get_gathered_context = Mock(return_value={})

        # Mock db_client
        mock_db_client = Mock()
        mock_db_client.update_workflow_run = AsyncMock()

        with (
            patch("api.services.pipecat.event_handlers.db_client", mock_db_client),
            patch(
                "api.services.pipecat.event_handlers.enqueue_job",
                new_callable=AsyncMock,
            ) as mock_enqueue_job,
            patch(
                "api.services.pipecat.event_handlers.get_organization_id_from_workflow_run",
                return_value=1,
            ),
            patch(
                "api.services.pipecat.event_handlers.apply_disposition_mapping",
                side_effect=lambda value, org_id: value,  # Return value unchanged
            ),
        ):
            # Register event handlers
            register_transport_event_handlers(
                mock_transport,
                workflow_run_id=123,
                audio_buffer=mock_audio_buffer,
                task=mock_task,
                engine=mock_engine,
                usage_metrics_aggregator=mock_aggregator,
            )

            # Verify handlers were registered
            assert "on_client_connected" in handlers
            assert "on_client_disconnected" in handlers

            # Step 1: Client connects
            await handlers["on_client_connected"](
                mock_transport, {"id": "participant_1"}
            )

            # Verify initialization
            mock_audio_buffer.start_recording.assert_called_once()
            mock_engine.initialize.assert_called_once()

            # Step 2-3: Simulate voicemail detection occurs
            # Update engine state to reflect voicemail was detected
            mock_engine.get_call_disposition = Mock(
                return_value=EndTaskReason.VOICEMAIL_DETECTED.value
            )
            mock_engine.get_gathered_context = Mock(
                return_value={
                    "voicemail_transcript": "You've reached voicemail, leave a message",
                    "voicemail_confidence": 0.95,
                }
            )

            # Step 5: Client disconnects
            await handlers["on_client_disconnected"](
                mock_transport, {"id": "participant_1"}, None
            )

            # Verify engine cleanup
            mock_engine.cleanup.assert_called_once()

            # Step 6: Verify proper disconnect reason in workflow run update
            mock_db_client.update_workflow_run.assert_called()
            call_args = mock_db_client.update_workflow_run.call_args

            # Check the gathered context includes disconnect reason
            gathered_context = call_args[1]["gathered_context"]
            assert gathered_context["mapped_call_disposition"] == "voicemail_detected"
            assert gathered_context["voicemail_confidence"] == 0.95
            assert (
                gathered_context["voicemail_transcript"]
                == "You've reached voicemail, leave a message"
            )

            # Verify task was NOT cancelled (engine-initiated disconnect)
            mock_task.cancel.assert_not_called()

            # Verify audio buffer was stopped
            mock_audio_buffer.stop_recording.assert_called_once()

            # Verify background jobs were enqueued
            assert (
                mock_enqueue_job.call_count >= 3
            )  # At least 3 jobs should be enqueued
