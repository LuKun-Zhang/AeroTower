"""稳定种子与 RNG 工厂。

为什么不用内置 ``hash()``：Python 对 str 的 hash 受 ``PYTHONHASHSEED`` 影响，
同一输入在不同进程会得到不同结果，实验无法跨进程复现。这里统一用
``zlib.crc32``，并允许把实验种子混入，从而让同一份条件在任何进程都一致。
"""

import random
import zlib

_MASK = 0x7FFFFFFF


def stable_hash(text, mod=100000):
    """与进程无关的稳定哈希，返回 [0, mod)。"""
    value = zlib.crc32(str(text).encode('utf-8')) & 0xFFFFFFFF
    return value % max(1, int(mod))


def derive_seed(seed, salt=''):
    """把实验种子与用途盐混成一个 31 位整数。"""
    return stable_hash(f"{int(seed)}:{salt}", _MASK)


def rng_for(seed, salt=''):
    """为某个用途创建独立的 Random 实例，不触碰全局 random。"""
    return random.Random(derive_seed(seed, salt))


def mixed_seed(seed, key):
    """在实验种子之上混入业务键（机场/日期等），用于算法内部打散。"""
    base = int(seed) if seed is not None else 2024
    return stable_hash(f"{base}:{key}", _MASK)
