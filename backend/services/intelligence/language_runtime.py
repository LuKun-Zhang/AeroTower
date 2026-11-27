"""固定CPU推理格式；低内存时在加载大权重前明确退回模板。"""
import ctypes
import sys

DTYPE = "float32"
THREADS = 4


class MemoryStatus(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)]+[(name, ctypes.c_ulonglong) for name in
        ("total", "available", "page_total", "page_available", "virtual_total", "virtual_available", "extended")]


def ensure_memory(large_model):
    if sys.platform != "win32":
        return
    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise RuntimeError("无法确认可用内存，本次回退模板")
    minimum = (6.5 if large_model else 2)*2**30
    if memory.available < minimum:
        raise RuntimeError("可用内存不足，1.5B模型需要约7GB可用内存；本次回退模板，关闭其他程序后可重试" if large_model else "可用内存不足，本次回退模板")
