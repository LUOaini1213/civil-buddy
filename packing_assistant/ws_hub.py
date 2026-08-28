"""进程内事件总线：SSE 与 WebSocket 多 tab 共享订阅。

键: session_id 或 run_id
发布: publish(key, event)  — 同步 pipeline 可从任意线程调用
订阅: subscribe(key) -> queue.Queue  — WebSocket 协程阻塞 get
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Dict, List, Set


class EventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key -> set of queues
        self._subs: Dict[str, Set[queue.Queue]] = {}
        # 最近事件环形缓冲，供晚订阅者 catch-up
        self._recent: Dict[str, List[Dict[str, Any]]] = {}
        self._recent_max = 200
        # 缓冲键数上限：长跑进程防内存泄漏（无订阅者的最老键先淘汰）
        self._recent_keys_max = 512

    def _evict_stale_recent_locked(self) -> None:
        """持锁调用：超出键数上限时，淘汰最老且无在线订阅者的键。"""
        if len(self._recent) <= self._recent_keys_max:
            return
        for k in list(self._recent.keys()):
            if len(self._recent) <= self._recent_keys_max:
                break
            if k not in self._subs:
                self._recent.pop(k, None)

    def subscribe(self, key: str) -> queue.Queue:
        k = str(key or "default")
        q: queue.Queue = queue.Queue(maxsize=500)
        with self._lock:
            self._subs.setdefault(k, set()).add(q)
            # catch-up
            for ev in self._recent.get(k, []):
                try:
                    q.put_nowait(ev)
                except queue.Full:
                    break
        return q

    def unsubscribe(self, key: str, q: queue.Queue) -> None:
        k = str(key or "default")
        with self._lock:
            qs = self._subs.get(k)
            if not qs:
                return
            qs.discard(q)
            if not qs:
                self._subs.pop(k, None)

    def publish(self, key: str, event: Dict[str, Any]) -> int:
        """返回投递到的订阅者数量。"""
        k = str(key or "default")
        ev = dict(event)
        with self._lock:
            buf = self._recent.setdefault(k, [])
            buf.append(ev)
            if len(buf) > self._recent_max:
                del buf[: len(buf) - self._recent_max]
            self._evict_stale_recent_locked()
            qs = list(self._subs.get(k, set()))
        n = 0
        for q in qs:
            try:
                q.put_nowait(ev)
                n += 1
            except queue.Full:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    q.put_nowait(ev)
                    n += 1
                except queue.Full:
                    pass
        # 同时广播到 run_id 别名
        rid = str(ev.get("run_id") or "")
        if rid and rid != k:
            n += self._publish_alias(rid, ev)
        return n

    def _publish_alias(self, key: str, ev: Dict[str, Any]) -> int:
        with self._lock:
            qs = list(self._subs.get(key, set()))
            buf = self._recent.setdefault(key, [])
            buf.append(ev)
            if len(buf) > self._recent_max:
                del buf[: len(buf) - self._recent_max]
            self._evict_stale_recent_locked()
        n = 0
        for q in qs:
            try:
                q.put_nowait(ev)
                n += 1
            except queue.Full:
                pass
        return n

    def subscriber_count(self, key: str) -> int:
        with self._lock:
            return len(self._subs.get(str(key or "default"), set()))


# 全局单例
HUB = EventHub()
