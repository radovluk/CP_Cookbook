"""
Type definitions and wrapper utilities for OptalCP Python API.

This module contains the low-level type definitions used for JSON serialization
and argument wrapping. It has no internal dependencies except _constants.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NotRequired, TypeAlias, TypedDict


class _ElementProps(TypedDict):
    """
    Properties of a model element for JSON serialization.

    Required fields: func, args
    All other fields are optional.
    """
    # Required fields
    func: str  # Function name (e.g., "intervalVar", "plus", "endOf")
    args: list[_Argument]  # Forward reference to break circular dependency

    # Optional fields
    name: NotRequired[str]
    status: NotRequired[int]  # PresenceStatus
    # For IntVar and BoolVar:
    min: NotRequired[int]
    max: NotRequired[int]
    # For IntervalVar:
    startMin: NotRequired[int]
    startMax: NotRequired[int]
    endMin: NotRequired[int]
    endMax: NotRequired[int]
    lengthMin: NotRequired[int]
    lengthMax: NotRequired[int]
    # For IntStepFunction:
    values: NotRequired[list[list[int]]]

class _IndirectArgument(TypedDict, total=False):
    """Represents an indirect argument with optional 'arg' (ElementProps) or 'ref' (reference ID)."""
    arg: _ElementProps  # Inlined expression
    ref: int  # Reference ID

_ScalarArgument: TypeAlias = int | float | bool | _IndirectArgument
_Argument: TypeAlias = _ScalarArgument | list[_ScalarArgument] | list[list[int]]

def _wrap_int(value: int) -> _ScalarArgument:
    """Internal: Ensure the value is an integer."""
    if not isinstance(value, (int, bool)): # type: ignore[misc]
        raise TypeError(f"Expected int or bool. Got {type(value).__name__}")
    return value

def _wrap_bool(value: bool) -> _ScalarArgument:
    """Internal: Ensure the value is a boolean."""
    if not isinstance(value, bool): # type: ignore[misc]
        raise TypeError(f"Expected bool. Got {type(value).__name__}")
    return value

def _wrap_int_list(values: Iterable[int]) -> list[_ScalarArgument]: # type: ignore[reportUnusedFunction]
    """
    Internal: Ensure the values are a list of integers.
    Copy the array so that if the user changes it in the future, we are not affected by the change.
    """
    # Validate all elements first
    for v in values:
        if not isinstance(v, (int, bool)): # type: ignore[misc]
            raise TypeError(f"Expected list of int or bool. Got {type(v).__name__}")
    # Then make a shallow copy
    return list(values)

def _wrap_int_matrix(values: Iterable[Iterable[int]]) -> _Argument: # type: ignore[reportUnusedFunction]
    """
    Internal: Ensure the values are a matrix (list of lists) of integers.
    Copy the matrix so that if the user changes it in the future, we are not affected by the change.
    """
    # Validate all elements first
    for row in values:
        for v in row:
            if not isinstance(v, (int, bool)): # type: ignore[misc]
                raise TypeError(f"Expected list of list of int or bool. Got {type(v).__name__}")
    # Then make a deep copy using list comprehensions
    return [[int(v) for v in row] for row in values]
