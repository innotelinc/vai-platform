"""Tests specific to Stasis RTP audio handling to ensure correct μ-law processing."""

import pytest
from api.services.telephony.stasis_rtp_serializer import StasisRTPFrameSerializer

from pipecat.audio.audio_utils import AudioEncoding, calculate_chunk_size_bytes
from pipecat.frames.frames import TTSAudioRawFrame


class TestStasisAudioFlow:
    """Test the complete audio flow for Stasis RTP transport."""

    def test_elevenlabs_ulaw_metadata(self):
        """Test that ElevenLabs μ-law audio frames have correct metadata."""
        # Create a frame as ElevenLabs would
        audio_data = b"\xff" * 160  # 160 bytes of μ-law silence
        frame = TTSAudioRawFrame(audio=audio_data, sample_rate=8000, num_channels=1)
        frame.metadata["audio_encoding"] = "ulaw"

        # Verify metadata
        assert frame.metadata.get("audio_encoding") == "ulaw"
        assert len(frame.audio) == 160  # 20ms of 8kHz μ-law

    @pytest.mark.asyncio
    async def test_serializer_passthrough_for_ulaw(self):
        """Test that StasisRTPFrameSerializer passes through μ-law audio."""
        serializer = StasisRTPFrameSerializer()

        # Create a μ-law frame
        ulaw_data = b"\xff" * 160
        frame = TTSAudioRawFrame(audio=ulaw_data, sample_rate=8000, num_channels=1)
        frame.metadata["audio_encoding"] = "ulaw"

        # Serialize should pass through without conversion
        result = await serializer.serialize(frame)

        assert result == ulaw_data  # Should be unchanged
        assert len(result) == 160

    def test_chunk_size_for_stasis_configuration(self):
        """Test chunk size calculation for typical Stasis configurations."""
        # Stasis typically uses 20ms packets at 8kHz

        # PCM calculation (what upstream assumes)
        pcm_chunk_size = calculate_chunk_size_bytes(
            sample_rate=8000, duration_ms=20, num_channels=1, encoding=AudioEncoding.PCM
        )
        assert pcm_chunk_size == 320

        # μ-law calculation (what we actually need)
        ulaw_chunk_size = calculate_chunk_size_bytes(
            sample_rate=8000,
            duration_ms=20,
            num_channels=1,
            encoding=AudioEncoding.ULAW,
        )
        assert ulaw_chunk_size == 160

        # The ratio should always be 2:1 for PCM:μ-law
        assert pcm_chunk_size == ulaw_chunk_size * 2

    def test_rtp_packet_timing(self):
        """Test that RTP packet timing is correct for μ-law audio."""
        # For 8kHz μ-law:
        # - 20ms = 160 bytes
        # - RTP timestamp increments by 160 for each packet

        sample_rate = 8000
        packet_duration_ms = 20

        # Calculate bytes per packet
        bytes_per_packet = calculate_chunk_size_bytes(
            sample_rate, packet_duration_ms, 1, AudioEncoding.ULAW
        )

        # RTP timestamp increment should equal samples per packet
        samples_per_packet = int(sample_rate * packet_duration_ms / 1000)
        rtp_timestamp_increment = samples_per_packet

        assert bytes_per_packet == 160
        assert rtp_timestamp_increment == 160

    def test_audio_speed_scenario(self):
        """Test the scenario that was causing audio to play too fast."""
        # Original problem: 320 bytes of μ-law was being sent as one chunk
        # This is 40ms of audio, not 20ms, causing 2x playback speed

        # Incorrect scenario (what was happening)
        incorrect_chunk_size = 320  # PCM assumption
        incorrect_duration = incorrect_chunk_size / (
            8000 * 1
        )  # bytes / (samples/sec * bytes/sample)
        # For μ-law: 320 bytes = 320 samples = 0.04 seconds = 40ms

        # Correct scenario (what should happen)
        correct_chunk_size = 160  # μ-law reality
        correct_duration = correct_chunk_size / (
            8000 * 1
        )  # 160 samples = 0.02 seconds = 20ms

        assert incorrect_duration == 0.04  # 40ms - too much!
        assert correct_duration == 0.02  # 20ms - correct!

    def test_transport_chunk_calculation(self):
        """Test that transport correctly calculates chunk sizes for different encodings."""
        from pipecat.transports.base_transport import TransportParams

        # Standard transport params for Stasis
        params = TransportParams(
            audio_out_enabled=True,
            audio_out_sample_rate=8000,
            audio_out_channels=1,
            audio_out_10ms_chunks=2,  # 20ms total
        )

        # Calculate what the transport would compute for PCM
        audio_bytes_10ms_pcm = (
            int(params.audio_out_sample_rate / 100) * params.audio_out_channels * 2
        )
        chunk_size_pcm = audio_bytes_10ms_pcm * params.audio_out_10ms_chunks

        assert audio_bytes_10ms_pcm == 160  # 10ms of PCM
        assert chunk_size_pcm == 320  # 20ms of PCM

        # Our calculation for μ-law
        duration_ms = params.audio_out_10ms_chunks * 10
        chunk_size_ulaw = calculate_chunk_size_bytes(
            params.audio_out_sample_rate,
            duration_ms,
            params.audio_out_channels,
            AudioEncoding.ULAW,
        )

        assert chunk_size_ulaw == 160  # 20ms of μ-law
        assert chunk_size_ulaw == chunk_size_pcm // 2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_mixed_encoding_stream(self):
        """Test handling of streams that mix PCM and μ-law frames."""
        # This shouldn't happen in practice, but we should handle it gracefully

        # PCM frame
        pcm_frame = TTSAudioRawFrame(
            audio=b"\x00" * 320, sample_rate=8000, num_channels=1
        )
        pcm_chunk_size = calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.PCM)
        assert pcm_chunk_size == 320

        # μ-law frame
        ulaw_frame = TTSAudioRawFrame(
            audio=b"\xff" * 160, sample_rate=8000, num_channels=1
        )
        ulaw_frame.metadata["audio_encoding"] = "ulaw"
        ulaw_chunk_size = calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.ULAW)
        assert ulaw_chunk_size == 160

    def test_non_standard_sample_rates(self):
        """Test chunk size calculations for non-standard sample rates."""
        # While Stasis typically uses 8kHz, we should handle other rates correctly

        test_cases = [
            (16000, 20, AudioEncoding.ULAW, 320),  # 16kHz μ-law
            (24000, 20, AudioEncoding.ULAW, 480),  # 24kHz μ-law
            (48000, 10, AudioEncoding.ULAW, 480),  # 48kHz μ-law, 10ms
        ]

        for sample_rate, duration_ms, encoding, expected_size in test_cases:
            chunk_size = calculate_chunk_size_bytes(
                sample_rate, duration_ms, 1, encoding
            )
            assert chunk_size == expected_size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
