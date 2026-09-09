"""Shared deadline for read-only public adapters; late results cannot persist.

Never pass a callback that writes a database or external service. Persistence is
performed by the caller only after this function successfully returns.
"""
import signal
import threading
from collections.abc import Callable
from time import monotonic
from typing import TypeVar, cast

T = TypeVar('T')


class PublicReadDeadlineExceeded(TimeoutError):
    pass


def _alarm(_signum, _frame):
    raise PublicReadDeadlineExceeded('DEADLINE_EXCEEDED')


def bounded_public_read(invoke: Callable[[], T], deadline_monotonic: float | None) -> T:
    if deadline_monotonic is None:
        return invoke()
    remaining = deadline_monotonic - monotonic()
    if remaining <= 0:
        raise PublicReadDeadlineExceeded('DEADLINE_EXCEEDED')
    alarm_supported = (threading.current_thread() is threading.main_thread()
                       and hasattr(signal, 'setitimer') and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))
    if alarm_supported:
        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        try:
            value = invoke()
            if monotonic() >= deadline_monotonic:
                raise PublicReadDeadlineExceeded('DEADLINE_EXCEEDED')
            return value
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    completed = threading.Event()
    result: T | None = None
    failure: Exception | None = None

    def read_in_background():
        nonlocal result, failure
        try:
            result = invoke()
        except Exception as error:  # noqa: BLE001 - re-raise on the caller thread
            failure = error
        finally:
            completed.set()

    threading.Thread(target=read_in_background, daemon=True).start()
    if not completed.wait(remaining) or monotonic() >= deadline_monotonic:
        raise PublicReadDeadlineExceeded('DEADLINE_EXCEEDED')
    if failure is not None:
        raise failure
    return cast(T, result)
