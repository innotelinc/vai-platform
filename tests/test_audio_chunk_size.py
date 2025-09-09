"""Tests for audio chunk size calculations to ensure robustness against upstream changes."""

import pytest

from pipecat.audio.audio_utils import (
    AudioEncoding,
    calculate_audio_bytes_per_sample,
    calculate_chunk_size_bytes,
    calculate_duration_ms,
    get_audio_encoding,
)


class TestAudioEncoding:
    """Test audio encoding detection from metadata."""

    def test_get_audio_encoding_pcm_default(self):
        """Test that PCM is the default encoding."""
        assert get_audio_encoding({}) == AudioEncoding.PCM
        assert get_audio_encoding({"audio_encoding": ""}) == AudioEncoding.PCM
        assert get_audio_encoding({"audio_encoding": "unknown"}) == AudioEncoding.PCM

    def test_get_audio_encoding_ulaw(self):
        """Test μ-law encoding detection."""
        assert get_audio_encoding({"audio_encoding": "ulaw"}) == AudioEncoding.ULAW
        assert get_audio_encoding({"audio_encoding": "ULAW"}) == AudioEncoding.ULAW
        assert get_audio_encoding({"audio_encoding": "Ulaw"}) == AudioEncoding.ULAW

    def test_get_audio_encoding_alaw(self):
        """Test A-law encoding detection."""
        assert get_audio_encoding({"audio_encoding": "alaw"}) == AudioEncoding.ALAW
        assert get_audio_encoding({"audio_encoding": "ALAW"}) == AudioEncoding.ALAW


class TestAudioBytesPerSample:
    """Test bytes per sample calculation for different encodings."""

    def test_pcm_bytes_per_sample(self):
        """Test PCM uses 2 bytes per sample."""
        assert calculate_audio_bytes_per_sample(AudioEncoding.PCM) == 2

    def test_ulaw_bytes_per_sample(self):
        """Test μ-law uses 1 byte per sample."""
        assert calculate_audio_bytes_per_sample(AudioEncoding.ULAW) == 1

    def test_alaw_bytes_per_sample(self):
        """Test A-law uses 1 byte per sample."""
        assert calculate_audio_bytes_per_sample(AudioEncoding.ALAW) == 1


class TestChunkSizeCalculation:
    """Test chunk size calculations for various configurations."""

    def test_pcm_8khz_20ms_mono(self):
        """Test PCM 8kHz 20ms mono chunk size."""
        chunk_size = calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.PCM)
        assert chunk_size == 320  # 8000/1000 * 20 * 1 * 2

    def test_ulaw_8khz_20ms_mono(self):
        """Test μ-law 8kHz 20ms mono chunk size."""
        chunk_size = calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.ULAW)
        assert chunk_size == 160  # 8000/1000 * 20 * 1 * 1

    def test_pcm_16khz_10ms_mono(self):
        """Test PCM 16kHz 10ms mono chunk size."""
        chunk_size = calculate_chunk_size_bytes(16000, 10, 1, AudioEncoding.PCM)
        assert chunk_size == 320  # 16000/1000 * 10 * 1 * 2

    def test_pcm_44100hz_10ms_stereo(self):
        """Test PCM 44.1kHz 10ms stereo chunk size."""
        chunk_size = calculate_chunk_size_bytes(44100, 10, 2, AudioEncoding.PCM)
        assert chunk_size == 1764  # 44100/1000 * 10 * 2 * 2

    def test_different_durations(self):
        """Test various durations for consistency."""
        # 10ms chunks
        assert calculate_chunk_size_bytes(8000, 10, 1, AudioEncoding.PCM) == 160
        assert calculate_chunk_size_bytes(8000, 10, 1, AudioEncoding.ULAW) == 80

        # 20ms chunks
        assert calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.PCM) == 320
        assert calculate_chunk_size_bytes(8000, 20, 1, AudioEncoding.ULAW) == 160

        # 40ms chunks
        assert calculate_chunk_size_bytes(8000, 40, 1, AudioEncoding.PCM) == 640
        assert calculate_chunk_size_bytes(8000, 40, 1, AudioEncoding.ULAW) == 320


class TestDurationCalculation:
    """Test duration calculation from byte count."""

    def test_pcm_duration_calculation(self):
        """Test duration calculation for PCM audio."""
        # 320 bytes of 8kHz mono PCM should be 20ms
        duration = calculate_duration_ms(320, 8000, 1, AudioEncoding.PCM)
        assert duration == 20.0

        # 160 bytes of 8kHz mono PCM should be 10ms
        duration = calculate_duration_ms(160, 8000, 1, AudioEncoding.PCM)
        assert duration == 10.0

    def test_ulaw_duration_calculation(self):
        """Test duration calculation for μ-law audio."""
        # 160 bytes of 8kHz mono μ-law should be 20ms
        duration = calculate_duration_ms(160, 8000, 1, AudioEncoding.ULAW)
        assert duration == 20.0

        # 80 bytes of 8kHz mono μ-law should be 10ms
        duration = calculate_duration_ms(80, 8000, 1, AudioEncoding.ULAW)
        assert duration == 10.0

    def test_round_trip_consistency(self):
        """Test that chunk size and duration calculations are consistent."""
        test_cases = [
            (8000, 20, 1, AudioEncoding.PCM),
            (8000, 20, 1, AudioEncoding.ULAW),
            (16000, 10, 1, AudioEncoding.PCM),
            (44100, 10, 2, AudioEncoding.PCM),
        ]

        for sample_rate, duration_ms, channels, encoding in test_cases:
            chunk_size = calculate_chunk_size_bytes(
                sample_rate, duration_ms, channels, encoding
            )
            calculated_duration = calculate_duration_ms(
                chunk_size, sample_rate, channels, encoding
            )
            assert abs(calculated_duration - duration_ms) < 0.1, (
                f"Round trip failed for {sample_rate}Hz {duration_ms}ms {channels}ch {encoding}: "
                f"expected {duration_ms}ms, got {calculated_duration}ms"
            )


class TestRobustnessAgainstUpstreamChanges:
    """Test scenarios that ensure our code is robust against upstream changes."""

    def test_chunk_size_independence(self):
        """Test that our calculations don't depend on upstream PCM assumptions."""
        # Simulate what upstream calculates for PCM
        upstream_sample_rate = 8000
        upstream_channels = 1
        upstream_10ms_chunks = 2  # 20ms total

        # Upstream calculation (assumes PCM with 2 bytes per sample)
        upstream_audio_bytes_10ms = (
            int(upstream_sample_rate / 100) * upstream_channels * 2
        )
        upstream_chunk_size = upstream_audio_bytes_10ms * upstream_10ms_chunks

        # Our calculation for PCM should match upstream
        our_pcm_chunk_size = calculate_chunk_size_bytes(
            upstream_sample_rate,
            upstream_10ms_chunks * 10,
            upstream_channels,
            AudioEncoding.PCM,
        )
        assert our_pcm_chunk_size == upstream_chunk_size

        # Our calculation for μ-law should be different
        our_ulaw_chunk_size = calculate_chunk_size_bytes(
            upstream_sample_rate,
            upstream_10ms_chunks * 10,
            upstream_channels,
            AudioEncoding.ULAW,
        )
        assert our_ulaw_chunk_size == upstream_chunk_size // 2

    def test_various_upstream_configurations(self):
        """Test that our calculations work correctly for various upstream configs."""
        configurations = [
            # (sample_rate, channels, 10ms_chunks)
            (8000, 1, 1),  # 10ms chunks
            (8000, 1, 2),  # 20ms chunks
            (8000, 1, 4),  # 40ms chunks
            (16000, 1, 2),  # 16kHz, 20ms
            (24000, 1, 2),  # 24kHz, 20ms
            (44100, 2, 1),  # 44.1kHz stereo, 10ms
        ]

        for sample_rate, channels, chunks_10ms in configurations:
            # Simulate upstream PCM calculation
            upstream_bytes_10ms = int(sample_rate / 100) * channels * 2
            upstream_chunk_size = upstream_bytes_10ms * chunks_10ms

            # Our calculations
            duration_ms = chunks_10ms * 10

            # PCM should match upstream
            pcm_size = calculate_chunk_size_bytes(
                sample_rate, duration_ms, channels, AudioEncoding.PCM
            )
            assert pcm_size == upstream_chunk_size, (
                f"PCM mismatch for {sample_rate}Hz {channels}ch {duration_ms}ms: "
                f"expected {upstream_chunk_size}, got {pcm_size}"
            )

            # μ-law should be half of PCM
            ulaw_size = calculate_chunk_size_bytes(
                sample_rate, duration_ms, channels, AudioEncoding.ULAW
            )
            assert ulaw_size == upstream_chunk_size // 2, (
                f"μ-law mismatch for {sample_rate}Hz {channels}ch {duration_ms}ms: "
                f"expected {upstream_chunk_size // 2}, got {ulaw_size}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
