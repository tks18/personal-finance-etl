"""Background task execution runner marshaling callbacks to the main Tkinter thread.

Owns
----
- BackgroundTaskRunner: Bounded thread-pool runner managing asynchronous non-blocking
  computations (system diagnostics, database snapshots, file parsing).
- TaskHandle: Cancellable task handle tracking generation counters and cancellation tokens.
- Safe callback dispatch to the CustomTkinter UI loop via widget.after(0, ...).

Does not own
-------------
- Pipeline worker processes or IPC multiprocessing queues (owned by application.pipeline.worker).
- Tkinter widget layout or styling (owned by presentation.desktop.* tabs).
"""

from __future__ import annotations

import logging
import queue
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]

__all__ = ["BackgroundTaskRunner", "TaskHandle", "get_background_runner"]

logger = logging.getLogger(__name__)


class TaskHandle[T]:
    """Cancellable token and generation handle for an asynchronous background task."""

    def __init__(self, generation: int = 0) -> None:
        self.generation: int = generation
        self._cancelled: bool = False
        self.future: Future[Any] | None = None

    def cancel(self) -> None:
        """Mark task as cancelled so post-execution UI callbacks are dropped."""
        self._cancelled = True
        if self.future is not None and not self.future.done():
            self.future.cancel()

    @property
    def is_cancelled(self) -> bool:
        """Whether this task has been explicitly cancelled."""
        return self._cancelled


class BackgroundTaskRunner:
    """Thread-safe background task runner with main-thread Tkinter callback dispatch."""

    _instance: BackgroundTaskRunner | None = None

    def __init__(self, max_workers: int = 3) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pfetl-bg-task-",
        )
        self._is_shutdown = False
        self._queue: queue.Queue[tuple[Callable[[], None], Any]] = queue.Queue()
        self._polling_widgets: set[int] = set()

    @classmethod
    def get_instance(cls) -> BackgroundTaskRunner:
        """Obtain the global singleton BackgroundTaskRunner instance."""
        if cls._instance is None or cls._instance._is_shutdown:
            cls._instance = cls()
        return cls._instance

    def _ensure_polling(self, widget: Any) -> None:
        """Ensure the parent widget event loop polls the callback queue."""
        widget_id = id(widget)
        if widget_id in self._polling_widgets:
            return
        self._polling_widgets.add(widget_id)

        def _poll() -> None:
            self.drain()
            try:
                if hasattr(widget, "winfo_exists") and widget.winfo_exists():
                    widget.after(16, _poll)
                    return
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            self._polling_widgets.discard(widget_id)

        try:
            widget.after(16, _poll)
        except Exception:  # pylint: disable=broad-exception-caught
            self._polling_widgets.discard(widget_id)

    def drain(self) -> None:
        """Process all queued completion callbacks safely in the current thread."""
        while True:
            try:
                callback, widget = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                if widget is None or (hasattr(widget, "winfo_exists") and widget.winfo_exists()):
                    callback()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.error("Error executing background task callback: %s", exc)

    def run[T](
        self,
        target_callable: Callable[[], T],
        *,
        on_success: Callable[[T], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_finally: Callable[[], None] | None = None,
        parent_widget: ctk.CTk | ctk.CTkFrame | None = None,
        generation: int = 0,
    ) -> TaskHandle[T]:
        """Submit a callable to the background pool, marshaling callbacks to parent_widget."""
        handle: TaskHandle[T] = TaskHandle(generation=generation)

        if parent_widget is not None and hasattr(parent_widget, "winfo_exists"):
            try:
                if parent_widget.winfo_exists():
                    self._ensure_polling(parent_widget)
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        def _worker() -> None:
            result: T | None = None
            err: Exception | None = None
            try:
                result = target_callable()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                err = exc
                logger.debug("Background task raised exception: %s", exc, exc_info=True)

            def _dispatch_callbacks() -> None:
                if handle.is_cancelled:
                    return
                try:
                    if err is not None:
                        if on_error is not None:
                            on_error(err)
                    else:
                        if on_success is not None and result is not None:
                            on_success(result)
                except Exception as cb_err:  # pylint: disable=broad-exception-caught
                    logger.error("Error in background task completion callback: %s", cb_err)
                finally:
                    if on_finally is not None and not handle.is_cancelled:
                        try:
                            on_finally()
                        except Exception as fin_err:  # pylint: disable=broad-exception-caught
                            logger.error("Error in background task finalizer: %s", fin_err)

            self._queue.put((_dispatch_callbacks, parent_widget))
            if parent_widget is None:
                self.drain()

        if not self._is_shutdown:
            future = self._executor.submit(_worker)
            handle.future = future

        return handle

    def _marshal_to_ui(
        self,
        parent_widget: Any | None,
        callback: Callable[[], None],
    ) -> None:
        """Marshal a callback to the Tkinter event loop safely."""
        self._queue.put((callback, parent_widget))
        if parent_widget is None:
            self.drain()

    def shutdown(self, wait: bool = False) -> None:
        """Shutdown the background thread pool executor."""
        self._is_shutdown = True
        self._executor.shutdown(wait=wait, cancel_futures=True)


def get_background_runner() -> BackgroundTaskRunner:
    """Obtain the global BackgroundTaskRunner convenience instance."""
    return BackgroundTaskRunner.get_instance()
