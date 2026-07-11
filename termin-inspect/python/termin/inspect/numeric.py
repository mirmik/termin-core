"""Exact numeric parsing shared by inspector frontends."""

from __future__ import annotations


UINT32_MAX = 4_294_967_295


def parse_uint32(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("uint32 value cannot be boolean")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text or not text.isdecimal():
            raise ValueError("uint32 value must be an unsigned decimal integer")
        parsed = int(text, 10)
    else:
        raise ValueError("uint32 value must be an integer or decimal string")
    if not 0 <= parsed <= UINT32_MAX:
        raise ValueError(f"uint32 value must be in [0, {UINT32_MAX}]")
    return parsed


__all__ = ["UINT32_MAX", "parse_uint32"]
