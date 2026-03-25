"""
Constants for the OptalCP package.
"""

from __future__ import annotations

from enum import IntEnum

IntVarMax = 1073741823
r"""
Maximum value of a decision variable or a decision expression (such as `x+1` where `x` is a variable).

Arithmetic expressions must stay within the range [:const:`IntVarMin`, :const:`IntVarMax`]. If an expression exceeds this range for all possible variable assignments, the model becomes infeasible.

## Example

The following model is infeasible because `x*x` exceeds `IntVarMax` for all values in the variable's domain:

.. code-block:: python

    import optalcp as cp

    model = cp.Model()
    x = model.int_var(min=10000000, max=20000000)
    # Constraint x*x >= 1:
    model.enforce(x * x >= 1)
    result = model.solve()

For any value of `x` in the range [10000000, 20000000], the expression `x*x` exceeds :const:`IntVarMax` and cannot be computed, making the model infeasible.
"""

IntVarMin = -IntVarMax
r"""
Minimum value of a decision variable or a decision expression (such as `x+1` where `x` is a variable).
The opposite of :const:`IntVarMax`.

Use `IntVarMin` when you need to allow the full range of negative values for an integer variable.

## Example

.. code-block:: python

    import optalcp as cp

    model = cp.Model()
    # IntVarMin is the minimum allowed value for integer variables
    x = model.int_var(min=cp.IntVarMin, max=0, name="x")
"""

IntervalMax = 715827882
r"""
Maximum value of start or end of an interval variable. The opposite of :const:`IntervalMin`.

Use `IntervalMax` when you want to leave the end time of an interval variable unconstrained.

## Example

.. code-block:: python

    import optalcp as cp

    model = cp.Model()
    # IntervalMax is the maximum allowed value for interval start/end
    task = model.interval_var(end=(0, cp.IntervalMax), length=10, name="task")
"""

IntervalMin = -IntervalMax
r"""
Minimum value of start or end of an interval variable. The opposite of :const:`IntervalMax`.

Use `IntervalMin` when you want to leave the start time of an interval variable unconstrained.

## Example

.. code-block:: python

    import optalcp as cp

    model = cp.Model()
    # IntervalMin is the minimum allowed value for interval start/end
    task = model.interval_var(start=(cp.IntervalMin, 0), length=10, name="task")
"""

LengthMax = IntervalMax - IntervalMin
r"""
Maximum length of an interval variable. The maximum length can be achieved by
an interval that starts at :const:`IntervalMin` and ends at :const:`IntervalMax`.

Use `LengthMax` when you want to leave the length of an interval variable unconstrained.

## Example

.. code-block:: python

    import optalcp as cp

    model = cp.Model()
    # LengthMax is the maximum allowed length for an interval variable
    task = model.interval_var(length=(0, cp.LengthMax), name="task")
"""

# Presence status values (synchronized with C++ enum Presence::Value)
# Internal - use is_optional(), is_present(), is_absent() methods instead
class _PresenceStatus(IntEnum):
    Optional = 0
    Present = 1
    Absent = 2
