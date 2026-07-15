import subprocess
import threading


class RunTestCancelled(Exception):
    pass


class LocateTaskBusy(Exception):
    pass


class LocateTaskBus:
    def __init__(self):
        self._task_lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._process_lock = threading.Lock()
        self._current_process = None
        self._running = False

    @property
    def is_running(self):
        return self._running

    def begin_task(self):
        if not self._task_lock.acquire(blocking=False):
            raise LocateTaskBusy("已有衰退定位任务正在运行，请等待完成后再启动。")
        self._cancel_event.clear()
        self._running = True

    def end_task(self):
        self._running = False
        self._cancel_event.clear()
        with self._process_lock:
            self._current_process = None
        if self._task_lock.locked():
            self._task_lock.release()

    def cancel(self):
        self._cancel_event.set()
        with self._process_lock:
            process = self._current_process
        if process and process.poll() is None:
            print("[INFO] 正在终止当前 RunTest 进程...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()

    def check_cancelled(self):
        if self._cancel_event.is_set():
            raise RunTestCancelled("衰退定位任务已终止")

    def attach_process(self, process):
        with self._process_lock:
            self._current_process = process

    def detach_process(self):
        with self._process_lock:
            self._current_process = None


LOCATE_TASK_BUS = LocateTaskBus()
