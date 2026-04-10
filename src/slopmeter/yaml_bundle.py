from __future__ import annotations

import json
from collections.abc import Mapping, Sequence


def _format_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return repr(value)
    return json.dumps(str(value), ensure_ascii=False)


def _dump_lines(value: object, *, indent: int) -> list[str]:
    prefix = " " * indent

    if isinstance(value, Mapping):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)) and not item:
                lines.append(f"{prefix}{key}: []")
                continue
            if isinstance(item, Mapping) or (
                isinstance(item, Sequence)
                and not isinstance(item, (str, bytes, bytearray))
            ):
                lines.append(f"{prefix}{key}:")
                nested = _dump_lines(item, indent=indent + 2)
                lines.extend(nested or [f"{prefix}  []"])
            else:
                lines.append(f"{prefix}{key}: {_format_scalar(item)}")
        return lines

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if not value:
            return [f"{prefix}[]"]
        lines = []
        for item in value:
            if isinstance(item, Mapping) or (
                isinstance(item, Sequence)
                and not isinstance(item, (str, bytes, bytearray))
            ):
                lines.append(f"{prefix}-")
                nested = _dump_lines(item, indent=indent + 2)
                lines.extend(nested or [f"{prefix}  []"])
            else:
                lines.append(f"{prefix}- {_format_scalar(item)}")
        return lines

    return [f"{prefix}{_format_scalar(value)}"]


def dump_yaml(value: object) -> str:
    return "\n".join(_dump_lines(value, indent=0)) + "\n"
