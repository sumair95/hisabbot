"""
Audio preprocessing for Whisper STT — Phases 1+2 of the STT package.

Every inbound voice note runs through:

  1. ffmpeg pipeline (single subprocess call):
       highpass=f=80          cut low rumble (fans, traffic, AC hum)
       afftdn=nf=-25          FFT denoiser, suppresses stationary noise
       loudnorm=I=-16:TP=-1.5  normalize loudness so quiet voices carry
       silenceremove=...       trim leading/trailing dead air
     Output: 16kHz mono PCM s16le (Whisper's expected input)

  2. Voice Activity Detection (webrtcvad):
       Frame the cleaned PCM into 30ms windows; compute speech_ratio
       (fraction of frames classified as speech). If too low, raise
       VoiceUnusable so the webhook can reply "voice samajh nahi aayi"
       without paying for a Whisper API call.

The processed PCM is returned as an in-memory WAV with header so
Whisper accepts it directly without re-encoding.
"""
from __future__ import annotations
import asyncio
import io
import wave
from dataclasses import dataclass

import webrtcvad

from ..utils.logging import get_logger

log = get_logger("audio_preprocess")


# Sample rate Whisper expects and webrtcvad supports.
SAMPLE_RATE = 16000

# webrtcvad accepts frames of exactly 10/20/30 ms.
# 30ms @ 16kHz = 480 samples × 2 bytes (s16le) = 960 bytes.
VAD_FRAME_MS = 30
VAD_FRAME_BYTES = SAMPLE_RATE * VAD_FRAME_MS // 1000 * 2

# webrtcvad mode 0..3 — 3 is most aggressive at filtering noise.
# Mode 2 is a deliberate balance: reduces false-positive (noise -> speech)
# while staying tolerant of quiet speech.
VAD_AGGRESSIVENESS = 2

# Minimum fraction of frames classified as speech to consider audio usable.
# Real voice notes in QUIET environments land at 0.4–0.9; in a crowded
# kirana shop the surrounding chatter pushes the apparent speech ratio of
# the shopkeeper's own voice down to ~0.10–0.15 because the noise frames
# get classified as speech too. 0.08 is the empirical floor that still
# excludes pure silence and pocket-recordings without rejecting real
# (noisy) voice notes. Pure noise with mode 2 typically lands below 0.05.
MIN_SPEECH_RATIO = 0.08

# Anything shorter than this after preprocessing is almost certainly an
# accidental tap — reject without a Whisper call.
MIN_DURATION_SEC = 0.3

# Cap on preprocessing wall time. Railway request budget is generous but
# we want a deterministic ceiling so a malformed file can't hang us.
FFMPEG_TIMEOUT_SEC = 15


class VoiceUnusable(Exception):
    """Raised when the audio cannot be reasonably transcribed."""

    def __init__(self, reason: str, *, speech_ratio: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.speech_ratio = speech_ratio


@dataclass
class PreprocessResult:
    wav_bytes: bytes        # 16kHz mono WAV with header — feed to Whisper as-is
    duration_sec: float
    speech_ratio: float


# Filter graph applied in a single ffmpeg pass. Order is intentional:
#   1. highpass before denoiser (denoiser is more effective once rumble is gone)
#   2. denoiser before loudnorm (so we don't amplify residual noise)
#   3. loudnorm before silenceremove (so threshold has a stable reference)
#   4. silenceremove last
# afftdn noise floor is intentionally -20 (not -25). -25 is more aggressive
# at scrubbing stationary noise, but in crowded shops it also eats real
# speech consonants — Whisper recovers from residual noise better than from
# missing phonemes. -20 leaves more speech detail intact.
_FFMPEG_FILTERGRAPH = (
    "highpass=f=80,"
    "afftdn=nf=-20,"
    "loudnorm=I=-16:TP=-1.5:LRA=11,"
    "silenceremove="
        "start_periods=1:start_threshold=-50dB:start_silence=0.5:"
        "stop_periods=1:stop_threshold=-50dB:stop_silence=0.5:"
        "detection=peak"
)


async def preprocess_audio(audio_bytes: bytes) -> PreprocessResult:
    """
    Clean up an inbound voice note and decide whether it contains real speech.
    Returns a PreprocessResult with WAV bytes ready for Whisper.

    Raises VoiceUnusable if the audio is silent, mostly noise, too short,
    or fails to decode.
    """
    if not audio_bytes:
        raise VoiceUnusable("empty_audio")

    pcm = await _run_ffmpeg(audio_bytes)
    if not pcm:
        raise VoiceUnusable("ffmpeg_empty_output")

    # 2 bytes per sample (s16le) at SAMPLE_RATE Hz mono
    duration_sec = len(pcm) / 2 / SAMPLE_RATE
    if duration_sec < MIN_DURATION_SEC:
        log.info("audio_preprocess.too_short", duration_sec=round(duration_sec, 2))
        raise VoiceUnusable("too_short", speech_ratio=0.0)

    speech_ratio = _vad_speech_ratio(pcm)
    if speech_ratio < MIN_SPEECH_RATIO:
        log.info(
            "audio_preprocess.no_speech",
            speech_ratio=round(speech_ratio, 3),
            duration_sec=round(duration_sec, 2),
        )
        raise VoiceUnusable("no_speech_detected", speech_ratio=speech_ratio)

    wav_bytes = _wrap_pcm_as_wav(pcm)
    log.info(
        "audio_preprocess.ok",
        duration_sec=round(duration_sec, 2),
        speech_ratio=round(speech_ratio, 3),
        bytes_in=len(audio_bytes),
        bytes_out=len(wav_bytes),
    )
    return PreprocessResult(
        wav_bytes=wav_bytes,
        duration_sec=duration_sec,
        speech_ratio=speech_ratio,
    )


async def _run_ffmpeg(audio_bytes: bytes) -> bytes:
    """Run ffmpeg, pipe audio through stdin -> 16kHz mono PCM s16le on stdout."""
    args = [
        "ffmpeg",
        "-loglevel", "error",
        "-nostdin",
        "-i", "pipe:0",
        "-af", _FFMPEG_FILTERGRAPH,
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
        "pipe:1",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as e:
        # ffmpeg binary missing in the image — log loudly so it's diagnosable
        log.error("audio_preprocess.ffmpeg_missing", error=str(e))
        raise VoiceUnusable("ffmpeg_not_installed")

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=audio_bytes),
            timeout=FFMPEG_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:  # noqa: BLE001
            pass
        log.error("audio_preprocess.ffmpeg_timeout", bytes_in=len(audio_bytes))
        raise VoiceUnusable("ffmpeg_timeout")

    if proc.returncode != 0:
        err = (stderr or b"").decode("utf-8", errors="replace")[:300]
        log.error("audio_preprocess.ffmpeg_failed", code=proc.returncode, err=err)
        raise VoiceUnusable(f"ffmpeg_failed_rc_{proc.returncode}")

    return stdout or b""


def _vad_speech_ratio(pcm: bytes) -> float:
    """Fraction of fixed-size frames in PCM classified as speech by webrtcvad."""
    if len(pcm) < VAD_FRAME_BYTES:
        return 0.0
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    speech_frames = 0
    total_frames = 0
    # Iterate over WHOLE frames only; partial trailing frame is dropped.
    end = len(pcm) - VAD_FRAME_BYTES + 1
    for offset in range(0, end, VAD_FRAME_BYTES):
        frame = pcm[offset:offset + VAD_FRAME_BYTES]
        try:
            if vad.is_speech(frame, SAMPLE_RATE):
                speech_frames += 1
        except Exception:  # noqa: BLE001
            # webrtcvad raises on weird frames; ignore them — they don't count
            pass
        total_frames += 1
    if total_frames == 0:
        return 0.0
    return speech_frames / total_frames


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Build an in-memory 16-bit mono WAV with header — Whisper accepts WAV."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
