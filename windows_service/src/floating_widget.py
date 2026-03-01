"""
Floating widget for the OpenClaw Windows client.

Provides an always-on-top, semi-transparent, draggable control panel with:
  - A status indicator (Idle / Listening / Connected)
  - [Start Listening]  button  — activates microphone input
  - [Stop Listening]   button  — deactivates microphone input
  - [×] close button           — minimises to system tray (does not quit service)

The widget is built with Tkinter (Python standard library) to keep the
dependency footprint as small as possible.
"""

import logging
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# ── Colour palette ────────────────────────────────────────────────────────────
_BG = "#1e1e2e"          # dark background
_FG = "#cdd6f4"          # light foreground
_ACCENT = "#89b4fa"      # blue accent
_DANGER = "#f38ba8"      # red / stop
_SUCCESS = "#a6e3a1"     # green / active
_MUTED = "#585b70"       # muted / disabled


class FloatingWidget:
    """
    A small always-on-top Tkinter window that floats over all other windows.

    Parameters
    ----------
    on_start_listening:
        Called when the user presses *Start Listening*.
    on_stop_listening:
        Called when the user presses *Stop Listening*.
    on_close:
        Called when the user presses the × button.
        Defaults to hiding the widget (not destroying it).
    initial_x / initial_y:
        Initial screen position.
    opacity:
        Window opacity 0.0–1.0.
    """

    def __init__(
        self,
        on_start_listening: Optional[Callable[[], None]] = None,
        on_stop_listening: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None,
        initial_x: int = 50,
        initial_y: int = 50,
        opacity: float = 0.85,
    ) -> None:
        self._on_start_listening = on_start_listening
        self._on_stop_listening = on_stop_listening
        self._on_close = on_close
        self._initial_x = initial_x
        self._initial_y = initial_y
        self._opacity = max(0.1, min(1.0, opacity))

        self._root: Optional[tk.Tk] = None
        self._status_var: Optional[tk.StringVar] = None
        self._thread: Optional[threading.Thread] = None
        self._drag_x = 0
        self._drag_y = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the widget in a dedicated daemon thread."""
        self._thread = threading.Thread(
            target=self._build_and_run, daemon=True, name="FloatingWidgetThread"
        )
        self._thread.start()

    def stop(self) -> None:
        """Destroy the widget window."""
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:  # noqa: BLE001
                pass

    def set_status(self, status: str, listening: bool = False, connected: bool = False) -> None:
        """
        Thread-safe method to update the status label.

        Parameters
        ----------
        status:
            Human-readable status text.
        listening:
            When True the indicator is highlighted green.
        connected:
            When True the indicator uses the accent colour.
        """
        if self._root and self._status_var:
            colour = _SUCCESS if listening else (_ACCENT if connected else _MUTED)
            self._root.after(
                0,
                lambda: self._apply_status(status, colour),
            )

    def update_position(self, x: int, y: int) -> None:
        """Move the widget to absolute screen coordinates."""
        if self._root:
            self._root.after(0, lambda: self._root.geometry(f"+{x}+{y}"))

    # ------------------------------------------------------------------
    # Internal – widget construction
    # ------------------------------------------------------------------

    def _build_and_run(self) -> None:
        try:
            self._root = tk.Tk()
            self._root.title("OpenClaw")
            self._root.geometry(f"220x140+{self._initial_x}+{self._initial_y}")
            self._root.resizable(False, False)
            self._root.overrideredirect(True)   # borderless
            self._root.wm_attributes("-topmost", True)
            self._root.wm_attributes("-alpha", self._opacity)
            self._root.configure(bg=_BG)

            self._build_ui()
            self._root.mainloop()
        except Exception as exc:  # noqa: BLE001
            logger.error("FloatingWidget error: %s", exc)

    def _build_ui(self) -> None:
        root = self._root

        # ── title bar (draggable) ──────────────────────────────────────
        title_bar = tk.Frame(root, bg=_BG, cursor="fleur")
        title_bar.pack(fill=tk.X, pady=(4, 0))

        title_lbl = tk.Label(
            title_bar,
            text="🐾 OpenClaw",
            bg=_BG,
            fg=_ACCENT,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        title_lbl.pack(side=tk.LEFT, padx=8)

        close_btn = tk.Button(
            title_bar,
            text="×",
            bg=_BG,
            fg=_MUTED,
            activebackground=_DANGER,
            activeforeground="#ffffff",
            relief=tk.FLAT,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
            command=self._handle_close,
            bd=0,
        )
        close_btn.pack(side=tk.RIGHT, padx=4)

        # Enable drag on both the title bar and its label
        for widget in (title_bar, title_lbl):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_motion)

        # ── status label ─────────────────────────────────────────────
        self._status_var = tk.StringVar(value="● Idle")
        status_lbl = tk.Label(
            root,
            textvariable=self._status_var,
            bg=_BG,
            fg=_MUTED,
            font=("Segoe UI", 8),
            anchor="w",
        )
        status_lbl.pack(fill=tk.X, padx=10, pady=(2, 0))
        self._status_label = status_lbl

        # ── button row ───────────────────────────────────────────────
        btn_frame = tk.Frame(root, bg=_BG)
        btn_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        start_btn = tk.Button(
            btn_frame,
            text="▶  Start Listening",
            bg=_ACCENT,
            fg="#1e1e2e",
            activebackground=_SUCCESS,
            activeforeground="#1e1e2e",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=self._handle_start,
            bd=0,
            padx=6,
            pady=4,
        )
        start_btn.pack(fill=tk.X, pady=(0, 4))

        stop_btn = tk.Button(
            btn_frame,
            text="■  Stop Listening",
            bg=_MUTED,
            fg=_FG,
            activebackground=_DANGER,
            activeforeground="#1e1e2e",
            relief=tk.FLAT,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
            command=self._handle_stop,
            bd=0,
            padx=6,
            pady=4,
        )
        stop_btn.pack(fill=tk.X)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _handle_start(self) -> None:
        logger.debug("Start Listening pressed")
        if self._on_start_listening:
            threading.Thread(target=self._on_start_listening, daemon=True).start()

    def _handle_stop(self) -> None:
        logger.debug("Stop Listening pressed")
        if self._on_stop_listening:
            threading.Thread(target=self._on_stop_listening, daemon=True).start()

    def _handle_close(self) -> None:
        logger.debug("Close pressed")
        if self._on_close:
            self._on_close()
        else:
            self._root.withdraw()

    def _apply_status(self, text: str, colour: str) -> None:
        if self._status_var:
            self._status_var.set(f"● {text}")
        if hasattr(self, "_status_label"):
            self._status_label.configure(fg=colour)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._root.winfo_x()
        self._drag_y = event.y_root - self._root.winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        new_x = event.x_root - self._drag_x
        new_y = event.y_root - self._drag_y
        self._root.geometry(f"+{new_x}+{new_y}")
