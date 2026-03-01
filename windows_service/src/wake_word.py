"""
Wake word and speech recognition module.

Listens on the default microphone for a configurable wake word phrase.
Once triggered, captures speech until a stop phrase is detected or
the caller explicitly halts recognition.

Requires the ``SpeechRecognition`` package (``pip install SpeechRecognition``).
On Windows the built-in ``speech_recognition`` backend can use CMU Sphinx
offline or the free Google Web Speech API.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import speech_recognition as sr
    _SR_AVAILABLE = True
except ImportError:
    _SR_AVAILABLE = False
    logger.warning(
        "SpeechRecognition package not installed. "
        "Install it with: pip install SpeechRecognition"
    )


class WakeWordDetector:
    """
    Background thread that waits for a configurable wake word.

    Parameters
    ----------
    wake_word:
        Phrase that triggers active listening (case-insensitive).
    stop_phrase:
        Phrase that deactivates listening (case-insensitive).
    on_wake:
        Callback invoked when the wake word is detected.
    on_speech:
        Callback invoked with each recognised utterance while active.
    on_stop:
        Callback invoked when the stop phrase is detected or
        :meth:`stop_listening` is called.
    speech_timeout:
        Seconds to wait for speech before giving up on a phrase.
    phrase_timeout:
        Maximum seconds allowed for a single phrase.
    """

    def __init__(
        self,
        wake_word: str = "hey claw",
        stop_phrase: str = "stop listening",
        on_wake: Optional[Callable[[], None]] = None,
        on_speech: Optional[Callable[[str], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        speech_timeout: float = 5.0,
        phrase_timeout: float = 10.0,
    ) -> None:
        self._wake_word = wake_word.lower().strip()
        self._stop_phrase = stop_phrase.lower().strip()
        self._on_wake = on_wake
        self._on_speech = on_speech
        self._on_stop = on_stop
        self._speech_timeout = speech_timeout
        self._phrase_timeout = phrase_timeout

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._active_listening = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_active(self) -> bool:
        """True when actively processing speech (after wake word)."""
        return self._active_listening

    def start(self) -> None:
        """Start the wake-word detection loop in a daemon thread."""
        if not _SR_AVAILABLE:
            logger.error("Cannot start WakeWordDetector: SpeechRecognition not installed.")
            return
        if self._running:
            return
        self._running = True
        self._active_listening = False
        self._thread = threading.Thread(
            target=self._detection_loop, daemon=True, name="WakeWordThread"
        )
        self._thread.start()
        logger.info("Wake word detector started (wake=%r, stop=%r)", self._wake_word, self._stop_phrase)

    def stop(self) -> None:
        """Stop the detection loop."""
        self._running = False
        self._active_listening = False
        logger.info("Wake word detector stopped.")

    def activate_listening(self) -> None:
        """Manually activate active listening (as if the wake word was spoken)."""
        with self._lock:
            if not self._active_listening:
                self._active_listening = True
                logger.info("Listening activated manually.")
                if self._on_wake:
                    try:
                        self._on_wake()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("on_wake callback error: %s", exc)

    def stop_listening(self) -> None:
        """Manually deactivate active listening."""
        with self._lock:
            if self._active_listening:
                self._active_listening = False
                logger.info("Listening deactivated manually.")
                if self._on_stop:
                    try:
                        self._on_stop()
                    except Exception as exc:  # noqa: BLE001
                        logger.error("on_stop callback error: %s", exc)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _detection_loop(self) -> None:
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True

        while self._running:
            try:
                with sr.Microphone() as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    while self._running:
                        try:
                            audio = recognizer.listen(
                                source,
                                timeout=self._speech_timeout,
                                phrase_time_limit=self._phrase_timeout,
                            )
                        except sr.WaitTimeoutError:
                            continue

                        try:
                            text = recognizer.recognize_google(audio).lower().strip()
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as exc:
                            logger.warning("Speech recognition request error: %s", exc)
                            continue

                        logger.debug("Heard: %r", text)
                        self._handle_text(text)

            except OSError as exc:
                if self._running:
                    logger.error("Microphone error: %s. Retrying…", exc)
                    time.sleep(2)

    def _handle_text(self, text: str) -> None:
        with self._lock:
            if not self._active_listening:
                if self._wake_word in text:
                    logger.info("Wake word detected: %r", text)
                    self._active_listening = True
                    if self._on_wake:
                        try:
                            self._on_wake()
                        except Exception as exc:  # noqa: BLE001
                            logger.error("on_wake callback error: %s", exc)
            else:
                if self._stop_phrase in text:
                    logger.info("Stop phrase detected: %r", text)
                    self._active_listening = False
                    if self._on_stop:
                        try:
                            self._on_stop()
                        except Exception as exc:  # noqa: BLE001
                            logger.error("on_stop callback error: %s", exc)
                else:
                    if self._on_speech:
                        try:
                            self._on_speech(text)
                        except Exception as exc:  # noqa: BLE001
                            logger.error("on_speech callback error: %s", exc)
