from secrets import randbits
from time import time_ns
from uuid import UUID


def uuid7() -> UUID:
    """Create a time-ordered RFC 9562 UUIDv7."""
    unix_milliseconds = time_ns() // 1_000_000
    value = (unix_milliseconds & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= randbits(12) << 64
    value |= 0b10 << 62
    value |= randbits(62)
    return UUID(int=value)
