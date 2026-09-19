"""Linux: the worker confines itself with Landlock (writes, TCP) and seccomp (inet sockets, exec).

Both are unprivileged and irreversible for the life of the process, and both bind root too.

    Landlock   only *write-type* filesystem access is handled, so reading and executing stay
               allowed everywhere while create / write / truncate / rename / delete are allowed
               only beneath the write roots. ABI >= 4 also denies TCP bind and connect.
    seccomp    socket(AF_INET | AF_INET6) and execve / execveat return EPERM. AF_UNIX is left
               alone (the interpreter and resolvers use it); a forked child cannot become
               another program. Works on kernels that have no Landlock at all.
"""

from __future__ import annotations

import ctypes
import os
import platform
from typing import Any, Dict, Sequence

_SYS_CREATE, _SYS_ADD_RULE, _SYS_RESTRICT = 444, 445, 446          # same numbers on every architecture
_WRITE_V1 = sum(1 << bit for bit in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12))   # write_file, remove_*, make_*
_REFER, _TRUNCATE = 1 << 13, 1 << 14                                 # ABI 2, ABI 3
_NET_TCP = 0b11                                                      # bind_tcp | connect_tcp, ABI 4
_PR_SET_NO_NEW_PRIVS, _PR_SET_SECCOMP, _SECCOMP_MODE_FILTER = 38, 22, 2
_ARCH = {"x86_64": (0xC000003E, 41, 59, 322), "aarch64": (0xC00000B7, 198, 221, 281)}   # audit arch, socket, execve, execveat


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class _SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_uint16), ("jt", ctypes.c_uint8), ("jf", ctypes.c_uint8), ("k", ctypes.c_uint32)]


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_uint16), ("filter", ctypes.POINTER(_SockFilter))]


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def landlock_abi() -> int:
    """0 when the kernel has no Landlock (or it is not in the active LSM list)."""
    try:
        version = _libc().syscall(_SYS_CREATE, None, 0, 1)
    except (OSError, AttributeError):
        return 0
    return max(0, int(version))


def probe() -> Dict[str, Any]:
    abi = landlock_abi()
    seccomp = platform.machine() in _ARCH
    return {"backend": "linux-landlock-seccomp", "available": abi > 0 or seccomp, "landlock_abi": abi,
            "enforces": {"write": abi > 0, "spawn": seccomp, "network": seccomp or abi >= 4},
            "reason": "" if abi > 0 else "内核没有启用 Landlock，写入无法由内核限制"}


def _landlock(write_roots: Sequence[str], abi: int, network: bool) -> None:
    libc = _libc()
    flags = _WRITE_V1 | (_REFER if abi >= 2 else 0) | (_TRUNCATE if abi >= 3 else 0)
    attr = _RulesetAttr(flags, _NET_TCP if abi >= 4 and not network else 0)
    ruleset = libc.syscall(_SYS_CREATE, ctypes.byref(attr), ctypes.sizeof(attr) if abi >= 4 else 8, 0)
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), "landlock_create_ruleset: " + os.strerror(ctypes.get_errno()))
    try:
        for root in write_roots:
            parent = os.open(root, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = _PathBeneath(flags, parent)
                if libc.syscall(_SYS_ADD_RULE, ruleset, 1, ctypes.byref(rule), 0) != 0:
                    raise OSError(ctypes.get_errno(), "landlock_add_rule: " + os.strerror(ctypes.get_errno()))
            finally:
                os.close(parent)
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
        if libc.syscall(_SYS_RESTRICT, ruleset, 0) != 0:
            raise OSError(ctypes.get_errno(), "landlock_restrict_self: " + os.strerror(ctypes.get_errno()))
    finally:
        os.close(ruleset)


def _seccomp(network: bool, spawn: bool) -> None:
    audit, nr_socket, nr_execve, nr_execveat = _ARCH[platform.machine()]
    ld, jeq, ret = 0x20, 0x15, 0x06
    allow, eperm = 0x7FFF0000, 0x00050000 | 1
    program = [(ld, 0, 0, 4), (jeq, 1, 0, audit), (ret, 0, 0, allow),      # a foreign-arch syscall is not ours to judge
               (ld, 0, 0, 0)]
    if not network:                                                         # socket(AF_INET=2 | AF_INET6=10) -> EPERM
        program += [(jeq, 0, 5, nr_socket), (ld, 0, 0, 16), (jeq, 2, 0, 2), (jeq, 1, 0, 10), (ret, 0, 0, allow), (ret, 0, 0, eperm)]
    if not spawn:
        program += [(jeq, 1, 0, nr_execve), (jeq, 0, 1, nr_execveat), (ret, 0, 0, eperm)]
    program.append((ret, 0, 0, allow))
    array = (_SockFilter * len(program))(*[_SockFilter(*ins) for ins in program])
    libc = _libc()
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS")
    if libc.prctl(_PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(_SockFprog(len(program), array)), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "seccomp: " + os.strerror(ctypes.get_errno()))


def confine_self(write_roots: Sequence[str], *, network: bool = False, spawn: bool = False) -> Dict[str, Any]:
    """Apply everything this kernel offers and say what that was. Raises if nothing could hold writes."""
    abi = landlock_abi()
    if abi <= 0:
        raise OSError("内核没有 Landlock：写入无法由内核限制")
    _landlock(write_roots, abi, network)
    filtered = platform.machine() in _ARCH
    if filtered:
        _seccomp(network, spawn)
    return {"backend": "linux-landlock-seccomp", "landlock_abi": abi,
            "enforces": {"write": True, "spawn": filtered and not spawn, "network": (filtered or abi >= 4) and not network}}
