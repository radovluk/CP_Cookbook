"""
Scheduling-related variable classes for OptalCP Python API.

This module contains:
- IntStepFunction: Step functions for scheduling
- SequenceVar: Sequence variables for ordering tasks
- IntervalVar: Interval variables for representing tasks
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ._constants import IntervalMax, LengthMax, _PresenceStatus
from ._expressions import (
    BoolExpr,
    Constraint,
    CumulExpr,
    IntExpr,
    ModelElement,
    _Argument,
    _ElementProps,
    _ScalarArgument,
    _wrap_int,
    _wrap_int_list,
    _wrap_int_matrix,
)

if TYPE_CHECKING:
    from ._expressions import _Directive
    from ._model import Model


# =============================================================================
# IntStepFunction
# =============================================================================

class IntStepFunction(ModelElement):
    r"""
    Integer step function.

    Integer step function is a piecewise constant function defined on integer
    values in range :const:`IntVarMin` to :const:`IntVarMax`. The function can be
    created by :meth:`Model.step_function`.

    Step functions can be used in the following ways:

    * Function :meth:`Model.eval` evaluates the function at the given point (given as :class:`IntExpr`).
    * Function :meth:`Model.integral` computes a sum (integral) of the function over an :class:`IntervalVar`.
    * Constraints :meth:`Model.forbid_start` and :meth:`Model.forbid_end` forbid the start/end of an :class:`IntervalVar` to be in a zero-value interval of the function.
    * Constraint :meth:`Model.forbid_extent` forbids the extent of an :class:`IntervalVar` to be in a zero-value interval of the function.
    """

    def __init__(self, model: Model, values: Iterable[tuple[int, int]]):
        # Internal constructor - users create step functions via Model.step_function()
        super().__init__(model, "intStepFunction", [])

        # Validate and copy the array so the user cannot change it later
        validated_values: list[list[int]] = []
        for i, item in enumerate(values):
            # Check if item is a sequence with exactly 2 elements
            if not hasattr(item, '__len__'):
                raise ValueError(f"Step function item at index {i} must be a sequence of 2 integers (value, next_point), got non-sequence: {item!r}")
            if len(item) != 2:
                raise ValueError(f"Step function item at index {i} must have exactly 2 elements (value, next_point), got {len(item)}: {item!r}")

            # Extract the two values
            val, next_point = item

            # Validate both are integers
            if not isinstance(val, int): # type: ignore[misc]
                raise TypeError(f"Step function value at index {i} must be an integer, got {type(val).__name__}")
            if not isinstance(next_point, int): # type: ignore[misc]
                raise TypeError(f"Step function next_point at index {i} must be an integer, got {type(next_point).__name__}")

            # Store as a list [value, next_point] to match the JSON format
            validated_values.append([val, next_point])

        self._props['values'] = validated_values

    @staticmethod
    def _wrap(expr: IntStepFunction) -> _ScalarArgument:
        """Internal: Convert a IntStepFunction to an argument."""
        if isinstance(expr, IntStepFunction): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected IntStepFunction. Got {type(expr).__name__}")

    def integral(self, interval: IntervalVar) -> IntExpr:
        r"""
        Computes sum of values of the step function over the interval `interval`.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The sum is computed over all integer time points from `interval.start()` to `interval.end()-1` inclusive. In other words, the sum includes the function value at the start time but excludes the value at the end time (half-open interval). If the interval variable has zero length, then the result is 0. If the interval variable is absent, then the result is *absent*.

        **Requirement**: The step function `func` must be non-negative.

        .. seealso::

            - :meth:`Model.integral` for the equivalent function on :class:`Model`.
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(interval)]
        return IntExpr(self._model, "intStepFunctionIntegral", out_params)

    def _step_function_integral_in_range(self, interval: IntervalVar, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(interval), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self._model, "intStepFunctionIntegralInRange", out_params)

    def eval(self, arg: IntExpr | int) -> IntExpr:
        r"""
        Evaluates the step function at a given point.

        :param arg: The point at which to evaluate the step function.
        :type arg: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The result is the value of the step function at the point `arg`. If the value of `arg` is `absent`, then the result is also `absent`.

        By constraining the returned value, it is possible to limit `arg` to be only within certain segments of the segmented function. In particular, functions :meth:`Model.forbid_start` and :meth:`Model.forbid_end` work that way.

        .. seealso::

            - :meth:`Model.eval` for the equivalent function on :class:`Model`.
            - :meth:`Model.forbid_start`, :meth:`Model.forbid_end` are convenience functions built on top of `eval`.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(arg)]
        return IntExpr(self._model, "intStepFunctionEval", out_params)

    def _step_function_eval_in_range(self, arg: IntExpr | int, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self._model, "intStepFunctionEvalInRange", out_params)

    def _step_function_eval_not_in_range(self, arg: IntExpr | int, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self._model, "intStepFunctionEvalNotInRange", out_params)




# =============================================================================
# SequenceVar
# =============================================================================

class SequenceVar(ModelElement):
    r"""
    Models a sequence (order) of interval variables.

    A sequence variable represents an ordered arrangement of interval variables
    where no two intervals overlap. The sequence captures not just that the intervals
    don't overlap, but also their relative ordering in the solution.

    Sequence variables are created using :meth:`Model.sequence_var` and are typically
    used with the :meth:`SequenceVar.no_overlap` constraint to enforce non-overlapping
    with optional transition times between intervals.

    The position of each interval in the sequence can be queried using
    :meth:`Model.position` or :meth:`IntervalVar.position`, which returns an integer
    expression representing the interval's index in the final ordering (0-based).
    Absent intervals have an absent position.

    .. seealso::

        - :meth:`Model.sequence_var` to create sequence variables.
        - :meth:`SequenceVar.no_overlap` for the no-overlap constraint with transitions.
        - :meth:`Model.position` to get an interval's position in the sequence.
    """

    def __init__(self, model: Model, func: str, args: list[_Argument]):
        super().__init__(model, func, args)
        self._force_ref()

    def _make_auxiliary(self) -> None:
        """Internal: Mark this sequence as auxiliary."""
        self._props['func'] = '_sequenceVar'

    @staticmethod
    def _wrap(expr: SequenceVar) -> _ScalarArgument:
        """Internal: Convert a SequenceVar to an argument."""
        if isinstance(expr, SequenceVar): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected SequenceVar. Got {type(expr).__name__}")
    @staticmethod
    def _wrap_list(exprs: Iterable[SequenceVar]) -> _Argument:
        return [SequenceVar._wrap(e) for e in exprs]

    def no_overlap(self, transitions: Iterable[Iterable[int]] | None = None) -> Constraint:
        r"""
        Constrain the interval variables forming the sequence to not overlap.

        :param transitions: 2D square array of minimum transition distances between the intervals. The first index is the type (index) of the first interval in the sequence, the second index is the type (index) of the second interval in the sequence
        :type transitions: Iterable[Iterable[int]] | None
        :rtype: Constraint
        :returns: The no-overlap constraint.

        ## Details

        The `no_overlap` constraint makes sure that the intervals in the sequence
        do not overlap.  That is, for every pair of interval variables `x` and `y`
        at least one of the following conditions must hold (in a solution):

        1. Interval variable `x` is *absent*. This means that the interval is not
        present in the solution (not performed), so it cannot overlap
        with any other interval. Only optional interval variables can be *absent*.
        2. Interval variable `y` is *absent*.
        3. `x` ends before `y` starts, i.e. `x.end()` is less or equal to `y.start()`.
        4. `y` ends before `x` starts, i.e. `y.end()` is less or equal to `x.start()`.

        In addition, if the `transitions` parameter is specified, then the cases 3 and 4
        are further constrained by the minimum transition distance between the
        intervals:

        3. `x.end() + transitions[x.type][y.type]` is less or equal to `y.start()`.
        4. `y.end() + transitions[y.type][x.type]` is less or equal to `x.start()`.

        where `x.type` and `y.type` are the types of the interval variables `x` and `y`
        as given in :meth:`Model.sequence_var`. If types were not specified,
        then they are equal to the indices of the interval variables in the array
        passed to :meth:`Model.sequence_var`. Transition times
        cannot be negative.

        Note that transition times are enforced between every pair of interval variables,
        not only between direct neighbors.

        The size of the 2D array `transitions` must be equal to the number of types
        of the interval variables.

        This constraint is equivalent to :meth:`Model.no_overlap` called with the
        sequence variable's intervals and types.

        ## Example

        A worker must perform a set of tasks. Each task is characterized by:

        * `length` of the task (how long it takes to perform it),
        * `location` of the task (where it must be performed),
        * a time window `earliest` to `deadline` when the task must be performed.

        There are three locations, `0`, `1`, and `2`. The minimum travel times between
        the locations are given by a transition matrix `transitions`. Transition times
        are not symmetric. For example, it takes 10 minutes to travel from location `0`
        to location `1` but 15 minutes to travel back from location `1` to location `0`.

        We will model this problem using `no_overlap` constraint with transition times.

        .. code-block:: python

            import optalcp as cp

            # Travel times between locations:
            transitions = [
              [ 0, 10, 10],
              [15,  0, 10],
              [ 5,  5,  0]
            ]
            # Tasks to be scheduled:
            tasks = [
              {"location": 0, "length": 20, "earliest": 0, "deadline": 100},
              {"location": 0, "length": 40, "earliest": 70, "deadline": 200},
              {"location": 1, "length": 10, "earliest": 0, "deadline": 200},
              {"location": 1, "length": 30, "earliest": 100, "deadline": 200},
              {"location": 1, "length": 10, "earliest": 0, "deadline": 150},
              {"location": 2, "length": 15, "earliest": 50, "deadline": 250},
              {"location": 2, "length": 10, "earliest": 20, "deadline": 60},
              {"location": 2, "length": 20, "earliest": 110, "deadline": 250},
            ]

            model = cp.Model()

            # From the array tasks create an array of interval variables:
            task_vars = [model.interval_var(
              name=f"Task{i}", length=t["length"], start=(t["earliest"], None), end=(None, t["deadline"])
            ) for i, t in enumerate(tasks)]
            # And an array of locations:
            types = [t["location"] for t in tasks]

            # Create the sequence variable for the tasks, location is the type:
            sequence = model.sequence_var(task_vars, types)
            # Tasks must not overlap and transitions must be respected:
            sequence.no_overlap(transitions)

            # Solve the model:
            result = model.solve({'solutionLimit': 1})
        """
        if transitions is None:
            return Constraint(self._model, 'noOverlap', [self._as_arg()])
        else:
            return Constraint(self._model, 'noOverlap', [self._as_arg(), _wrap_int_matrix(transitions)])

    def _same_sequence(self, sequence2: SequenceVar) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), SequenceVar._wrap(sequence2)]
        return Constraint(self._model, "sameSequence", out_params)




# =============================================================================
# IntervalVar
# =============================================================================

class IntervalVar(ModelElement):
    r"""
    Interval variable is a task, action, operation, or any other interval with a start
    and an end. The start and the end of the interval are unknowns that the solver
    has to find. They could be accessed as integer expressions using
    :meth:`IntervalVar.start` and :meth:`IntervalVar.end`.
    or using :meth:`Model.start` and :meth:`Model.end`.
    In addition to the start and the end of the interval, the interval variable
    has a length (equal to *end - start*) that can be accessed using
    :meth:`IntervalVar.length` or :meth:`Model.length`.

    The interval variable can be optional. In this case, the solver can decide
    to make the interval absent, which is usually interpreted as the fact that
    the interval doesn't exist, the task/action was not executed, or the operation
    was not performed.  When the interval variable is absent, its start, end,
    and length are also absent.  A boolean expression that represents the presence
    of the interval variable can be accessed using
    :meth:`IntervalVar.presence` and :meth:`Model.presence`.

    Interval variables can be created using the function
    :meth:`Model.interval_var`.
    By default, interval variables are *present* (not optional).
    To create an optional interval, specify `optional: true` in the
    arguments of the function.

    ## Example

    In the following example we create three present interval variables `x`, `y` and `z`
    and we make sure that they don't overlap.  Then, we minimize the maximum of
    the end times of the three intervals (the makespan):

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        x = model.interval_var(length=10, name="x")
        y = model.interval_var(length=10, name="y")
        z = model.interval_var(length=10, name="z")
        model.no_overlap([x, y, z])
        model.minimize(model.max([x.end(), y.end(), z.end()]))
        result = model.solve()

    ## Example

    In the following example, there is a task *X* that could be performed by two
    different workers *A* and *B*.  The interval variable `X` represents the task.
    It is not optional because the task `X` is mandatory. Interval variable
    `XA` represents the task `X` when performed by worker *A* and
    similarly `XB` represents the task `X` when performed by worker *B*.
    Both `XA` and `XB` are optional because it is not known beforehand which
    worker will perform the task.  The constraint :meth:`IntervalVar.alternative` links
    `X`, `XA` and `XB` together and ensures that only one of `XA` and `XB` is present and that
    `X` and the present interval are equal.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        X = model.interval_var(length=10, name="X")
        XA = model.interval_var(name="XA", optional=True)
        XB = model.interval_var(name="XB", optional=True)
        model.alternative(X, [XA, XB])
        result = model.solve()

    Variables `XA` and `XB` can be used elsewhere in the model, e.g. to make sure
    that each worker is assigned to at most one task at a time:

    .. code-block:: python

        # Tasks of worker A don't overlap:
        model.no_overlap([... , XA, ...])
        # Tasks of worker B don't overlap:
        model.no_overlap([... , XB, ...])
    """

    def __init__(self, model: Model, props: _ElementProps, ref_id: int | None = None):
        self._model = model
        self._props = props
        self._arg = None
        if ref_id is not None:
            # Loading from JSON - use existing ref_id
            self._arg = {'ref': ref_id}
        else:
            self._force_ref()

    @staticmethod
    def _wrap(expr: IntervalVar) -> _ScalarArgument:
        """Internal: Convert a CumulExpr to an argument."""
        if isinstance(expr, IntervalVar): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected IntervalVar. Got {type(expr).__name__}")

    @staticmethod
    def _wrap_list(exprs: Iterable[IntervalVar]) -> list[_ScalarArgument]:
        return [IntervalVar._wrap(e) for e in exprs]

    def presence(self) -> BoolExpr:
        r"""
        Creates a Boolean expression which is true if the interval variable is present.

        :rtype: BoolExpr
        :returns: A Boolean expression that is true if the interval variable is present in the solution.

        ## Details

        The resulting expression is never *absent*: it is `True` if the interval variable is *present* and `False` if the interval variable is *absent*.

        This function is the same as :meth:`Model.presence`, see its documentation for more details.

        ## Example

        In the following example, interval variables `x` and `y` must have the same presence status.
        I.e. they must either be both *present* or both *absent*.

        .. code-block:: python

            model = cp.Model()
            x = model.interval_var(name="x", optional=True, length=10)
            y = model.interval_var(name="y", optional=True, length=10)
            model.enforce(x.presence() == y.presence())

        .. seealso::

            - :meth:`Model.presence` is the equivalent function on :class:`Model`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return BoolExpr(self._model, "intervalPresenceOf", out_params)

    def start(self) -> IntExpr:
        r"""
        Creates an integer expression for the start time of the interval variable.

        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval variable is absent, then the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(x.end() + 10 <= y.start())
            model.enforce(x.length() <= y.length())

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`Model.start` is equivalent function on :class:`Model`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return IntExpr(self._model, "startOf", out_params)

    def end(self) -> IntExpr:
        r"""
        Creates an integer expression for the end time of the interval variable.

        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval variable is absent, then the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(x.end() + 10 <= y.start())
            model.enforce(x.length() <= y.length())

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`Model.end` is equivalent function on :class:`Model`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return IntExpr(self._model, "endOf", out_params)

    def length(self) -> IntExpr:
        r"""
        Creates an integer expression for the duration (end - start) of the interval variable.

        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval variable is absent, then the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(x.end() + 10 <= y.start())
            model.enforce(x.length() <= y.length())

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`Model.length` is equivalent function on :class:`Model`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return IntExpr(self._model, "lengthOf", out_params)

    def _alternative_cost(self, options: Iterable[IntervalVar], weights: Iterable[int]) -> IntExpr:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap_list(options), _wrap_int_list(weights)]
        return IntExpr(self._model, "intAlternativeCost", out_params)

    def end_before_end(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.end() + delay <= successor.end()

        In other words, end of `predecessor` plus `delay` must be less than or equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.end_before_end` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "endBeforeEnd", out_params)

    def end_before_start(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.end() + delay <= successor.start()

        In other words, end of `predecessor` plus `delay` must be less than or equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.end_before_start` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "endBeforeStart", out_params)

    def start_before_end(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.start() + delay <= successor.end()

        In other words, start of `predecessor` plus `delay` must be less than or equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.start_before_end` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "startBeforeEnd", out_params)

    def start_before_start(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.start() + delay <= successor.start()

        In other words, start of `predecessor` plus `delay` must be less than or equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.start_before_start` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "startBeforeStart", out_params)

    def end_at_end(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.end() + delay == successor.end()

        In other words, end of `predecessor` plus `delay` must be equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.end_at_end` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "endAtEnd", out_params)

    def end_at_start(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.end() + delay == successor.start()

        In other words, end of `predecessor` plus `delay` must be equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.end_at_start` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "endAtStart", out_params)

    def start_at_end(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.start() + delay == successor.end()

        In other words, start of `predecessor` plus `delay` must be equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.start_at_end` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "startAtEnd", out_params)

    def start_at_start(self, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Assuming that the current interval is `predecessor`, the constraint is the same as:

        .. code-block:: python

            predecessor.start() + delay == successor.start()

        In other words, start of `predecessor` plus `delay` must be equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`Model.start_at_start` is equivalent function on :class:`Model`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self._model, "startAtStart", out_params)

    def alternative(self, options: Iterable[IntervalVar]) -> Constraint:
        r"""
        Creates alternative constraints for the interval variable and provided `options`.

        :param options: The interval variables to choose from.
        :type options: Iterable[IntervalVar]
        :rtype: Constraint
        :returns: The alternative constraint.

        ## Details

        The alternative constraint requires that exactly one of the `options` intervals
        is present when `self` is present. The selected option must have the same
        start, end, and length as `self`. If `self` is absent, all options must be absent.

        This is useful for modeling choices, such as assigning a task to one of several
        machines, where each option represents the task executed on a different machine.

        This constraint is equivalent to :meth:`Model.alternative` with `self` as the main interval.
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap_list(options)]
        return Constraint(self._model, "alternative", out_params)

    def span(self, covered: Iterable[IntervalVar]) -> Constraint:
        r"""
        Constrains the interval variable to span (cover) a set of other interval variables.

        :param covered: The set of interval variables to cover.
        :type covered: Iterable[IntervalVar]
        :rtype: Constraint
        :returns: The span constraint.

        ## Details

        The span constraint ensures that `self` exactly covers all present intervals
        in `covered`. Specifically, `self` starts at the minimum start time and ends
        at the maximum end time of the present covered intervals. If all covered
        intervals are absent, `self` must also be absent.

        This is useful for modeling composite tasks or projects where a parent interval
        represents the overall duration of multiple sub-tasks.

        This constraint is equivalent to :meth:`Model.span` with `self` as the spanning interval.
        """
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap_list(covered)]
        return Constraint(self._model, "span", out_params)

    def position(self, sequence: SequenceVar) -> IntExpr:
        r"""
        Creates an expression equal to the position of the interval on the sequence.

        :param sequence: The sequence variable.
        :type sequence: SequenceVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        Returns an integer expression representing the 0-based position of this interval
        in the given sequence. The position reflects the order in which intervals appear
        after applying the :meth:`SequenceVar.no_overlap` constraint.

        If this interval is absent, the position expression is also absent.

        This method is equivalent to :meth:`Model.position` with `self` as the interval.
        """
        out_params: list[_Argument] = [self._as_arg(), SequenceVar._wrap(sequence)]
        return IntExpr(self._model, "position", out_params)

    def pulse(self, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) pulse for the interval variable and specified height.

        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        **Limitation:** The `height` must be non-negative. Pulses with negative height are not supported.

        This function is the same as :meth:`Model.pulse`.

        ## Example

        .. code-block:: python

            task = model.interval_var(name="task", length=10)
            pulse = task.pulse(5)

        .. seealso::

            - :meth:`Model.pulse` for detailed documentation and examples.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(height)]
        return CumulExpr(self._model, "pulse", out_params)

    def step_at_start(self, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) that changes value at start of the interval variable by the given height.

        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Creates cumulative function (expression) that changes value at start of the interval variable by the given height.

        This function is the same as :meth:`Model.step_at_start`.

        ## Example

        .. code-block:: python

            task = model.interval_var(name="task", length=10)
            step = task.step_at_start(5)

        .. seealso::

            - :meth:`Model.step_at_start` for detailed documentation.
            - :meth:`IntervalVar.step_at_end` for the opposite function.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(height)]
        return CumulExpr(self._model, "stepAtStart", out_params)

    def step_at_end(self, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) that changes value at end of the interval variable by the given height.

        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Creates cumulative function (expression) that changes value at end of the interval variable by the given height.

        This function is the same as :meth:`Model.step_at_end`.

        ## Example

        .. code-block:: python

            task = model.interval_var(name="task", length=10)
            step = task.step_at_end(5)

        .. seealso::

            - :meth:`Model.step_at_end` for detailed documentation.
            - :meth:`IntervalVar.step_at_start` for the opposite function.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(height)]
        return CumulExpr(self._model, "stepAtEnd", out_params)

    def _precedence_energy_before(self, others: Iterable[IntervalVar], heights: Iterable[int], capacity: int) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap_list(others), _wrap_int_list(heights), _wrap_int(capacity)]
        return Constraint(self._model, "precedenceEnergyBefore", out_params)

    def _precedence_energy_after(self, others: Iterable[IntervalVar], heights: Iterable[int], capacity: int) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap_list(others), _wrap_int_list(heights), _wrap_int(capacity)]
        return Constraint(self._model, "precedenceEnergyAfter", out_params)

    def forbid_extent(self, func: IntStepFunction) -> Constraint:
        r"""
        This function prevents the specified interval variable from overlapping with segments of the step function where the value is zero.

        :param func: The step function.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the extent (entire interval).

        ## Details

        This function prevents the specified interval variable from overlapping with segments of the step function where the value is zero. I.e., if :math:`[s, e)` is a segment of the step function where the value is zero, then the interval variable either ends before :math:`s` (:math:`\mathtt{interval.end()} \le s`) or starts after :math:`e` (:math:`e \le \mathtt{interval.start()}`).

        ## Example

        A production task that cannot overlap with scheduled maintenance windows:

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # A 3-hour production run
            production = model.interval_var(length=3, name="production")

            # Machine availability: 1 = available, 0 = under maintenance
            availability = model.step_function([
                (0, 1),   # Initially available
                (8, 0),   # 8h: maintenance starts
                (10, 1),  # 10h: maintenance ends
            ])

            # Production cannot overlap periods where availability is 0
            production.forbid_extent(availability)
            model.minimize(production.end())

            result = model.solve()
            # Production runs [0, 3) - finishes before maintenance window

        .. seealso::

            - :meth:`Model.forbid_extent` for the equivalent function on :class:`Model`.
            - :meth:`Model.forbid_start`, :meth:`Model.forbid_end` for similar functions that constrain the start/end of an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [self._as_arg(), IntStepFunction._wrap(func)]
        return Constraint(self._model, "forbidExtent", out_params)

    def forbid_start(self, func: IntStepFunction) -> Constraint:
        r"""
        Constrains the start of an interval variable to not coincide with zero segments of a step function.

        :param func: The step function whose zero segments define forbidden start times.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the start point.

        ## Details

        This function is equivalent to:

        .. code-block:: python

            model.enforce(func.eval(interval.start()) != 0)

        I.e., the function value at the start of the interval variable cannot be zero.

        ## Example

        A factory task that can only start during work hours (excluding breaks):

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # A 2-hour task on a machine
            task = model.interval_var(length=2, name="task")

            # Allowed start times: 1 = allowed, 0 = forbidden
            # Morning shift 6-14h, but break at 10-11h when no new task can start
            allowed_starts = model.step_function([
                (0, 0),   # Before 6h: forbidden
                (6, 1),   # 6h: shift starts, allowed
                (10, 0),  # 10h: break, forbidden
                (11, 1),  # 11h: break ends, allowed
                (14, 0),  # 14h: shift ends, forbidden
            ])

            # Task cannot start when allowed_starts is 0
            task.forbid_start(allowed_starts)
            model.minimize(task.start())

            result = model.solve()
            # Task starts at 6 (earliest allowed start time)

        .. seealso::

            - :meth:`Model.forbid_start` for the equivalent function on :class:`Model`.
            - :meth:`Model.forbid_end` for similar function that constrains end an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [self._as_arg(), IntStepFunction._wrap(func)]
        return Constraint(self._model, "forbidStart", out_params)

    def forbid_end(self, func: IntStepFunction) -> Constraint:
        r"""
        Constrains the end of an interval variable to not coincide with zero segments of a step function.

        :param func: The step function whose zero segments define forbidden end times.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the end point.

        ## Details

        This function is equivalent to:

        .. code-block:: python

            model.enforce(func.eval(interval.end()) != 0)

        I.e., the function value at the end of the interval variable cannot be zero.

        ## Example

        A delivery task that must complete during business hours (not during lunch break):

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # A 1-hour delivery task
            delivery = model.interval_var(length=1, name="delivery")

            # Allowed end times: 1 = allowed, 0 = forbidden
            # Business hours 9-17h, but deliveries cannot end during lunch 12-13h
            allowed_ends = model.step_function([
                (0, 0),   # Before 9h: forbidden
                (9, 1),   # 9h: business opens, allowed
                (12, 0),  # 12h: lunch break, forbidden
                (13, 1),  # 13h: lunch ends, allowed
                (17, 0),  # 17h: business closes, forbidden
            ])

            # Delivery cannot end when allowed_ends is 0
            delivery.forbid_end(allowed_ends)
            model.minimize(delivery.end())

            result = model.solve()
            # Delivery ends at 9 (starts at 8, ends at earliest allowed time)

        .. seealso::

            - :meth:`Model.forbid_end` for the equivalent function on :class:`Model`.
            - :meth:`Model.forbid_start` for similar function that constrains start an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [self._as_arg(), IntStepFunction._wrap(func)]
        return Constraint(self._model, "forbidEnd", out_params)

    def _disjunctive_is_before(self, y: IntervalVar) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(y)]
        return BoolExpr(self._model, "disjunctiveIsBefore", out_params)

    def _related(self, y: IntervalVar) -> _Directive:
        out_params: list[_Argument] = [self._as_arg(), IntervalVar._wrap(y)]
        return _Directive(self._model, "related", out_params)



    def _is_absent(self) -> bool:
        """Internal helper to check if interval is absent."""
        return self._props.get('status') == _PresenceStatus.Absent

    # Presence property
    @property
    def optional(self) -> bool | None:
        r"""
        The presence status of the interval variable.

        Gets or sets the presence status of the interval variable using a tri-state value:

        - `True` / `True`: The interval is *optional* - the solver decides whether it is present or absent in the solution.
        - `False` / `False`: The interval is *present* - it must be scheduled in the solution.
        - `None` / `None`: The interval is *absent* - it will be omitted from the solution (and everything that depends on it).

        **Note:** This property reflects the presence status in the model
        (before the solve), not in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task1 = model.interval_var(length=10, name="task1")
            task2 = model.interval_var(length=10, optional=True, name="task2")

            print(task1.optional)  # False (present by default)
            print(task2.optional)  # True (optional)

            # Make task1 optional
            task1.optional = True
            print(task1.optional)  # True

            # Make task2 absent
            task2.optional = None
            print(task2.optional)  # None

        .. seealso::

            - :attr:`IntervalVar.start_min`, :attr:`IntervalVar.end_min`, :attr:`IntervalVar.length_min`.
        """
        status = self._props.get('status')
        if status == _PresenceStatus.Absent:
            return None
        return status == _PresenceStatus.Optional

    @optional.setter
    def optional(self, value: bool | None) -> None:
        if value is None:
            self._props['status'] = _PresenceStatus.Absent
        elif value:
            self._props['status'] = _PresenceStatus.Optional
        else:
            self._props.pop('status', None)

    # Start properties
    @property
    def start_min(self) -> int | None:
        r"""
        The minimum start time of the interval variable.

        Gets or sets the minimum start time of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntervalMin` to :const:`IntervalMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            print(task.start_min)  # 0 (default)

            task.start_min = 5
            print(task.start_min)  # 5

        .. seealso::

            - :attr:`IntervalVar.start_max`, :attr:`IntervalVar.end_min`, :attr:`IntervalVar.length_min`.
        """
        if self._is_absent():
            return None
        return self._props.get('startMin', 0)

    @start_min.setter
    def start_min(self, value: int) -> None:
        self._props['startMin'] = int(value)

    @property
    def start_max(self) -> int | None:
        r"""
        The maximum start time of the interval variable.

        Gets or sets the maximum start time of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntervalMin` to :const:`IntervalMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            task.start_max = 100
            print(task.start_max)  # 100

        .. seealso::

            - :attr:`IntervalVar.start_min`, :attr:`IntervalVar.end_max`, :attr:`IntervalVar.length_max`.
        """
        if self._is_absent():
            return None
        return self._props.get('startMax', IntervalMax)

    @start_max.setter
    def start_max(self, value: int) -> None:
        self._props['startMax'] = int(value)

    # End properties
    @property
    def end_min(self) -> int | None:
        r"""
        The minimum end time of the interval variable.

        Gets or sets the minimum end time of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntervalMin` to :const:`IntervalMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            print(task.end_min)  # 10 (start_min + length)

            task.end_min = 20
            print(task.end_min)  # 20

        .. seealso::

            - :attr:`IntervalVar.end_max`, :attr:`IntervalVar.start_min`, :attr:`IntervalVar.length_min`.
        """
        if self._is_absent():
            return None
        return self._props.get('endMin', 0)

    @end_min.setter
    def end_min(self, value: int) -> None:
        self._props['endMin'] = int(value)

    @property
    def end_max(self) -> int | None:
        r"""
        The maximum end time of the interval variable.

        Gets or sets the maximum end time of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntervalMin` to :const:`IntervalMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            task.end_max = 100
            print(task.end_max)  # 100

        .. seealso::

            - :attr:`IntervalVar.end_min`, :attr:`IntervalVar.start_max`, :attr:`IntervalVar.length_max`.
        """
        if self._is_absent():
            return None
        return self._props.get('endMax', IntervalMax)

    @end_max.setter
    def end_max(self, value: int) -> None:
        self._props['endMax'] = int(value)

    # Length properties
    @property
    def length_min(self) -> int | None:
        r"""
        The minimum length of the interval variable.

        Gets or sets the minimum length of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range 0 to :const:`LengthMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            print(task.length_min)  # 10

            task.length_min = 5
            print(task.length_min)  # 5

        .. seealso::

            - :attr:`IntervalVar.length_max`, :attr:`IntervalVar.start_min`, :attr:`IntervalVar.end_min`.
        """
        if self._is_absent():
            return None
        return self._props.get('lengthMin', 0)

    @length_min.setter
    def length_min(self, value: int) -> None:
        self._props['lengthMin'] = int(value)

    @property
    def length_max(self) -> int | None:
        r"""
        The maximum length of the interval variable.

        Gets or sets the maximum length of the interval variable.

        The initial value is set during construction by :meth:`Model.interval_var`.
        If the interval is absent, the getter returns `None`.

        **Note:** This property reflects the interval's domain in the model
        (before the solve), not in the solution.

        The value must be in the range 0 to :const:`LengthMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task = model.interval_var(length=10, name="task")

            print(task.length_max)  # 10

            task.length_max = 20
            print(task.length_max)  # 20

        .. seealso::

            - :attr:`IntervalVar.length_min`, :attr:`IntervalVar.start_max`, :attr:`IntervalVar.end_max`.
        """
        if self._is_absent():
            return None
        return self._props.get('lengthMax', LengthMax)

    @length_max.setter
    def length_max(self, value: int) -> None:
        self._props['lengthMax'] = int(value)
