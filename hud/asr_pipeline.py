"""
ASR Pipeline — Whisper-based speech transcription with pre-warming.

Varshitha's module. Key features:
- Pre-warmed model on init (avoids 5–10s cold start on first voice command)
- Bandpass filter (300–3400 Hz) + noise gate + RMS normalisation
- No hardcoded language — Whisper detects English/Hindi/Hinglish automatically
- initial_prompt primes Whisper for Indian-accented English and PHANTOM context
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

_INITIAL_PROMPT = (
    "PHANTOM AI assistant for local system management. "
    "User is giving a command in English or Hinglish."
)


class ASRPipeline:
    """
    Whisper ASR pipeline with pre-warming and Indian accent robustness.
    """

    def __init__(self, model_size: str = "tiny"):
        self._model_size = model_size
        self._model = None
        self._load_model()  # Pre-warm on init — not on first use

    def _load_model(self) -> None:
        """Load Whisper model and warm it up with silence to trigger JIT."""
        try:
            import whisper

            logger.info(f"Loading Whisper {self._model_size} model...")
            self._model = whisper.load_model(self._model_size)

            # Warm up with 1 second of silence
            silence = np.zeros(16000, dtype=np.float32)
            self._model.transcribe(silence, language=None, fp16=False)
            logger.info(f"Whisper {self._model_size} ready.")

        except ImportError:
            logger.error("openai-whisper not installed. Run: pip install openai-whisper")
        except Exception as e:
            logger.error(f"Whisper load failed: {e}")

    def transcribe(self, audio_array: np.ndarray) -> dict:
        """
        Transcribe audio. Language is auto-detected (no hardcoding).

        Returns:
            {
                "text": str,
                "language": str,          # e.g. "en", "hi"
                "language_confidence": float,
                "segments": list
            }
        """
        if self._model is None:
            return {"text": "", "language": "en", "language_confidence": 0.0, "segments": []}

        processed = self.preprocess_audio(audio_array)
        result = self._model.transcribe(
            processed,
            fp16=False,
            initial_prompt=_INITIAL_PROMPT,
            # No language= param — let Whisper detect it
        )
        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", "en"),
            "language_confidence": result.get("language_probability", 1.0),
            "segments": result.get("segments", []),
        }

    def preprocess_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
    ) -> np.ndarray:
        """
        Apply Indian accent robustness pre-processing pipeline:
        1. Bandpass filter: 300–3400 Hz (voice frequency range)
        2. Noise gate: suppress frames below -40 dB
        3. Amplitude normalisation: RMS to -20 dBFS
        """
        audio = audio_data.astype(np.float32)

        # 1. Bandpass filter (300–3400 Hz)
        try:
            from scipy.signal import butter, sosfilt

            nyq = sample_rate / 2.0
            sos = butter(4, [300 / nyq, 3400 / nyq], btype="band", output="sos")
            audio = sosfilt(sos, audio).astype(np.float32)
        except ImportError:
            pass  # scipy not available — skip filter

        # 2. Noise gate: zero out frames below -40 dBFS
        threshold_linear = 10 ** (-40 / 20)  # -40 dBFS in linear amplitude
        frame_size = int(sample_rate * 0.025)  # 25ms frames
        for i in range(0, len(audio) - frame_size, frame_size):
            frame = audio[i : i + frame_size]
            rms = np.sqrt(np.mean(frame ** 2))
            if rms < threshold_linear:
                audio[i : i + frame_size] = 0.0

        # 3. RMS normalisation to -20 dBFS
        rms = np.sqrt(np.mean(audio ** 2))
        target_rms = 10 ** (-20 / 20)  # -20 dBFS
        if rms > 1e-8:
            audio = audio * (target_rms / rms)

        return np.clip(audio, -1.0, 1.0)
