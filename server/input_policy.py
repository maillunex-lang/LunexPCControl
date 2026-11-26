"""REL-02 preparatory argument validators for Windows desktop input.

No control tools are enabled by merely importing this module.
The gateway stays strictly read-only until an independently authenticated
time-limited consent mechanism is installed and tested.
"""
from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_INPUT = frozenset({"Click", "Type", "Scroll", "Move"})
MAX_COORDINATE = 8191
MAX_TEXT_LENGTH = 500

class InputPolicyError(ValueError):
    """Unsafe or malformed remote input request."""


def _point(point):
    if not isinstance(point, list) or len(point) != 2:
        raise InputPolicyError("loc must be an array with x and y")
    if any(type(v) is not int or v < 0 or v > MAX_COORDINATE for v in point):
        raise InputPolicyError("coordinates must be bounded nonnegative integers")
    return point


def _exact_keys(arguments, allowed, required):
    if not isinstance(arguments, dict):
        raise InputPolicyError("arguments must be a JSON object")
    if not required.issubset(arguments) or not set(arguments).issubset(allowed):
        raise InputPolicyError("unexpected or missing arguments")


def _enum(value, values):
    if type(value) is not str or value not in values:
        raise InputPolicyError("invalid action parameter")


def validate_input(name, arguments):
    """Return a strict normalized input request or raise before forwarding.

    The returned arguments never contain label-based clicks, drag,
    keyboard shortcuts, submission via Enter, arbitrary upstream extensions,
    or a payload larger than the documented bound.
    """
    if name not in SUPPORTED_INPUT:
        raise InputPolicyError("unsupported input tool")
    if name == "Click":
        _exact_keys(arguments, {"loc", "button", "clicks"}, {"loc"})
        _point(arguments["loc"])
        button = arguments.get("button", "left")
        clicks = arguments.get("clicks", 1)
        _enum(button, {"left", "right", "middle"})
        if type(clicks) is not int or clicks not in (0, 1, 2):
            raise InputPolicyError("only hover, single or double click permitted")
        return {"loc": list(arguments["loc"]), "button": button, "clicks": clicks}
    if name == "Move":
        _exact_keys(arguments, {"loc"}, {"loc"})
        _point(arguments["loc"])
        return {"loc": list(arguments["loc"]), "drag": False}
    if name == "Scroll":
        _exact_keys(arguments, {"loc", "type", "direction", "wheel_times"}, {"loc"})
        _point(arguments["loc"])
        kind = arguments.get("type", "vertical")
        direction = arguments.get("direction", "down")
        wheel_times = arguments.get("wheel_times", 1)
        _enum(kind, {"vertical", "horizontal"})
        _enum(direction, {"up", "down"} if kind == "vertical" else {"left", "right"})
        if type(wheel_times) is not int or not 1 <= wheel_times <= 10:
            raise InputPolicyError("wheel amount must be between 1 and 10")
        return {"loc": list(arguments["loc"]), "type": kind,
                "direction": direction, "wheel_times": wheel_times}
    _exact_keys(arguments, {"loc", "text", "clear"}, {"loc", "text"})
    _point(arguments["loc"])
    value = arguments["text"]
    clear = arguments.get("clear", False)
    if type(value) is not str or not 1 <= len(value) <= MAX_TEXT_LENGTH or "\x00" in value:
        raise InputPolicyError("text length/content invalid")
    if type(clear) is not bool:
        raise InputPolicyError("clear must be boolean")
    return {"loc": list(arguments["loc"]), "text": value,
            "clear": clear, "press_enter": False, "caret_position": "idle"}
