"""
Activity Tracker – hjälpprocess för psutil.open_files()

open_files() är farlig att köra i tracker-processen:
- Den håller GIL under hela anropet, så alla trådar (tracker, webb, watchdog) står
  still medan den kör – i minuter om ett filhandtag fastnar (t.ex. efter viloläge).
- När NtQueryObject fastnar dödar psutil sin hjälptråd med TerminateThread, vilket
  kan lämna Windows-lås och heap i oordning: nya trådar startar aldrig och processen
  kan krascha i ntdll.dll (sett 2026-10-05 och 2026-10-21).

Därför körs anropet i en separat process. Fastnar eller kraschar den drabbas bara
den – klienten ger upp efter en timeout, dödar den och startar en ny vid behov.
"""

import os
import sys
import time
import secrets
import logging
import threading
import subprocess
import ctypes
import ctypes.wintypes as wt
from pathlib import Path
from multiprocessing.connection import Client, Listener

HELPER_ARG  = "--doc-helper"
_ENV_PIPE   = "ACTIVITY_TRACKER_DOC_PIPE"
_ENV_KEY    = "ACTIVITY_TRACKER_DOC_KEY"
HUNG_SEC    = 10    # svarar inte på så här länge → döda och starta om
RETRY_SEC   = 30    # vänta så här länge innan ny start efter att den dött/dödats
CONNECT_SEC = 10    # max tid för att starta och ansluta


# ── Serversidan (körs i hjälpprocessen) ───────────────────────

def serve_from_env():
    """Startpunkt i hjälpprocessen: svarar på pid → lista med öppna filsökvägar (eller None)."""
    import psutil
    address = os.environ[_ENV_PIPE]
    key = bytes.fromhex(os.environ[_ENV_KEY])
    with Listener(address, family="AF_PIPE", authkey=key) as listener:
        conn = listener.accept()
    while True:
        try:
            pid = conn.recv()
        except (EOFError, OSError):
            return  # trackern har stängt anslutningen eller dött
        try:
            files = [f.path for f in psutil.Process(pid).open_files()]
        except Exception:
            files = None
        try:
            conn.send(files)
        except OSError:
            return


# ── Klientsidan (körs i tracker-processen) ────────────────────

# Egen WinDLL-instans så att argtypes/restype inte påverkar tracker.py:s kernel32
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _BASIC_LIMIT(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wt.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wt.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wt.DWORD),
        ("SchedulingClass", wt.DWORD),
    ]


class _EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BASIC_LIMIT),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
_k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
_k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JobObjectExtendedLimitInformation = 9
_job = None


def _kill_with_parent(proc):
    """Lägger hjälpprocessen i ett jobb som Windows stänger när tracker-processen dör,
    så att en hängd hjälpprocess aldrig blir kvar som föräldralös."""
    global _job
    try:
        if _job is None:
            job = _k32.CreateJobObjectW(None, None)
            if not job:
                return
            info = _EXTENDED_LIMIT()
            info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _k32.SetInformationJobObject(job, _JobObjectExtendedLimitInformation,
                                                ctypes.byref(info), ctypes.sizeof(info)):
                return
            _job = job
        _k32.AssignProcessToJobObject(_job, int(proc._handle))
    except Exception:
        logging.exception("[DocHelper] Kunde inte koppla hjälpprocessen till ett jobb")


def _helper_cmd():
    if getattr(sys, "frozen", False):
        return [sys.executable, HELPER_ARG]
    return [sys.executable, str(Path(__file__).resolve())]


class DocHelper:
    """Ett anrop i taget. Svar som kommer efter timeout kastas, och medan ett gammalt
    anrop fortfarande pågår hoppas nya över (returnerar None) i stället för att vänta."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._conn = None
        self._pending_since = None
        self._retry_after = 0.0

    def open_files(self, pid, timeout):
        """Lista med öppna filsökvägar för pid, eller None (fel, timeout eller upptagen)."""
        with self._lock:
            try:
                if not self._ensure_running():
                    return None
                if self._pending_since is not None:
                    if self._conn.poll(0):
                        self._conn.recv()  # sent svar på ett tidigare anrop – kasta
                        self._pending_since = None
                    elif time.monotonic() - self._pending_since > HUNG_SEC:
                        logging.warning(f"[DocHelper] Svarar inte på {HUNG_SEC}s – startar om")
                        self._stop()
                        return None
                    else:
                        return None
                self._conn.send(pid)
                self._pending_since = time.monotonic()
                if self._conn.poll(timeout):
                    files = self._conn.recv()
                    self._pending_since = None
                    return files
                return None
            except Exception:
                logging.warning("[DocHelper] Hjälpprocessen dog – startar om vid behov")
                self._stop()
                return None

    def _ensure_running(self):
        if self._conn is not None and self._proc.poll() is None:
            return True
        if self._conn is not None:
            logging.warning(f"[DocHelper] Hjälpprocessen avslutades (kod {self._proc.returncode})")
            self._stop()
        if time.monotonic() < self._retry_after:
            return False
        address = rf"\\.\pipe\activity_tracker_doc_{os.getpid()}_{secrets.token_hex(4)}"
        key = secrets.token_bytes(16)
        env = dict(os.environ, **{_ENV_PIPE: address, _ENV_KEY: key.hex()})
        try:
            self._proc = subprocess.Popen(
                _helper_cmd(), env=env, close_fds=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            logging.exception("[DocHelper] Kunde inte starta hjälpprocessen")
            self._retry_after = time.monotonic() + RETRY_SEC
            return False
        _kill_with_parent(self._proc)
        deadline = time.monotonic() + CONNECT_SEC
        while True:
            try:
                self._conn = Client(address, family="AF_PIPE", authkey=key)
                return True
            except Exception:  # pipen finns inte än, eller handskakningen avbröts
                if self._proc.poll() is not None or time.monotonic() > deadline:
                    logging.warning("[DocHelper] Kunde inte ansluta till hjälpprocessen")
                    self._stop()
                    return False
                time.sleep(0.1)

    def _stop(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.kill()
            except OSError:
                pass
        self._conn = self._proc = self._pending_since = None
        self._retry_after = time.monotonic() + RETRY_SEC


if __name__ == "__main__":
    serve_from_env()
