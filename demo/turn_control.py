"""Cooperative cancellation owned by a session turn, never by an HTTP socket."""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from queue import Empty, Full, Queue
import socket
from threading import Event, RLock, Thread


class TurnCancelled(RuntimeError):
    pass


_LOCK = RLock()
_TURNS: dict[str, TurnControl] = {}
_FINISHED: OrderedDict[str, str] = OrderedDict()
_CURRENT = ContextVar("civil_turn_control", default=None)
_TERMINAL = frozenset({"done", "failed", "cancelled"})


class TurnControl:
    def __init__(self, session: str):
        self.session = session
        self.event = Event()
        self.state = "running"
        self._lock = RLock()
        self._closers: list = []

    def check(self):
        if self.event.is_set():
            raise TurnCancelled("本轮已取消")

    def request_cancel(self) -> bool:
        with self._lock:
            if self.state in _TERMINAL:
                return False
            self.event.set()
            self.state = "cancelling"
            closers = list(reversed(self._closers))
        for closer in closers:
            try:
                closer()
            except Exception:
                pass  # Cancellation still stops the next cooperative boundary.
        return True

    def seal(self, state: str):
        """Claim the terminal result before persistence, resolving finish/cancel races."""
        with self._lock:
            if state != "cancelled":
                self.check()
            self.state = state

    @contextmanager
    def interrupt_on_cancel(self, closer):
        with self._lock:
            self.check()
            self._closers.append(closer)
        try:
            yield
        finally:
            with self._lock:
                self._closers.remove(closer)


def acquire(session: str) -> TurnControl:
    with _LOCK:
        if session in _TURNS:
            raise ValueError("这个会话正在处理上一条消息，请完成或停止后重试")
        control = TurnControl(session)
        _TURNS[session] = control
        _FINISHED.pop(session, None)
        return control


def release(control: TurnControl, state: str):
    with _LOCK:
        if _TURNS.get(control.session) is not control:
            return
        _TURNS.pop(control.session)
        _FINISHED[control.session] = state
        while len(_FINISHED) > 256:
            _FINISHED.popitem(last=False)


def status(session: str) -> dict:
    with _LOCK:
        control = _TURNS.get(session)
        state = control.state if control else _FINISHED.get(session, "idle")
        return {"session_id": session, "state": state, "active": control is not None,
                "cancel_requested": bool(control and control.event.is_set())}


def cancel(session: str) -> dict:
    with _LOCK:
        control = _TURNS.get(session)
    requested = bool(control and control.request_cancel())
    return {"ok": True, **status(session), "cancel_requested": requested}


@contextmanager
def using(control: TurnControl):
    token = _CURRENT.set(control)
    try:
        yield
    finally:
        _CURRENT.reset(token)


@contextmanager
def interrupt_http(resource):
    """Close this turn's HTTP connection, including a currently blocked socket read."""
    control = _CURRENT.get()
    if control is None:
        yield
        return

    def close():
        stream = getattr(resource, "extensions", {}).get("network_stream")
        if stream is not None:
            connection = stream.get_extra_info("socket")
            if connection is not None:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
        resource.close()

    with control.interrupt_on_cancel(close):
        yield
        control.check()


@contextmanager
def interrupt_event(resource, event=None):
    """A child deadline can interrupt its own transport without cancelling siblings."""
    if event is None:
        yield
        return
    if event.is_set():
        raise InterruptedError("子任务已停止")
    finished = Event()

    def monitor():
        while not finished.wait(0.05):
            if not event.is_set():
                continue
            try:
                stream = getattr(resource, "extensions", {}).get("network_stream")
                connection = stream.get_extra_info("socket") if stream is not None else None
                if connection is not None:
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                resource.close()
            except Exception:
                pass
            return

    watcher = Thread(target=monitor, name="civil-child-transport", daemon=True)
    watcher.start()
    try:
        yield
        if event.is_set():
            raise InterruptedError("子任务已停止")
    finally:
        finished.set()
        watcher.join(timeout=0.5)


def model_events(iterator, control: TurnControl):
    """Read-only model work can be detached after its transport is interrupted.

    The producer alone advances/closes the generator. No generator is closed from
    another thread and no thread is killed; a blocked third-party iterator may
    finish later, but its output is discarded and it cannot start another step.
    """
    queue = Queue(maxsize=32)
    finished = Event()

    def produce():
        try:
            with using(control):
                control.check()
                for item in iterator:
                    control.check()
                    while not control.event.is_set():
                        try:
                            queue.put((True, item), timeout=0.05)
                            break
                        except Full:
                            pass
        except Exception as exc:
            while not control.event.is_set():
                try:
                    queue.put((False, exc), timeout=0.05)
                    break
                except Full:
                    pass
        finally:
            try:
                if hasattr(iterator, "close"):
                    iterator.close()
            finally:
                finished.set()

    Thread(target=produce, name="civil-model-" + control.session, daemon=True).start()
    while True:
        control.check()
        try:
            success, value = queue.get(timeout=0.05)
        except Empty:
            if finished.is_set():
                control.check()
                return
            continue
        control.check()
        if not success:
            raise value
        yield value
