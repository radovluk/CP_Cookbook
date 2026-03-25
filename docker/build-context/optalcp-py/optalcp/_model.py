"""
Core model classes for OptalCP Python API.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, overload

from ._constants import _PresenceStatus
from ._expressions import (
    BoolExpr,
    Constraint,
    CumulExpr,
    IntExpr,
    Objective,
    _Argument,
    _Directive,
    _ElementProps,
    _SearchDecision,
    _wrap_bool,
    _wrap_int,
    _wrap_int_list,
)
from ._int_bool_var import BoolVar, IntVar
from ._parameters import Parameters
from ._scheduling import IntervalVar, IntStepFunction, SequenceVar

if TYPE_CHECKING:
    from ._result import SolveResult
    from ._solution import Solution


class Model:
    r"""
    *Model* captures the problem to be solved. It contains variables,
    constraints and objective function.

    To create an optimization model, you must first create a *Model* object.
    Then you can use the methods of the *Model* to create variables (e.g. :meth:`Model.interval_var`), the objective function (:meth:`Model.minimize` or :meth:`Model.maximize`)
    and constraints (e.g. :meth:`Model.no_overlap`).
    Note that a boolean expression becomes a constraint only by passing it to
    :meth:`Model.enforce`; otherwise, it is not enforced.

    To solve a model, pass it to function :meth:`Model.solve` or to :class:`Solver`
    class.

    ## Available modeling elements

    ### Variables

    Interval variables can be created by function :meth:`Model.interval_var`, integer variables by function :meth:`Model.int_var`.

    ### Basic integer expressions

    * :meth:`Model.start`: start of an interval variable (optional integer expression).
    * :meth:`Model.end`:   end of an interval variable (optional integer expression).
    * :meth:`Model.length`: length of an interval variable (optional integer expression).
    * :meth:`Model.guard`: replaces *absent* value by a constant.

    ### Integer arithmetics

    Use standard arithmetic operators on integer expressions: `+`, `-`, unary `-`, `*`, `//`.

    * :meth:`Model.abs`:   absolute value.
    * :meth:`Model.min2`:  minimum of two integer expressions.
    * :meth:`Model.min`:   minimum of an array of integer expressions.
    * :meth:`Model.max2`:  maximum of two integer expressions.
    * :meth:`Model.max`:   maximum of an array of integer expressions.
    * :meth:`Model.sum`:   sum of an array of integer expressions.

    ### Comparison operators for integer expressions

    Use standard comparison operators on integer expressions: `<`, `<=`, `==`, `!=`, `>`, `>=`.

    * :meth:`Model.identity`: constraints two integer expressions to be equal, including the presence status.

    ### Boolean operators

    * :meth:`Model.not_`: negation.
    * :meth:`Model.and_`: conjunction.
    * :meth:`Model.or_`:  disjunction.
    * :meth:`Model.implies`: implication.

    ### Functions returning :class:`BoolExpr`

    * :meth:`Model.presence`: whether the argument is *present* or *absent*.
    * :meth:`Model.in_range`: whether an integer expression is within the given range

    ### Basic constraints on interval variables

    * :meth:`Model.alternative`: an alternative between multiple interval variables.
    * :meth:`Model.span`: span (cover) of interval variables.
    * :meth:`Model.end_before_end`, :meth:`Model.end_before_start`, :meth:`Model.start_before_end`, :meth:`Model.start_before_start`,
      :meth:`Model.end_at_start`, :meth:`Model.start_at_end`: precedence constraints.

    ### Disjunction (noOverlap)

    * :meth:`Model.sequence_var`: sequence variable over a set of interval variables.
    * :meth:`Model.no_overlap`: constraints a set of interval variables to not overlap (possibly with transition times).
    * :meth:`Model.position`: returns the position of an interval variable in a sequence.

    ### Basic cumulative expressions

    * :meth:`Model.pulse`: changes value during the interval variable.
    * :meth:`Model.step_at_start`: changes value at the start of the interval variable.
    * :meth:`Model.step_at_end`: changes value at the end of the interval variable.
    * :meth:`Model.step_at`: changes value at a given time.

    ### Combining cumulative expressions

    Use standard operators on cumulative expressions: `+`, `-`, unary `-`, and :meth:`Model.sum`.

    ### Constraints on cumulative expressions

    Use comparison operators on cumulative expressions: `<=`, `>=`.

    ### Objective

    * :meth:`Model.minimize`: minimize an integer expression.
    * :meth:`Model.maximize`: maximize an integer expression.

    ## Example

    Our goal is to schedule a set of tasks such that it is finished as soon as
    possible (i.e., the makespan is minimized).  Each task has a fixed duration, and
    cannot be interrupted.  Moreover, each task needs a certain number of
    workers to be executed, and the total number of workers is limited.
    The input data are generated randomly.

    .. code-block:: python

        import optalcp as cp
        import random

        # Constants for random problem generation:
        nb_tasks = 100
        nb_workers = 5
        max_duration = 100

        # Start by creating the model:
        model = cp.Model()

        # For each task we will have an interval variable and a cumulative expression:
        tasks = []
        worker_usage = []

        # Loop over the tasks:
        for i in range(nb_tasks):
            # Generate random task length:
            task_length = 1 + random.randint(0, max_duration - 2)
            # Create the interval variable for the task:
            task = model.interval_var(name=f"Task{i + 1}", length=task_length)
            # And store it in the array:
            tasks.append(task)
            # Generate random number of workers needed for the task:
            workers_needed = 1 + random.randint(0, nb_workers - 2)
            # Create the pulse that increases the number of workers used during the task:
            worker_usage.append(task.pulse(workers_needed))

        # Limit the sum of the pulses to the number of workers available:
        model.enforce(model.sum(worker_usage) <= nb_workers)
        # From an array of tasks, create an array of their ends:
        ends = [t.end() for t in tasks]
        # And minimize the maximum of the ends:
        model.minimize(model.max(ends))

        # Solve the model with the provided parameters:
        result = model.solve({
            'timeLimit': 3,  # Stop after 3 seconds
            'nbWorkers': 4,  # Use for CPU threads
        })

        if result.nb_solutions == 0:
            print("No solution found.")
        else:
            solution = result.solution
            # Note that in the preview version of the solver, the variable values in
            # the solution are masked, i.e. they are all *absent* (`None` in Python).
            # Objective value is not masked though.
            print(f"Solution found with makespan {solution.get_objective()}")
            for task in tasks:
                start = solution.get_start(task)
                if start is not None:
                    print(f"Task {task.name} starts at {start}")
                else:
                    print(f"Task {task.name} is absent (not scheduled).")

    .. seealso::

        - :meth:`Model.solve`.
        - :class:`Solution`.
        - :class:`Solver`.
    """

    def __init__(self, *, name: str | None = None):
        r"""
        Creates an empty optimization model.

        :param name: Optional name for the model
        :type name: str | None

        ## Details

        Creates an empty model with no variables, constraints, or objective.

        The optional `name` parameter can be used to identify the model in logs,
        debugging output, and benchmarking reports. When not specified, the model
        remains unnamed.

        After creating a model, use its methods to define:

        - **Variables**: :meth:`Model.interval_var`, :meth:`Model.int_var`, :meth:`Model.bool_var`
        - **Constraints**: :meth:`Model.no_overlap`, :meth:`Model.end_before_start`, :meth:`Model.enforce`, etc.
        - **Objective**: :meth:`Model.minimize` or :meth:`Model.maximize`

        .. code-block:: python

            import optalcp as cp

            # Create an unnamed model
            model = cp.Model()

            # Create a named model (useful for debugging)
            model = cp.Model(name="JobShop")

            # Add variables and constraints
            task = model.interval_var(length=10, name="task")
            model.minimize(task.end())

            # Solve
            result = model.solve()

        .. seealso::

            - :class:`Model` for available modeling methods.
            - :meth:`Model.solve` to solve the model.
        """
        self._name = name
        self._model: list[_Argument] = []  # Top-level constraints
        self._refs: list[_ElementProps] = []  # Nodes referenced by ID
        self._objective: _ElementProps | None = None
        self._interval_vars: list[IntervalVar] = []
        self._int_vars: list[IntVar] = []
        self._bool_vars: list[BoolVar] = []

    @property
    def name(self) -> str | None:
        r"""
        The name of the model.

        The name is optional and primarily useful for distinguishing between different
        models during debugging and benchmarking. When set, it helps identify the model
        in logs and benchmark results.

        The name can be set either in the constructor or by assigning to this property.
        Assigning overwrites any name that was previously set.

        .. code-block:: python

            import optalcp as cp

            # Set name in constructor
            model = cp.Model(name="MySchedulingProblem")
            print(model.name)  # "MySchedulingProblem"

            # Or set name later
            model = cp.Model()
            model.name = "JobShop"
            print(model.name)  # "JobShop"

            # Clear the name
            model.name = None
        """
        return self._name

    @name.setter
    def name(self, value: str | None) -> None:
        if value is not None and not isinstance(value, str):
            raise TypeError(f"Model name must be str or None, got {type(value).__name__}")
        self._name = value

    def get_interval_vars(self) -> list[IntervalVar]:
        r"""
        Returns a list of all interval variables in the model.

        :rtype: list[IntervalVar]
        :returns: A list of all interval variables in the model

        ## Details

        Returns a copy of the list containing all interval variables that have been
        created in this model using :meth:`Model.interval_var`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            task1 = model.interval_var(length=10, name="task1")
            task2 = model.interval_var(length=20, name="task2")

            intervals = model.get_interval_vars()
            print(len(intervals))  # 2
            for iv in intervals:
                print(iv.name)  # "task1", "task2"

        .. seealso::

            - :meth:`Model.get_int_vars`, :meth:`Model.get_bool_vars`.
        """
        return list(self._interval_vars)

    def get_int_vars(self) -> list[IntVar]:
        r"""
        Returns a list of all integer variables in the model.

        :rtype: list[IntVar]
        :returns: A list of all integer variables in the model

        ## Details

        Returns a copy of the list containing all integer variables that have been
        created in this model using :meth:`Model.int_var`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.int_var(min=0, max=10, name="x")
            y = model.int_var(min=0, max=100, name="y")

            int_vars = model.get_int_vars()
            print(len(int_vars))  # 2
            for iv in int_vars:
                print(iv.name)  # "x", "y"

        .. seealso::

            - :meth:`Model.get_interval_vars`, :meth:`Model.get_bool_vars`.
        """
        return list(self._int_vars)

    def get_bool_vars(self) -> list[BoolVar]:
        r"""
        Returns a list of all boolean variables in the model.

        :rtype: list[BoolVar]
        :returns: A list of all boolean variables in the model

        ## Details

        Returns a copy of the list containing all boolean variables that have been
        created in this model using :meth:`Model.bool_var`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            use_machine_a = model.bool_var(name="use_machine_a")
            use_machine_b = model.bool_var(name="use_machine_b")

            bool_vars = model.get_bool_vars()
            print(len(bool_vars))  # 2
            for bv in bool_vars:
                print(bv.name)  # "use_machine_a", "use_machine_b"

        .. seealso::

            - :meth:`Model.get_interval_vars`, :meth:`Model.get_int_vars`.
        """
        return list(self._bool_vars)

    def interval_var(self,
                     start: int | tuple[int | None, int | None] | None = None,
                     end: int | tuple[int | None, int | None] | None = None,
                     length: int | tuple[int | None, int | None] | None = None,
                     optional: bool = False,
                     name: str | None = None) -> IntervalVar:
        r"""
        Creates a new interval variable and adds it to the model.

        :param start: Fixed start time or range as (min, max). Use None for either bound to keep the default. For example, `(None, 100)` sets only startMax.
        :type start: int | tuple[int | None, int | None] | None
        :param end: Fixed end time or range as (min, max). Use None for either bound to keep the default. For example, `(None, 100)` sets only endMax.
        :type end: int | tuple[int | None, int | None] | None
        :param length: Fixed length or range as (min, max). Use None for either bound to keep the default. For example, `(5, None)` sets only lengthMin.
        :type length: int | tuple[int | None, int | None] | None
        :param optional: If True, the interval can be absent in a solution. The default is False.
        :type optional: bool
        :param name: Optional name for debugging purposes.
        :type name: str | None
        :rtype: IntervalVar
        :returns: The created interval variable.

        ## Details

        An interval variable represents an unknown interval (a task, operation,
        action) that the solver assigns a value in such a way as to satisfy all
        constraints.  An interval variable has a start, end, and length. In a
        solution, *start <= end* and *length = end - start*.

        The interval variable can be optional. In this case, its value in a solution
        could be *absent*, meaning that the task/operation is not performed.

        Parameters `start`, `end`, and `length` can be either an integer or a tuple
        of two integers.  If an integer is given, it represents a fixed value.
        If a tuple is given, it represents a range of possible values (min, max).
        Either element of the tuple can be `None` to use the default bound.
        The default range for start, end and length is `0` to :const:`IntervalMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # Create an interval variable with a fixed start but unknown length:
            x = model.interval_var(start=0, length=(10, 20), name="x")

            # Create an interval variable with start and end ranges:
            y = model.interval_var(start=(0, 5), end=(10, 15), name="y")

            # Create an optional interval variable with length range 5..10:
            z = model.interval_var(length=(5, 10), optional=True, name="z")

            # Set only startMax (startMin remains the default):
            w = model.interval_var(start=(None, 100), name="w")

        .. seealso::

            - :class:`IntervalVar`.
        """
        props: _ElementProps = {
            'func': 'intervalVar',
            'args': []
        }

        if name:
            props['name'] = name

        if optional:
            props['status'] = _PresenceStatus.Optional

        if start is not None:
            if isinstance(start, int):
                props['startMin'] = start
                props['startMax'] = start
            else:
                if start[0] is not None:
                    props['startMin'] = start[0]
                if start[1] is not None:
                    props['startMax'] = start[1]

        if end is not None:
            if isinstance(end, int):
                props['endMin'] = end
                props['endMax'] = end
            else:
                if end[0] is not None:
                    props['endMin'] = end[0]
                if end[1] is not None:
                    props['endMax'] = end[1]

        if length is not None:
            if isinstance(length, int):
                props['lengthMin'] = length
                props['lengthMax'] = length
            else:
                if length[0] is not None:
                    props['lengthMin'] = length[0]
                if length[1] is not None:
                    props['lengthMax'] = length[1]

        var = IntervalVar(self, props)
        self._interval_vars.append(var)
        return var

    def int_var(self,
                min: int | None = None,
                max: int | None = None,
                optional: bool = False,
                name: str | None = None) -> IntVar:
        r"""
        Creates a new integer variable and adds it to the model.

        :param min: Minimum value for the variable. Default is 0.
        :type min: int | None
        :param max: Maximum value for the variable. Default is IntVarMax.
        :type max: int | None
        :param optional: If True, the variable can be absent in a solution. The default is False.
        :type optional: bool
        :param name: Optional name for debugging purposes.
        :type name: str | None
        :rtype: IntVar
        :returns: The created integer variable.

        ## Details

        An integer variable represents an unknown value the solver must find.
        The variable can be optional.
        In this case, its value in a solution could be *absent*, meaning that the solution does not use the variable at all.

        The default domain is `0` to :const:`IntVarMax`.
        If `min` or `max` is not specified (or None), the default value is used.

        ## Example

        .. code-block:: python

            import optalcp as cp
            model = cp.Model()

            # Create an integer variable with possible values 1..10:
            x = model.int_var(min=1, max=10, name="x")

            # Create an optional integer variable with possible values 5..IntVarMax:
            y = model.int_var(min=5, optional=True, name="y")

            # Create a non-negative integer variable:
            z = model.int_var(max=100, name="z")
        """
        props: _ElementProps = {
            'func': 'intVar',
            'args': [],
        }

        if min is not None:
            props['min'] = min
        if max is not None:
            props['max'] = max
        if optional:
            props['status'] = _PresenceStatus.Optional
        if name:
            props['name'] = name

        var = IntVar(self, props)
        self._int_vars.append(var)
        return var

    def bool_var(self, optional: bool = False, name: str | None = None) -> BoolVar:
        r"""
        Creates a new boolean variable and adds it to the model.

        :param optional: If `True`, the variable can be absent in a solution. The default is `False`.
        :type optional: bool
        :param name: Optional name for the variable (useful for debugging)
        :type name: str | None
        :rtype: BoolVar
        :returns: The created boolean variable.

        ## Details

        A boolean variable represents an unknown truth value (`True` or `False`) that the
        solver must find. Boolean variables are useful for modeling decisions, choices,
        or logical conditions in your problem.

        By default, a boolean variable must be assigned a value (`True` or `False`) in every
        solution. When `optional=True`, the variable can also be *absent*, meaning the
        solution does not use the variable at all. This is useful when the variable
        represents a decision that may not apply in all scenarios.

        Boolean variables support logical operators:

        - `~x` for logical NOT
        - `x | y` for logical OR
        - `x & y` for logical AND

        ## Example

        Create boolean variables to model decisions:

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            use_machine_a = model.bool_var(name="use_machine_a")
            use_machine_b = model.bool_var(name="use_machine_b")

            # Constraint: must use at least one machine
            model.enforce(use_machine_a | use_machine_b)

            # Constraint: cannot use both machines
            model.enforce(~(use_machine_a & use_machine_b))

        .. seealso::

            - :meth:`Model.interval_var` for the primary variable type for scheduling problems.
            - :meth:`Model.int_var` for numeric decisions.
        """
        props: _ElementProps = {
            'func': 'boolVar',
            'args': [],
            'min': False,
            'max': True
        }

        if name:
            props['name'] = name
        if optional:
            props['status'] = _PresenceStatus.Optional

        var = BoolVar(self, props)
        self._bool_vars.append(var)
        return var

    def sequence_var(self,
                     intervals: Iterable[IntervalVar],
                     types: Iterable[int] | None = None,
                     name: str | None = None) -> SequenceVar:
        r"""
        Creates a sequence variable from the provided set of interval variables.

        :param intervals: Interval variables that will form the sequence in the solution
        :type intervals: Iterable[IntervalVar]
        :param types: Types of the intervals, used in particular for transition times
        :type types: Iterable[int] | None
        :param name: Name assigned to the sequence variable
        :type name: str | None
        :rtype: SequenceVar
        :returns: The created sequence variable

        ## Details

        Sequence variable is used together with :meth:`SequenceVar.no_overlap`
        constraint to model a set of intervals that cannot overlap and so they form
        a sequence in the solution. Sequence variable allows us to constrain the sequence further.
        For example, by specifying sequence-dependent minimum
        transition times.

        Types can be used to mark intervals with similar properties. In
        particular, they behave similarly in terms of transition times.
        Interval variable `intervals[0]` will have type `type[0]`, `intervals[1]`
        will have type `type[1]` and so on.

        If `types` are not specified then `intervals[0]` will have type 0,
        `intervals[1]` will have type 1, and so on.

        The length of the array `types` must be the same as the length of the array
        `intervals`. Types should be integer numbers in the range `0` to `n-1` where `n` is the
        number of types.

        .. seealso::

            - :meth:`SequenceVar.no_overlap` for an example of sequenceVar usage with transition times.
            - :class:`SequenceVar`.
            - :meth:`Model.no_overlap`.
        """
        # Convert interval variables to arguments
        interval_args = IntervalVar._wrap_list(intervals)

        # Build the arguments list
        out_params: list[_Argument] = [interval_args]
        if types is not None:
            types_args = _wrap_int_list(types)
            if len(types_args) != len(interval_args):
                raise ValueError(f"Length of types ({len(types_args)}) must equal length of intervals ({len(interval_args)})")
            out_params.append(types_args)

        result = SequenceVar(self, "sequenceVar", out_params)
        if name:
            result.name = name
        self._model.append(result._as_arg())
        return result

    def no_overlap(self,
                   intervals: Iterable[IntervalVar] | SequenceVar,
                   transitions: Iterable[Iterable[int]] | None = None) -> Constraint:
        r"""
        Constrain a set of interval variables not to overlap.

        :param intervals: An array of interval variables or a sequence variable to constrain
        :type intervals: Iterable[IntervalVar] | SequenceVar
        :param transitions: A 2D square array of minimum transition times between the intervals
        :type transitions: Iterable[Iterable[int]] | None
        :rtype: Constraint
        :returns: The no-overlap constraint.

        ## Details

        This function constrains a set of interval variables so they do not overlap.
        That is, for each pair of interval variables `x` and `y`, one of the
        following must hold:

        1. Interval variable `x` or `y` is *absent*. In this case, the absent interval
        is not scheduled (the task is not performed), so it cannot overlap
        with any other interval. Only *optional* interval variables can be *absent*.
        2. Interval variable `x` is before `y`, that is, `x.end()` is less than or
        equal to `y.start()`.
        3. The interval variable `y` is before `x`. That is, `y.end()` is less than or
        equal to `x.start()`.

        The function can also take a square array `transitions` of minimum
        transition times between the intervals. The transition time is the time
        that must elapse between the end of the first interval and the start of the
        second interval. The transition time cannot be negative. When transition
        times are specified, the above conditions 2 and 3 are modified as follows:

        2. `x.end() + transitions[i][j]` is less than or equal to `y.start()`.
        3. `y.end() + transitions[j][i]` is less than or equal to `x.start()`.

        Where `i` and `j` are types of `x` and `y`. When an array of intervals is passed,
        the type of each interval is its index in the array.

        Note that minimum transition times are enforced between all pairs of
        intervals, not only between direct neighbors.

        Instead of an array of interval variables, a :class:`SequenceVar` can be passed.
        See :meth:`Model.sequence_var` for how to assign types to intervals in a sequence.

        ## Example

        The following example does not use transition times. For example with
        transition times see :meth:`SequenceVar.no_overlap`.

        Let's consider a set of tasks that must be performed by a single machine.
        The machine can handle only one task at a time. Each task is
        characterized by its length and a deadline. The goal is to schedule the
        tasks on the machine so that the number of missed deadlines is minimized.

        .. code-block:: python

            tasks = [
                {"length": 10, "deadline": 70},
                {"length": 20, "deadline": 50},
                {"length": 15, "deadline": 50},
                {"length": 30, "deadline": 100},
                {"length": 20, "deadline": 120},
                {"length": 25, "deadline": 90},
                {"length": 30, "deadline": 80},
                {"length": 10, "deadline": 40},
                {"length": 20, "deadline": 60},
                {"length": 25, "deadline": 150},
            ]

            model = cp.Model()

            # An interval variable for each task:
            task_vars = []
            # A boolean expression that is true if the task is late:
            is_late = []

            for i, task in enumerate(tasks):
                task_var = model.interval_var(name=f"Task{i}", length=task["length"])
                task_vars.append(task_var)
                is_late.append(task_var.end() >= task["deadline"])

            # Tasks cannot overlap:
            model.no_overlap(task_vars)
            # Minimize the number of late tasks:
            model.minimize(model.sum(is_late))

            result = model.solve()

        .. seealso::

            - :meth:`SequenceVar.no_overlap` is the equivalent method on :class:`SequenceVar`.
        """
        # If given a SequenceVar, use it directly; otherwise create an auxiliary sequence variable
        if isinstance(intervals, SequenceVar):
            sequence = intervals
        else:
            sequence = self._auxiliary_sequence_var(intervals)

        # Apply the no_overlap constraint on the sequence
        return sequence.no_overlap(transitions)

    def _auxiliary_sequence_var(self, intervals: Iterable[IntervalVar]) -> SequenceVar:
        """
        Internal: Create an auxiliary sequence variable.

        An auxiliary sequence variable is used internally and doesn't appear
        in the model's variable list.
        """
        sequence = self.sequence_var(intervals)
        sequence._make_auxiliary()
        return sequence

    def step_function(self, values: Iterable[tuple[int, int]]) -> IntStepFunction:
        r"""
        Creates a new integer step function.

        :param values: An array of points defining the step function in the form [[x0, y0], [x1, y1], ..., [xn, yn]], where xi and yi are integers. The array must be sorted by xi
        :type values: Iterable[tuple[int, int]]
        :rtype: IntStepFunction
        :returns: The created step function

        ## Details

        Integer step function is a piecewise constant function defined on integer
        values in range :const:`IntVarMin` to :const:`IntVarMax`.  The function is
        defined as follows:

        * :math:`f(x) = 0` for :math:`x < x_0`,
        * :math:`f(x) = y_i` for :math:`x_i \leq x < x_{i+1}`
        * :math:`f(x) = y_n` for :math:`x \geq x_n`.

        Step functions can be used in the following ways:

        * Function :meth:`Model.eval` evaluates the function at the given point (given as :class:`IntExpr`).
        * Function :meth:`Model.integral` computes a sum (integral) of the function over an :class:`IntervalVar`.
        * Constraints :meth:`Model.forbid_start` and :meth:`Model.forbid_end` forbid the start/end of an :class:`IntervalVar` to be in a zero-value interval of the function.
        * Constraint :meth:`Model.forbid_extent` forbids the extent of an :class:`IntervalVar` to be in a zero-value interval of the function.
        """
        return IntStepFunction(self, values)

    def enforce(self, constraint: Constraint | BoolExpr | bool | Iterable[Constraint | BoolExpr | bool]) -> None:
        r"""
        Enforces a boolean expression as a constraint in the model.

        :param constraint: The constraint, boolean expression, or iterable of these to enforce in the model
        :type constraint: Constraint | BoolExpr | bool | Iterable[Constraint | BoolExpr | bool]

        ## Details

        This is the primary method for enforcing boolean expressions as constraints in the model.

        A constraint is satisfied if it is not `False`. In other words, a constraint is
        satisfied if it is `True` or *absent*.

        A boolean expression that is *not* enforced as a constraint can have
        arbitrary value in a solution (`True`, `False`, or *absent*). Once enforced
        as a constraint, it can only be `True` or *absent* in the solution.

        **Note:** Constraint objects are automatically registered when created.
        Passing them to `enforce()` is accepted but does nothing. For cumulative
        constraints (`cumul <= capacity`, `cumul >= min_level`), using `enforce()` is
        recommended for code clarity even though it's not required.

        ### Accepted argument types

        The `enforce` method accepts several types of arguments:

        1. **BoolExpr objects**: Boolean expressions created from comparisons
           (e.g., `x <= 5`, `a == b`) or logical operations (e.g., `a & b`, `~c`).
        2. **bool values**: Python boolean constants `True` or `False`.
        3. **Constraint objects**: Accepted but does nothing (constraints auto-register).
           Use with cumulative constraints for clarity: `model.enforce(cumul <= capacity)`.
        4. **Iterables**: Lists, tuples, or generators of the above types.

        ## Example

        Basic usage with a boolean expression:

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="x")

            # Enforce boolean expressions as constraints
            model.enforce(x.start() >= 0)
            model.enforce(x.end() <= 100)

        ## Example

        Enforcing multiple constraints at once using an iterable:

        .. code-block:: python

            model = cp.Model()
            tasks = [model.interval_var(length=10, name=f"task_{i}") for i in range(5)]

            # Enforce multiple constraints at once
            constraints = [task.start() >= 0 for task in tasks]
            model.enforce(constraints)

            # Or using a generator expression
            model.enforce(task.end() <= 100 for task in tasks)

        ## Example

        Enforcing multiple boolean expressions:

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 100, name="x")
            y = model.int_var(0, 100, name="y")

            # Enforce various boolean expressions
            model.enforce([
                x + y <= 50,           # From comparison
                x >= 10,               # From comparison
                True,                  # Trivially satisfied constraint
            ])

        .. seealso::

            - :meth:`BoolExpr.enforce` for the fluent-style alternative.
            - :meth:`Model.no_overlap` for creating no-overlap constraints.
            - :meth:`Model.minimize` for creating minimization objectives.
            - :meth:`Model.maximize` for creating maximization objectives.
        """
        if isinstance(constraint, Iterable):
            for c in constraint:
                if not isinstance(c, Constraint):
                    self._model.append(BoolExpr._wrap(c))
        elif not isinstance(constraint, Constraint):
            self._model.append(BoolExpr._wrap(constraint))

    def minimize(self, expr: IntExpr | int) -> Objective:
        r"""
        Creates a minimization objective for the provided expression.

        :param expr: The expression to minimize
        :type expr: IntExpr | int
        :rtype: Objective
        :returns: An Objective that minimizes the expression.

        ## Details

        Creates an :class:`Objective` to minimize the given expression.
        A model can have at most one objective. New objective replaces the old one.

        Equivalent of function :meth:`IntExpr.minimize`.

        ## Example

        In the following model, we search for a solution that minimizes the maximum
        end of the two intervals `x` and `y`:

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="x")
            y = model.interval_var(length=20, name="y")
            model.minimize(model.max2(x.end(), y.end()))
            result = model.solve()

        .. seealso::

            - :meth:`Model.maximize`.
            - :meth:`IntExpr.minimize` for fluent-style minimization.
        """
        return Objective(self, 'minimize', [IntExpr._wrap(expr)])

    def maximize(self, expr: IntExpr | int) -> Objective:
        r"""
        Creates a maximization objective for the provided expression.

        :param expr: The expression to maximize
        :type expr: IntExpr | int
        :rtype: Objective
        :returns: An Objective that maximizes the expression.

        ## Details

        Creates an :class:`Objective` to maximize the given expression.
        A model can have at most one objective. New objective replaces the old one.

        Equivalent of function :meth:`IntExpr.maximize`.

        ## Example

        In the following model, we search for a solution that maximizes
        the length of the interval variable `x`:

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=(10, 20), name="x")
            model.maximize(x.length())
            result = model.solve()

        .. seealso::

            - :meth:`Model.minimize`.
            - :meth:`IntExpr.maximize` for fluent-style maximization.
        """
        return Objective(self, 'maximize', [IntExpr._wrap(expr)])

    def _set_objective(self, objective: Objective) -> None:
        """Internal: Set the model's objective."""
        self._objective = objective._get_props()

    def _add_constraint(self, constraint: Constraint | BoolExpr) -> None:
        """Internal: Add a constraint to the model."""
        self._model.append(constraint._as_arg())

    def _add_directive(self, directive: _Directive) -> None:
        """Internal: Add a directive to the model."""
        self._model.append(directive._as_arg())

    def _get_new_ref_id(self, props: _ElementProps) -> int:
        """Internal: Allocate a new reference ID for a node."""
        ref_id = len(self._refs)
        self._refs.append(props)
        return ref_id

    def _to_dict(self) -> dict[str, Any]:
        """Internal: Convert model to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            'refs': self._refs,
            'model': self._model
        }

        if self._name:
            result['name'] = self._name

        if self._objective:
            result['objective'] = self._objective

        return result

    def _from_dict(self, data: dict[str, Any]) -> None:
        """Internal: Restore model from dictionary created by _to_dict()."""
        # Restore the core model structure
        self._refs = data['refs']
        self._model = data['model']

        # Restore optional fields
        if 'name' in data:
            self._name = data['name']

        if 'objective' in data:
            self._objective = data['objective']

        # Reconstruct variable objects from refs
        for i, props in enumerate(self._refs):
            func = props.get('func')
            if func == 'boolVar':
                self._bool_vars.append(BoolVar(self, props, i))
            elif func == 'intVar':
                self._int_vars.append(IntVar(self, props, i))
            elif func == 'intervalVar':
                self._interval_vars.append(IntervalVar(self, props, i))

    @overload
    def sum(self, args: Iterable[IntExpr | int]) -> IntExpr:
        r"""
        Creates an integer expression for the sum of the arguments.

        :param args: Array of integer expressions to sum.
        :type args: Iterable[IntExpr | int]
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        Absent arguments are ignored (treated as zeros). Therefore, the resulting expression is never *absent*.

        Note that the binary operator `+` handles absent values differently. For example, when `x` is *absent* then:

        * `x + 3` is *absent*.
        * `model.sum([x, 3])` is 3.

        ## Example

        Let's consider a set of optional tasks. Due to limited resources and time, only some of them can be executed. Every task has a profit, and we want to maximize the total profit from the executed tasks.

        .. code-block:: python

            import optalcp as cp

            # Lengths and profits of the tasks:
            lengths = [10, 20, 15, 30, 20, 25, 30, 10, 20, 25]
            profits = [ 5,  6,  7,  8,  9, 10, 11, 12, 13, 14]

            model = cp.Model()
            tasks: list[cp.IntervalVar] = []
            # Profits of individual tasks. The value will be zero if the task is not executed.
            task_profits: list[cp.IntExpr] = []

            for i in range(len(lengths)):
              # All tasks must finish before time 100:
              task = model.interval_var(name=f"Task{i}", optional=True, length=lengths[i], end=(None, 100))
              tasks.append(task)
              task_profits.append(task.presence() * profits[i])

            model.maximize(model.sum(task_profits))
            # Tasks cannot overlap:
            model.no_overlap(tasks)

            result = model.solve({'searchType': 'FDS'})
        """
        ...

    @overload
    def sum(self, args: Iterable[CumulExpr]) -> CumulExpr:
        r"""
        Sum of cumulative expressions.

        :param args: Array of cumulative expressions to sum.
        :type args: Iterable[CumulExpr]
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Computes the sum of cumulative functions. The sum can be used, e.g., to combine contributions of individual tasks to total resource consumption.

        **Limitation:** Currently, pulse-based and step-based cumulative expressions cannot be mixed. All expressions in the sum must be either pulse-based or step-based.
        """
        ...

    def sum(self, args: Iterable[IntExpr | int] | Iterable[CumulExpr]) -> IntExpr | int | CumulExpr:
        # Take the first element to determine the type
        args_iter = iter(args)
        try:
            first = next(args_iter)
        except StopIteration:
            # The array is empty
            # Return 0 as the sum of an empty list. For different handling of empty sum, use Model.cumul_sum().
            return 0

        if isinstance(first, CumulExpr):
            wrapped_args = [CumulExpr._wrap(first)]
            wrapped_args.extend(CumulExpr._wrap(e) for e in args_iter)  # type: ignore[arg-type]
            return CumulExpr(self, "cumulSum", [wrapped_args])
        else:
            wrapped_args = [IntExpr._wrap(first)]
            wrapped_args.extend(IntExpr._wrap(e) for e in args_iter)  # type: ignore[arg-type]
            return IntExpr(self, "intSum", [wrapped_args])

    def presence(self, arg: IntervalVar | IntExpr | int) -> BoolExpr:
        r"""
        Creates a boolean expression that is true if the given argument is present in the solution.

        :param arg: The argument to check for presence in the solution
        :type arg: IntervalVar | IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true if the argument is present in the solution.

        ## Details

        The value of the expression remains unknown until a solution is found.
        The expression can be used in a constraint to restrict possible solutions.

        The function is equivalent to :meth:`IntervalVar.presence`
        and :meth:`IntExpr.presence`.

        ## Example

        In the following example, interval variables `x` and `y` must have the same presence status.
        I.e. they must either be both *present* or both *absent*.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            x = model.interval_var(name="x", optional=True, length=10, start=[0, 100])
            y = model.interval_var(name="y", optional=True, length=10, start=[0, 100])
            model.enforce(model.presence(x) == model.presence(y))

        ### Simple constraints over presence

        The solver treats binary constraints over presence in a special way: it
        uses them to better propagate other constraints over the same pairs of variables.
        Let's extend the previous example by a constraint that `x` must end before
        `y` starts:

        .. code-block:: python

            import optalcp as cp

            x = model.interval_var(name="x", optional=True, length=10, start=(0, 100))
            y = model.interval_var(name="y", optional=True, length=10, start=(0, 100))
            model.enforce(model.presence(x) == model.presence(y))
            # x.end <= y.start:
            precedence = x.end() <= y.start()
            model.enforce(precedence)

        In this example, the solver sees (propagates) that the minimum start time of
        `y` is 10 and maximum end time of `x` is 90.  Without the constraint over
        `presence`, the solver could not propagate that because one
        of the intervals can be *absent* and the other one *present* (and so the
        value of `precedence` would be *absent* and the constraint would be
        satisfied).

        To achieve good propagation, it is recommended to use binary
        constraints over `presence` when possible. For example, multiple binary
        constraints can be used instead of a single complicated constraint.
        """
        if isinstance(arg, IntervalVar):
            return BoolExpr(self, "intervalPresenceOf", [IntervalVar._wrap(arg)])
        return BoolExpr(self, "intPresenceOf", [IntExpr._wrap(arg)])

    # =========================================================================
    # Solving and serialization methods
    # =========================================================================

    def solve(self,
              parameters: Parameters | None = None,
              warm_start: Solution | None = None) -> SolveResult:
        r"""
        Solves the model and returns the result.

        :param parameters: The parameters for solving
        :type parameters: Parameters | None
        :param warm_start: The solution to start with
        :type warm_start: Solution | None
        :rtype: SolveResult
        :returns: The result of the solve.

        ## Details

        Solves the model using the OptalCP solver and returns the result. This is the
        main entry point for solving constraint programming models.

        The solver searches for solutions that satisfy all constraints in the model.
        If an objective was specified (using :meth:`Model.minimize` or
        :meth:`Model.maximize`), the solver searches for optimal or near-optimal
        solutions within the given time limit.

        The returned :class:`SolveResult` contains:

        * `solution` - The best solution found, or `None` if no solution was found.
          Use this to query variable values via methods like `get_start()`, `get_end()`,
          and `get_value()`.
        * `objective` - The objective value of the best solution (if an objective
          was specified).
        * `nb_solutions` - The total number of solutions found during the search.
        * `proof` - Whether the solver proved optimality or infeasibility.
        * `duration` - The total time spent solving.
        * Statistics like `nb_branches`, `nb_fails`, and `nb_restarts`.

        When an error occurs (e.g., invalid model, solver not found), the function
        raises an exception.

        ### Parameters

        Solver behavior can be controlled via the `parameters` argument. Common parameters
        include:

        * `timeLimit` - Maximum solving time in seconds.
        * `solutionLimit` - Stop after finding this many solutions.
        * `nbWorkers` - Number of parallel threads to use.
        * `searchType` - Search strategy (`"LNS"`, `"FDS"`, etc.).

        See :class:`Parameters` for the complete list.

        ### Warm start

        If the `warm_start` parameter is specified, the solver will start with the
        given solution. The solution must be compatible with the model; otherwise,
        an error will be raised. The solver will take advantage of the
        solution to speed up the search: it will search only for better solutions
        (if it is a minimization or maximization problem). The solver may also try to
        improve the provided solution by Large Neighborhood Search.

        ### Advanced usage

        This is a simple blocking function for basic usage. For advanced features
        like event callbacks, progress monitoring, or async support, use the
        :class:`Solver` class instead.

        This method works seamlessly in both regular Python scripts and Jupyter
        notebooks. In Jupyter (where an event loop is already running), it
        automatically handles nested event loops.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="task_x")
            y = model.interval_var(length=20, name="task_y")
            x.end_before_start(y)
            model.minimize(y.end())

            # Basic solve
            result = model.solve()
            print(f"Objective: {result.objective}")

            # Solve with parameters
            params: cp.Parameters = {'timeLimit': 60, 'searchType': 'LNS'}
            result = model.solve(params)

            # Solve with warm start
            if result.solution:
                result2 = model.solve(params, warm_start=result.solution)

        .. seealso::

            - :class:`Solver` for async solving with event callbacks.
            - :class:`Parameters` for available solver parameters.
            - :class:`SolveResult` for the result structure.
            - :class:`Solution` for working with solutions.
        """
        from ._solver import Solver
        return Solver()._sync_solve(self, parameters, warm_start)

    def to_json(self,
                parameters: Parameters | None = None,
                warm_start: Solution | None = None) -> str:
        r"""
        Exports the model to JSON format.

        :param parameters: Optional solver parameters to include
        :type parameters: Parameters | None
        :param warm_start: Optional initial solution to include
        :type warm_start: Solution | None
        :rtype: str
        :returns: A string containing the model in JSON format.

        ## Details

        The result can be stored in a file for later use. The model can be
        converted back from JSON format using :meth:`Model.from_json`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="task_x")
            y = model.interval_var(length=20, name="task_y")
            x.end_before_start(y)
            model.minimize(y.end())

            # Export to JSON
            json_str = model.to_json()

            # Save to file
            with open("model.json", "w") as f:
                f.write(json_str)

            # Later, load from JSON
            model2, params2, warm_start2 = cp.Model.from_json(json_str)

        .. seealso::

            - :meth:`Model.from_json` to import from JSON.
            - :meth:`Model.to_text` to export as text format.
            - :meth:`Model.to_js` to export as JavaScript code.
        """
        from ._result import _to_json_impl
        return _to_json_impl(self, parameters, warm_start)

    def to_text(self,
               parameters: Parameters | None = None,
               warm_start: Solution | None = None) -> str:
        r"""
        Converts the model to text format similar to IBM CP Optimizer file format.

        :param parameters: Optional solver parameters (mostly unused)
        :type parameters: Parameters | None
        :param warm_start: Optional initial solution to include
        :type warm_start: Solution | None
        :rtype: str
        :returns: Text representation of the model.

        ## Details

        The output is human-readable and can be stored in a file. Unlike JSON format,
        there is no way to convert the text format back into a Model.

        The result is so similar to the file format used by IBM CP Optimizer that,
        under some circumstances, the result can be used as an input file for
        CP Optimizer. However, some differences between OptalCP and CP Optimizer
        make it impossible to guarantee the result is always valid for CP Optimizer.

        Known issues:

        * OptalCP supports optional integer expressions, while CP Optimizer does not.
          If the model contains optional integer expressions, the result will not be
          valid for CP Optimizer or may be badly interpreted. For example, to get
          a valid CP Optimizer file, don't use `interval.start()`, use
          `interval.start_or(default)` instead.
        * For the same reason, prefer precedence constraints such as
          `end_before_start()` over `model.enforce(x.end() <= y.start())`.
        * Negative heights in cumulative expressions (e.g., in `step_at_start()`)
          are not supported by CP Optimizer.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="task_x")
            y = model.interval_var(length=20, name="task_y")
            x.end_before_start(y)
            model.minimize(y.end())

            # Convert to text format
            text = model.to_txt()
            print(text)

            # Save to file
            with open("model.txt", "w") as f:
                f.write(text)

        .. seealso::

            - :meth:`Model.to_js` to export as JavaScript code.
            - :meth:`Model.to_json` to export as JSON (can be imported back).
        """
        from ._solver import Solver
        solver = Solver()
        return solver._sync_to_text(self, parameters, warm_start)

    def to_js(self,
              parameters: Parameters | None = None,
              warm_start: Solution | None = None) -> str:
        r"""
        Converts the model to equivalent JavaScript code.

        :param parameters: Optional solver parameters (included in generated code)
        :type parameters: Parameters | None
        :param warm_start: Optional initial solution to include
        :type warm_start: Solution | None
        :rtype: str
        :returns: JavaScript code representing the model.

        ## Details

        The output is human-readable, executable with Node.js, and can be stored
        in a file. It is meant as a way to export a model to a format that is
        executable, human-readable, editable, and independent of other libraries.

        This feature is experimental and the result is not guaranteed to be valid
        in all cases.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="task_x")
            y = model.interval_var(length=20, name="task_y")
            x.end_before_start(y)
            model.minimize(y.end())

            # Convert to JavaScript code
            js_code = model.to_js()
            print(js_code)

            # Save to file
            with open("model.js", "w") as f:
                f.write(js_code)

        .. seealso::

            - :meth:`Model.to_text` to export as text format.
            - :meth:`Model.to_json` to export as JSON (can be imported back).
        """
        from ._solver import Solver
        solver = Solver()
        return solver._sync_to_js(self, parameters, warm_start)

    @classmethod
    def from_json(cls, json_str: str) -> tuple[Model, Parameters | None, Solution | None]:
        r"""
        Creates a model from JSON format.

        :param json_str: A string containing the model in JSON format
        :type json_str: str
        :rtype: tuple[Model, Parameters | None, Solution | None]
        :returns: A tuple containing the model, optional parameters, and optional warm start solution.

        ## Details

        Creates a new Model instance from a JSON string that was previously
        exported using :meth:`Model.to_json`.

        The method returns a tuple with three elements:
        1. The reconstructed Model
        2. Parameters (if they were included in the JSON), or None
        3. Warm start Solution (if it was included in the JSON), or None

        Variables in the new model can be accessed using methods like
        :meth:`Model.get_interval_vars`, :meth:`Model.get_int_vars`, etc.

        .. code-block:: python

            import optalcp as cp

            # Create and export a model
            model = cp.Model()
            x = model.interval_var(length=10, name="task_x")
            model.minimize(x.end())

            params: cp.Parameters = {'timeLimit': 60}
            json_str = model.to_json(params)

            # Save to file
            with open("model.json", "w") as f:
                f.write(json_str)

            # Later, load from file
            with open("model.json", "r") as f:
                json_str = f.read()

            # Restore model, parameters, and warm start
            model2, params2, warm_start2 = cp.Model.from_json(json_str)

            # Access variables
            interval_vars = model2.get_interval_vars()
            print(f"Loaded model with {len(interval_vars)} interval variables")

            # Solve with restored parameters
            if params2:
                result = model2.solve(params2)
            else:
                result = model2.solve()

        .. seealso::

            - :meth:`Model.to_json` to export to JSON.
        """
        from ._result import _from_json_impl
        return _from_json_impl(json_str)

    def _reusable_bool_expr(self, value: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [BoolExpr._wrap(value)]
        return BoolExpr(self, "reusableBoolExpr", out_params)

    def _reusable_int_expr(self, value: IntExpr | int) -> IntExpr:
        out_params: list[_Argument] = [IntExpr._wrap(value)]
        return IntExpr(self, "reusableIntExpr", out_params)

    def not_(self, arg: BoolExpr | bool) -> BoolExpr:
        r"""
        Negation of the boolean expression `arg`.

        :param arg: The boolean expression to negate.
        :type arg: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the argument has value *absent* then the resulting expression has also value *absent*.

        Same as :meth:`BoolExpr.not_`.
        """
        out_params: list[_Argument] = [BoolExpr._wrap(arg)]
        return BoolExpr(self, "boolNot", out_params)

    def or_(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Logical _OR_ of boolean expressions `lhs` and `rhs`.

        :param lhs: The first boolean expression.
        :type lhs: BoolExpr | bool
        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If one of the arguments has value *absent*, then the resulting expression also has value *absent*.

        Same as :meth:`BoolExpr.or_`.
        """
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolOr", out_params)

    def and_(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Logical _AND_ of boolean expressions `lhs` and `rhs`.

        :param lhs: The first boolean expression.
        :type lhs: BoolExpr | bool
        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If one of the arguments has value *absent*, then the resulting expression also has value *absent*.

        Same as :meth:`BoolExpr.and_`.
        """
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolAnd", out_params)

    def implies(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Logical implication of two boolean expressions, that is `lhs` implies `rhs`.

        :param lhs: The first boolean expression.
        :type lhs: BoolExpr | bool
        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If one of the arguments has value *absent*, then the resulting expression also has value *absent*.

        Same as :meth:`BoolExpr.implies`.
        """
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolImplies", out_params)

    def _eq(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolEq", out_params)

    def _ne(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolNe", out_params)

    def _nand(self, lhs: BoolExpr | bool, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [BoolExpr._wrap(lhs), BoolExpr._wrap(rhs)]
        return BoolExpr(self, "boolNand", out_params)

    def guard(self, arg: IntExpr | int, absent_value: int = 0) -> IntExpr:
        r"""
        Creates an expression that replaces value *absent* by a constant.

        :param arg: The integer expression to guard.
        :type arg: IntExpr | int
        :param absent_value: The value to use when the expression is absent.
        :type absent_value: int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The resulting expression is:

        * equal to `arg` if `arg` is *present*
        * and equal to `absent_value` otherwise (i.e. when `arg` is *absent*).

        The default value of `absent_value` is 0.

        The resulting expression is never *absent*.

        Same as :meth:`IntExpr.guard`.
        """
        out_params: list[_Argument] = [IntExpr._wrap(arg), _wrap_int(absent_value)]
        return IntExpr(self, "intGuard", out_params)

    def identity(self, lhs: IntExpr | int, rhs: IntExpr | int) -> Constraint:
        r"""
        Constrains `lhs` and `rhs` to be identical, including their presence status.

        :param lhs: The first integer expression.
        :type lhs: IntExpr | int
        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: Constraint
        :returns: The identity constraint.

        ## Details

        Identity is different than equality. For example, if `x` is *absent*, then `eq(x, 0)` is *absent*, but `identity(x, 0)` is `False`.

        Same as :meth:`IntExpr.identity`.
        """
        out_params: list[_Argument] = [IntExpr._wrap(lhs), IntExpr._wrap(rhs)]
        return Constraint(self, "intIdentity", out_params)

    def in_range(self, arg: IntExpr | int, lb: int, ub: int) -> BoolExpr:
        r"""
        Creates Boolean expression `lb` &le; `arg` &le; `ub`.

        :param arg: The integer expression to check.
        :type arg: IntExpr | int
        :param lb: The lower bound of the range.
        :type lb: int
        :param ub: The upper bound of the range.
        :type ub: int
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If `arg` has value *absent* then the resulting expression has also value *absent*.

        Use :meth:`Model.enforce` to add this expression as a constraint to the model.

        Same as :meth:`IntExpr.in_range`.
        """
        out_params: list[_Argument] = [IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return BoolExpr(self, "intInRange", out_params)

    def _not_in_range(self, arg: IntExpr | int, lb: int, ub: int) -> BoolExpr:
        out_params: list[_Argument] = [IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return BoolExpr(self, "intNotInRange", out_params)

    def abs(self, arg: IntExpr | int) -> IntExpr:
        r"""
        Creates an integer expression which is absolute value of `arg`.

        :param arg: The integer expression.
        :type arg: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If `arg` has value *absent* then the resulting expression has also value *absent*.

        Same as :meth:`IntExpr.abs`.
        """
        out_params: list[_Argument] = [IntExpr._wrap(arg)]
        return IntExpr(self, "intAbs", out_params)

    def min2(self, lhs: IntExpr | int, rhs: IntExpr | int) -> IntExpr:
        r"""
        Creates an integer expression which is the minimum of `lhs` and `rhs`.

        :param lhs: The first integer expression.
        :type lhs: IntExpr | int
        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If one of the arguments has value *absent*, then the resulting expression also has value *absent*.

        Same as :meth:`IntExpr.min2`. See :meth:`Model.min` for n-ary minimum.
        """
        out_params: list[_Argument] = [IntExpr._wrap(lhs), IntExpr._wrap(rhs)]
        return IntExpr(self, "intMin2", out_params)

    def max2(self, lhs: IntExpr | int, rhs: IntExpr | int) -> IntExpr:
        r"""
        Creates an integer expression which is the maximum of `lhs` and `rhs`.

        :param lhs: The first integer expression.
        :type lhs: IntExpr | int
        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If one of the arguments has value *absent*, then the resulting expression also has value *absent*.

        Same as :meth:`IntExpr.max2`. See :meth:`Model.max` for n-ary maximum.
        """
        out_params: list[_Argument] = [IntExpr._wrap(lhs), IntExpr._wrap(rhs)]
        return IntExpr(self, "intMax2", out_params)

    def max(self, args: Iterable[IntExpr | int]) -> IntExpr:
        r"""
        Creates an integer expression for the maximum of the arguments.

        :param args: Array of integer expressions to compute maximum of.
        :type args: Iterable[IntExpr | int]
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        Absent arguments are ignored as if they were not specified in the input array `args`. Maximum of an empty set (i.e. `max([])` is *absent*. The maximum is *absent* also if all arguments are *absent*.

        Note that binary function :meth:`Model.max2` handles absent values differently. For example, when `x` is *absent* then:

        * `max2(x, 5)` is *absent*.
        * `max([x, 5])` is 5.
        * `max([x])` is *absent*.

        ## Example

        A common use case is to compute *makespan* of a set of tasks, i.e. the time when the last task finishes. In the following example, we minimize the makespan of a set of tasks (other parts of the model are omitted).

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            # Create some tasks (lengths would typically come from problem data):
            tasks = [model.interval_var(length=10, name=f"task_{i}") for i in range(5)]
            # Create an array of end times of the tasks:
            end_times = [task.end() for task in tasks]
            makespan = model.max(end_times)
            model.minimize(makespan)

        Notice that when a task is *absent* (not executed), then its end time is *absent*. And therefore, the absent task is not included in the maximum.

        .. seealso::

            - Binary :meth:`Model.max2`.
            - Function :meth:`Model.span` constraints interval variable to start and end at minimum and maximum of the given set of intervals.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(args)]
        return IntExpr(self, "intMax", out_params)

    def min(self, args: Iterable[IntExpr | int]) -> IntExpr:
        r"""
        Creates an integer expression for the minimum of the arguments.

        :param args: Array of integer expressions to compute minimum of.
        :type args: Iterable[IntExpr | int]
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        Absent arguments are ignored as if they were not specified in the input array `args`. Minimum of an empty set (i.e. `min([])`) is *absent*. The minimum is *absent* also if all arguments are *absent*.

        Note that binary function :meth:`Model.min2` handles absent values differently. For example, when `x` is *absent* then:

        * `min2(x, 5)` is *absent*.
        * `min([x, 5])` is 5.
        * `min([x])` is *absent*.

        ## Example

        In the following example, we compute the time when the first task of `tasks` starts, i.e. the minimum of the starting times.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            # Create some tasks (lengths would typically come from problem data):
            tasks = [model.interval_var(length=10, name=f"task_{i}") for i in range(5)]
            # Create an array of start times of the tasks:
            start_times = [task.start() for task in tasks]
            first_start_time = model.min(start_times)

        Notice that when a task is *absent* (not executed), its end time is *absent*. And therefore, the absent task is not included in the minimum.

        .. seealso::

            - Binary :meth:`Model.min2`.
            - Function :meth:`Model.span` constraints interval variable to start and end at minimum and maximum of the given set of intervals.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(args)]
        return IntExpr(self, "intMin", out_params)

    def _int_present_linear_expr(self, coefficients: Iterable[int], expressions: Iterable[IntExpr | int], constant_term: int = 0) -> IntExpr:
        out_params: list[_Argument] = [_wrap_int_list(coefficients), IntExpr._wrap_list(expressions), _wrap_int(constant_term)]
        return IntExpr(self, "intPresentLinearExpr", out_params)

    def _int_optional_linear_expr(self, coefficients: Iterable[int], expressions: Iterable[IntExpr | int], constant_term: int = 0) -> IntExpr:
        out_params: list[_Argument] = [_wrap_int_list(coefficients), IntExpr._wrap_list(expressions), _wrap_int(constant_term)]
        return IntExpr(self, "intOptionalLinearExpr", out_params)

    def lex_le(self, lhs: Iterable[IntExpr | int], rhs: Iterable[IntExpr | int]) -> Constraint:
        r"""
        Lexicographic less than or equal constraint: `lhs` ≤ `rhs`.

        :param lhs: The left-hand side array of integer expressions.
        :type lhs: Iterable[IntExpr | int]
        :param rhs: The right-hand side array of integer expressions.
        :type rhs: Iterable[IntExpr | int]
        :rtype: Constraint
        :returns: The lexicographic constraint.

        ## Details

        Constrains `lhs` to be lexicographically less than or equal `rhs`.

        Both arrays must have the same length, and the length must be at least 1.

        Lexicographic ordering compares arrays element by element from the first
        position. The comparison `lhs` ≤ `rhs` holds if and only if:

        * all elements are equal (`lhs[i] == rhs[i]` for all `i`), or
        * there exists a position `k` where `lhs[k] < rhs[k]` and all preceding elements are equal (`lhs[i] == rhs[i]` for all `i < k`)

        Lexicographic constraints are useful for symmetry breaking. For example, when
        you have multiple equivalent solutions that differ only in the ordering of
        symmetric variables, adding a lexicographic constraint can eliminate redundant
        solutions.

        ## Example

        .. code-block:: python

            model = cp.Model()

            # Variables for a 3x3 matrix where rows should be lexicographically ordered
            rows = [[model.int_var(0, 9, name=f"x_{i}_{j}") for j in range(3)] for i in range(3)]

            # Break row symmetry: row[0] ≤ row[1] ≤ row[2] lexicographically
            model.lex_le(rows[0], rows[1])
            model.lex_le(rows[1], rows[2])

        .. seealso::

            - :meth:`Model.lex_lt`, :meth:`Model.lex_ge`, :meth:`Model.lex_gt` for other lexicographic comparisons.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(lhs), IntExpr._wrap_list(rhs)]
        return Constraint(self, "intLexLe", out_params)

    def lex_lt(self, lhs: Iterable[IntExpr | int], rhs: Iterable[IntExpr | int]) -> Constraint:
        r"""
        Lexicographic strictly less than constraint: `lhs` < `rhs`.

        :param lhs: The left-hand side array of integer expressions.
        :type lhs: Iterable[IntExpr | int]
        :param rhs: The right-hand side array of integer expressions.
        :type rhs: Iterable[IntExpr | int]
        :rtype: Constraint
        :returns: The lexicographic constraint.

        ## Details

        Constrains `lhs` to be lexicographically strictly less than `rhs`.

        Both arrays must have the same length, and the length must be at least 1.

        Lexicographic ordering compares arrays element by element from the first
        position. The comparison `lhs` < `rhs` holds if and only if:
        there exists a position `k` where `lhs[k] < rhs[k]` and all preceding elements are equal (`lhs[i] == rhs[i]` for all `i < k`)

        Lexicographic constraints are useful for symmetry breaking. For example, when
        you have multiple equivalent solutions that differ only in the ordering of
        symmetric variables, adding a lexicographic constraint can eliminate redundant
        solutions.

        ## Example

        .. code-block:: python

            model = cp.Model()

            # Variables for a 3x3 matrix where rows should be lexicographically ordered
            rows = [[model.int_var(0, 9, name=f"x_{i}_{j}") for j in range(3)] for i in range(3)]

            # Break row symmetry: row[0] < row[1] < row[2] lexicographically
            model.lex_lt(rows[0], rows[1])
            model.lex_lt(rows[1], rows[2])

        .. seealso::

            - :meth:`Model.lex_le`, :meth:`Model.lex_ge`, :meth:`Model.lex_gt` for other lexicographic comparisons.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(lhs), IntExpr._wrap_list(rhs)]
        return Constraint(self, "intLexLt", out_params)

    def lex_ge(self, lhs: Iterable[IntExpr | int], rhs: Iterable[IntExpr | int]) -> Constraint:
        r"""
        Lexicographic greater than or equal constraint: `lhs` ≥ `rhs`.

        :param lhs: The left-hand side array of integer expressions.
        :type lhs: Iterable[IntExpr | int]
        :param rhs: The right-hand side array of integer expressions.
        :type rhs: Iterable[IntExpr | int]
        :rtype: Constraint
        :returns: The lexicographic constraint.

        ## Details

        Constrains `lhs` to be lexicographically greater than or equal `rhs`.

        Both arrays must have the same length, and the length must be at least 1.

        Lexicographic ordering compares arrays element by element from the first
        position. The comparison `lhs` ≥ `rhs` holds if and only if:

        * all elements are equal (`lhs[i] == rhs[i]` for all `i`), or
        * there exists a position `k` where `lhs[k] > rhs[k]` and all preceding elements are equal (`lhs[i] == rhs[i]` for all `i < k`)

        Lexicographic constraints are useful for symmetry breaking. For example, when
        you have multiple equivalent solutions that differ only in the ordering of
        symmetric variables, adding a lexicographic constraint can eliminate redundant
        solutions.

        ## Example

        .. code-block:: python

            model = cp.Model()

            # Variables for a 3x3 matrix where rows should be lexicographically ordered
            rows = [[model.int_var(0, 9, name=f"x_{i}_{j}") for j in range(3)] for i in range(3)]

            # Break row symmetry: row[0] ≥ row[1] ≥ row[2] lexicographically
            model.lex_ge(rows[0], rows[1])
            model.lex_ge(rows[1], rows[2])

        .. seealso::

            - :meth:`Model.lex_le`, :meth:`Model.lex_lt`, :meth:`Model.lex_gt` for other lexicographic comparisons.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(lhs), IntExpr._wrap_list(rhs)]
        return Constraint(self, "intLexGe", out_params)

    def lex_gt(self, lhs: Iterable[IntExpr | int], rhs: Iterable[IntExpr | int]) -> Constraint:
        r"""
        Lexicographic strictly greater than constraint: `lhs` > `rhs`.

        :param lhs: The left-hand side array of integer expressions.
        :type lhs: Iterable[IntExpr | int]
        :param rhs: The right-hand side array of integer expressions.
        :type rhs: Iterable[IntExpr | int]
        :rtype: Constraint
        :returns: The lexicographic constraint.

        ## Details

        Constrains `lhs` to be lexicographically strictly greater than `rhs`.

        Both arrays must have the same length, and the length must be at least 1.

        Lexicographic ordering compares arrays element by element from the first
        position. The comparison `lhs` > `rhs` holds if and only if:
        there exists a position `k` where `lhs[k] > rhs[k]` and all preceding elements are equal (`lhs[i] == rhs[i]` for all `i < k`)

        Lexicographic constraints are useful for symmetry breaking. For example, when
        you have multiple equivalent solutions that differ only in the ordering of
        symmetric variables, adding a lexicographic constraint can eliminate redundant
        solutions.

        ## Example

        .. code-block:: python

            model = cp.Model()

            # Variables for a 3x3 matrix where rows should be lexicographically ordered
            rows = [[model.int_var(0, 9, name=f"x_{i}_{j}") for j in range(3)] for i in range(3)]

            # Break row symmetry: row[0] > row[1] > row[2] lexicographically
            model.lex_gt(rows[0], rows[1])
            model.lex_gt(rows[1], rows[2])

        .. seealso::

            - :meth:`Model.lex_le`, :meth:`Model.lex_lt`, :meth:`Model.lex_ge` for other lexicographic comparisons.
        """
        out_params: list[_Argument] = [IntExpr._wrap_list(lhs), IntExpr._wrap_list(rhs)]
        return Constraint(self, "intLexGt", out_params)

    def start(self, interval: IntervalVar) -> IntExpr:
        r"""
        Creates an integer expression for the start time of an interval variable.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval is absent, the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(model.end(x) + 10 <= model.start(y))
            model.enforce(model.length(x) <= model.length(y))

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`IntervalVar.start` is equivalent function on :class:`IntervalVar`.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval)]
        return IntExpr(self, "startOf", out_params)

    def end(self, interval: IntervalVar) -> IntExpr:
        r"""
        Creates an integer expression for the end time of an interval variable.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval is absent, the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(model.end(x) + 10 <= model.start(y))
            model.enforce(model.length(x) <= model.length(y))

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`IntervalVar.end` is equivalent function on :class:`IntervalVar`.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval)]
        return IntExpr(self, "endOf", out_params)

    def length(self, interval: IntervalVar) -> IntExpr:
        r"""
        Creates an integer expression for the duration (end - start) of an interval variable.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the interval is absent, the resulting expression is also absent.

        ## Example

        In the following example, we constrain interval variable `y` to start after the end of `x` with a delay of at least 10. In addition, we constrain the length of `x` to be less or equal to the length of `y`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x", ...)
            y = model.interval_var(name="y", ...)
            model.enforce(model.end(x) + 10 <= model.start(y))
            model.enforce(model.length(x) <= model.length(y))

        When `x` or `y` is *absent* then value of both constraints above is *absent* and therefore they are satisfied.

        .. seealso::

            - :meth:`IntervalVar.length` is equivalent function on :class:`IntervalVar`.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval)]
        return IntExpr(self, "lengthOf", out_params)

    def _alternative_cost(self, main: IntervalVar, options: Iterable[IntervalVar], weights: Iterable[int]) -> IntExpr:
        out_params: list[_Argument] = [IntervalVar._wrap(main), IntervalVar._wrap_list(options), _wrap_int_list(weights)]
        return IntExpr(self, "intAlternativeCost", out_params)

    def end_before_end(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.end() + delay <= successor.end())

        In other words, end of `predecessor` plus `delay` must be less than or equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.end_before_end` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "endBeforeEnd", out_params)

    def end_before_start(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.end() + delay <= successor.start())

        In other words, end of `predecessor` plus `delay` must be less than or equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.end_before_start` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "endBeforeStart", out_params)

    def start_before_end(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.start() + delay <= successor.end())

        In other words, start of `predecessor` plus `delay` must be less than or equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.start_before_end` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "startBeforeEnd", out_params)

    def start_before_start(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.start() + delay <= successor.start())

        In other words, start of `predecessor` plus `delay` must be less than or equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.start_before_start` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "startBeforeStart", out_params)

    def end_at_end(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.end() + delay == successor.end())

        In other words, end of `predecessor` plus `delay` must be equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.end_at_end` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "endAtEnd", out_params)

    def end_at_start(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.end() + delay == successor.start())

        In other words, end of `predecessor` plus `delay` must be equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.end_at_start` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "endAtStart", out_params)

    def start_at_end(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.start() + delay == successor.end())

        In other words, start of `predecessor` plus `delay` must be equal to end of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.start_at_end` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "startAtEnd", out_params)

    def start_at_start(self, predecessor: IntervalVar, successor: IntervalVar, delay: IntExpr | int = 0) -> Constraint:
        r"""
        Creates a precedence constraint between two interval variables.

        :param predecessor: The predecessor interval variable.
        :type predecessor: IntervalVar
        :param successor: The successor interval variable.
        :type successor: IntervalVar
        :param delay: The minimum delay between intervals.
        :type delay: IntExpr | int
        :rtype: Constraint
        :returns: The precedence constraint.

        ## Details

        Same as:

        .. code-block:: python

            model.enforce(predecessor.start() + delay == successor.start())

        In other words, start of `predecessor` plus `delay` must be equal to start of `successor`.

        When one of the two interval variables is absent, then the constraint is satisfied.

        .. seealso::

            - :meth:`IntervalVar.start_at_start` is equivalent function on :class:`IntervalVar`.
            - :meth:`IntervalVar.start`, :meth:`IntervalVar.end`
        """
        out_params: list[_Argument] = [IntervalVar._wrap(predecessor), IntervalVar._wrap(successor), IntExpr._wrap(delay)]
        return Constraint(self, "startAtStart", out_params)

    def alternative(self, main: IntervalVar, options: Iterable[IntervalVar]) -> Constraint:
        r"""
        Alternative constraint models a choice between different ways to execute an interval.

        :param main: The main interval variable.
        :type main: IntervalVar
        :param options: Array of optional interval variables to choose from.
        :type options: Iterable[IntervalVar]
        :rtype: Constraint
        :returns: The alternative constraint.

        ## Details

        Alternative constraint is a way to model various kinds of choices. For example, we can model a task that could be done by worker A, B, or C. To model such alternative, we use interval variable `main` that represents the task regardless the chosen worker and three interval variables `options = [A, B, C]` that represent the task when done by worker A, B, or C. Interval variables `A`, `B`, and `C` should be optional. This way, if e.g. option B is chosen, then `B` will be *present* and equal to `main` (they will start at the same time and end at the same time), the remaining options, A and C, will be *absent*.

        We may also decide not to execute the `main` task at all (if it is optional). Then `main` will be *absent* and all options `A`, `B` and `C` will be *absent* too.

        ### Formal definition

        The constraint `alternative(main, options)` is satisfied in the following two cases:
        1. Interval `main` is *absent* and all `options[i]` are *absent* too.
        2. Interval `main` is *present* and exactly one of `options[i]` is *present* (the remaining options are *absent*).    Let `k` be the index of the present option.    Then `main.start() == options[k].start()` and `main.end() == options[k].end()`.

        ## Example

        Let's consider task T, which can be done by workers A, B, or C. The length of the task and a cost associated with it depends on the chosen worker:

        * If done by worker A, then its length is 10, and the cost is 5.
        * If done by worker B, then its length is 20, and the cost is 2.
        * If done by worker C, then its length is 3, and the cost is 10.

        Each worker can execute only one task at a time. However, the remaining tasks are omitted in the model below. The objective could be, e.g., to minimize the total cost (also omitted in the model).

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            T = model.interval_var(name="T")
            T_A = model.interval_var(name="T_A", optional=True, length=10)
            T_B = model.interval_var(name="T_B", optional=True, length=20)
            T_C = model.interval_var(name="T_C", optional=True, length=3)

            # T_A, T_B and T_C are different ways to execute task T:
            model.alternative(T, [T_A, T_B, T_C])
            # The cost depends on the chosen option:
            cost_of_t = model.sum([
                T_A.presence() * 5,
                T_B.presence() * 2,
                T_C.presence() * 10
            ])

            # Each worker A can perform only one task at a time:
            model.no_overlap([T_A, ...])  # Worker A
            model.no_overlap([T_B, ...])  # Worker B
            model.no_overlap([T_C, ...])  # Worker C

            # Minimize the total cost:
            model.minimize(model.sum([cost_of_t, ...]))
        """
        out_params: list[_Argument] = [IntervalVar._wrap(main), IntervalVar._wrap_list(options)]
        return Constraint(self, "alternative", out_params)

    def _interval_var_element(self, slots: Iterable[IntervalVar], index: IntExpr | int, value: IntervalVar) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(slots), IntExpr._wrap(index), IntervalVar._wrap(value)]
        return Constraint(self, "intervalVarElement", out_params)

    def _increasing_interval_var_element(self, slots: Iterable[IntervalVar], index: IntExpr | int, value: IntervalVar) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(slots), IntExpr._wrap(index), IntervalVar._wrap(value)]
        return Constraint(self, "increasingIntervalVarElement", out_params)

    def _itv_mapping(self, tasks: Iterable[IntervalVar], slots: Iterable[IntervalVar], indices: Iterable[IntExpr | int]) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(tasks), IntervalVar._wrap_list(slots), IntExpr._wrap_list(indices)]
        return Constraint(self, "itvMapping", out_params)

    def span(self, main: IntervalVar, covered: Iterable[IntervalVar]) -> Constraint:
        r"""
        Constrains an interval variable to span (cover) a set of other interval variables.

        :param main: The spanning interval variable.
        :type main: IntervalVar
        :param covered: The set of interval variables to cover.
        :type covered: Iterable[IntervalVar]
        :rtype: Constraint
        :returns: The span constraint.

        ## Details

        Span constraint can be used to model, for example, a composite task that consists of several subtasks.

        The constraint makes sure that interval variable `main` starts with the first interval in `covered` and ends with the last interval in `covered`. Absent interval variables in `covered` are ignored.

        ### Formal definition

        Span constraint is satisfied in one of the following two cases:

        * Interval variable `main` is absent and all interval variables in `covered` are absent too.
        * Interval variable `main` is present, at least one interval in `covered` is present and:

           * `main.start()` is equal to the minimum starting time of all present intervals in `covered`.
           * `main.end()` is equal to the maximum ending time of all present intervals in `covered`.

        ## Example

        Let's consider composite task `T`, which consists of 3 subtasks: `T1`, `T2`, and `T3`. Subtasks are independent, could be processed in any order, and may overlap. However, task T is blocking a particular location, and no other task can be processed there. The location is blocked as soon as the first task from `T1`, `T2`, `T3` starts, and it remains blocked until the last one of them finishes.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # Subtasks have known lengths:
            T1 = model.interval_var(name="T1", length=10)
            T2 = model.interval_var(name="T2", length=5)
            T3 = model.interval_var(name="T3", length=15)
            # The main task has unknown length though:
            T = model.interval_var(name="T")

            # T spans/covers T1, T2 and T3:
            model.span(T, [T1, T2, T3])

            # Tasks requiring the same location cannot overlap.
            # Other tasks are not included in the example, therefore '...' below:
            model.no_overlap([T, ...])

        .. seealso::

            - :meth:`IntervalVar.span` is equivalent function on :class:`IntervalVar`.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(main), IntervalVar._wrap_list(covered)]
        return Constraint(self, "span", out_params)

    def position(self, interval: IntervalVar, sequence: SequenceVar) -> IntExpr:
        r"""
        Creates an expression equal to the position of the `interval` on the `sequence`.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param sequence: The sequence variable.
        :type sequence: SequenceVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        In the solution, the interval which is scheduled first has position 0, the second interval has position 1, etc. The position of an absent interval is `absent`.

        The `position` expression cannot be used with interval variables of possibly zero length (because the position of two simultaneous zero-length intervals would be undefined). Also, `position` cannot be used in case of :meth:`Model.no_overlap` constraint with transition times.

        .. seealso::

            - :meth:`IntervalVar.position` is equivalent function on :class:`IntervalVar`.
            - :meth:`Model.no_overlap` for constraints on overlapping intervals.
            - :meth:`Model.sequence_var` for creating sequence variables.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), SequenceVar._wrap(sequence)]
        return IntExpr(self, "position", out_params)

    def _same_sequence(self, sequence1: SequenceVar, sequence2: SequenceVar) -> Constraint:
        out_params: list[_Argument] = [SequenceVar._wrap(sequence1), SequenceVar._wrap(sequence2)]
        return Constraint(self, "sameSequence", out_params)

    def _same_sequence_group(self, sequences: Iterable[SequenceVar]) -> Constraint:
        out_params: list[_Argument] = [SequenceVar._wrap_list(sequences)]
        return Constraint(self, "sameSequenceGroup", out_params)

    def pulse(self, interval: IntervalVar, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) _pulse_ for the given interval variable and height.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Pulse can be used to model a resource requirement during an interval variable. The given amount `height` of the resource is used throughout the interval (from start to end).

        **Limitation:** The `height` must be non-negative. Pulses with negative height are not supported. If you need negative contributions, use step functions instead (see :meth:`Model.step_at_start` and :meth:`Model.step_at_end`).

        ### Formal definition

        Pulse creates a cumulative function which has the value:

        * `0` before `interval.start()`,
        * `height` between `interval.start()` and `interval.end()`,
        * `0` after `interval.end()`

        If `interval` is absent, the pulse is `0` everywhere.

        The `height` can be a constant value or an expression. In particular, the `height` can be given by an :class:`IntVar`. In such a case, the `height` is unknown at the time of the model creation but is determined during the search.

        Note that the `interval` and the `height` may have different presence statuses (when the `height` is given by a variable or an expression). In this case, the pulse is present only if both the `interval` and the `height` are present. Therefore, it is helpful to constrain the `height` to have the same presence status as the `interval`.

        Cumulative functions can be combined using operators (`+`, `-`, unary `-`) and :meth:`Model.sum`. A cumulative function's minimum and maximum height can be constrained using comparison operators (`<=`, `>=`).

        ## Example

        Let us consider a set of tasks and a group of 3 workers. Each task requires a certain number of workers (`demand`). Our goal is to schedule the tasks so that the length of the schedule (makespan) is minimal.

        .. code-block:: python

            import optalcp as cp

            # The input data:
            nb_workers = 3
            tasks = [
              { "length": 10, "demand": 3},
              { "length": 20, "demand": 2},
              { "length": 15, "demand": 1},
              { "length": 30, "demand": 2},
              { "length": 20, "demand": 1},
              { "length": 25, "demand": 2},
              { "length": 10, "demand": 1},
            ]

            model = cp.Model()
            # A set of pulses, one for each task:
            pulses = []
            # End times of the tasks:
            ends = []

            for i in range(len(tasks)):
              # Create a task:
              task = model.interval_var(name=f"T{i+1}", length=tasks[i]["length"])
              # Create a pulse for the task:
              pulses.append(model.pulse(task, tasks[i]["demand"]))
              # Store the end of the task:
              ends.append(task.end())

            # The number of workers used at any time cannot exceed nb_workers:
            model.enforce(model.sum(pulses) <= nb_workers)
            # Minimize the maximum of the ends (makespan):
            model.minimize(model.max(ends))

            result = model.solve({'searchType': 'FDS'})

        ## Example

        In the following example, we create three interval variables `x`, `y`, and `z` that represent some tasks. Variables `x` and `y` are present, but variable `z` is optional. Each task requires a certain number of workers. The length of the task depends on the assigned number of workers. The number of assigned workers is modeled using integer variables `wx`, `wy`, and `wz`.

        There are 7 workers. Therefore, at any time, the sum of the workers assigned to the running tasks must be less or equal to 7.

        If the task `z` is absent, then the variable `wz` has no meaning, and therefore, it should also be absent.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(name="x")
            y = model.interval_var(name="y")
            z = model.interval_var(name="z", optional=True)

            wx = model.int_var(min=1, max=5, name="wx")
            wy = model.int_var(min=1, max=5, name="wy")
            wz = model.int_var(min=1, max=5, name="wz", optional=True)

            # wz is present if and only if z is present:
            model.enforce(z.presence() == wz.presence())

            px = model.pulse(x, wx)
            py = model.pulse(y, wy)
            pz = model.pulse(z, wz)

            # There are at most 7 workers at any time:
            model.enforce(model.sum([px, py, pz]) <= 7)

            # Length of the task depends on the number of workers using the following formula:
            #    length * wx = 12
            model.enforce(x.length() * wx == 12)
            model.enforce(y.length() * wy == 12)
            model.enforce(z.length() * wz == 12)

        .. seealso::

            - :meth:`IntervalVar.pulse` is equivalent function on :class:`IntervalVar`.
            - :meth:`Model.step_at_start`, :meth:`Model.step_at_end`, :meth:`Model.step_at` for other basic cumulative functions.
            - :class:`CumulExpr` for constraining cumulative functions using comparison operators (`<=`, `>=`).
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntExpr._wrap(height)]
        return CumulExpr(self, "pulse", out_params)

    def step_at_start(self, interval: IntervalVar, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) that changes value at start of the interval variable by the given height.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Cumulative *step* functions could be used to model a resource that is consumed or produced and, therefore, changes in amount over time. Examples of such a resource are a battery, an account balance, a product's stock, etc.

        A `step_at_start` can change the amount of such resource at the start of a given variable. The amount is changed by the given `height`, which can be positive or negative.

        The `height` can be a constant value or an expression. In particular, the `height` can be given by an :class:`IntVar`. In such a case, the `height` is unknown at the time of the model creation but is determined during the search.

        Note that the `interval` and the `height` may have different presence statuses (when the `height` is given by a variable or an expression). In this case, the step is present only if both the `interval` and the `height` are present. Therefore, it is helpful to constrain the `height` to have the same presence status as the `interval`.

        Cumulative steps can be combined using operators (`+`, `-`, unary `-`) and :meth:`Model.sum`. A cumulative function's minimum and maximum height can be constrained using comparison operators (`<=`, `>=`).

        ### Formal definition

        stepAtStart creates a cumulative function which has the value:

        * `0` before `interval.start()`,
        * `height` after `interval.start()`.

        If the `interval` or the `height` is *absent*, the created cumulative function is `0` everywhere.

        ## Example

        Let us consider a set of tasks. Each task either costs a certain amount of money or makes some money. Money is consumed at the start of a task and produced at the end. We have an initial `budget`, and we want to schedule the tasks so that we do not run out of money (i.e., the amount is always non-negative).

        Tasks cannot overlap. Our goal is to find the shortest schedule possible.

        .. code-block:: python

            import optalcp as cp

            # The input data:
            budget = 100
            tasks = [
                {"length": 10, "money": -150},
                {"length": 20, "money":   40},
                {"length": 15, "money":   20},
                {"length": 30, "money":  -10},
                {"length": 20, "money":   30},
                {"length": 25, "money":  -20},
                {"length": 10, "money":   10},
                {"length": 20, "money":   50},
            ]

            model = cp.Model()
            task_vars = []
            # A set of steps, one for each task:
            steps = []

            for i in range(len(tasks)):
                interval = model.interval_var(name=f"T{i+1}", length=tasks[i]["length"])
                task_vars.append(interval)
                if tasks[i]["money"] < 0:
                    # Task costs some money:
                    steps.append(model.step_at_start(interval, tasks[i]["money"]))
                else:
                    # Tasks makes some money:
                    steps.append(model.step_at_end(interval, tasks[i]["money"]))

            # The initial budget increases the cumul at time 0:
            steps.append(model.step_at(0, budget))
            # The money must be non-negative at any time:
            model.enforce(model.sum(steps) >= 0)
            # Only one task at a time:
            model.no_overlap(task_vars)

            # Minimize the maximum of the ends (makespan):
            model.minimize(model.max([t.end() for t in task_vars]))

            result = model.solve({'searchType': 'FDS'})

        .. seealso::

            - :meth:`IntervalVar.step_at_start` is equivalent function on :class:`IntervalVar`.
            - :meth:`Model.step_at_end`, :meth:`Model.step_at`, :meth:`Model.pulse` for other basic cumulative functions.
            - :class:`CumulExpr` for constraining cumulative functions using comparison operators (`<=`, `>=`).
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntExpr._wrap(height)]
        return CumulExpr(self, "stepAtStart", out_params)

    def step_at_end(self, interval: IntervalVar, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates cumulative function (expression) that changes value at end of the interval variable by the given height.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param height: The height value.
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        Cumulative *step* functions could be used to model a resource that is consumed or produced and, therefore, changes in amount over time. Examples of such a resource are a battery, an account balance, a product's stock, etc.

        A `step_at_end` can change the amount of such resource at the end of a given variable. The amount is changed by the given `height`, which can be positive or negative.

        The `height` can be a constant value or an expression. In particular, the `height` can be given by an :class:`IntVar`. In such a case, the `height` is unknown at the time of the model creation but is determined during the search.

        Note that the `interval` and the `height` may have different presence statuses (when the `height` is given by a variable or an expression). In this case, the step is present only if both the `interval` and the `height` are present. Therefore, it is helpful to constrain the `height` to have the same presence status as the `interval`.

        Cumulative steps can be combined using operators (`+`, `-`, unary `-`) and :meth:`Model.sum`. A cumulative function's minimum and maximum height can be constrained using comparison operators (`<=`, `>=`).

        ### Formal definition

        stepAtEnd creates a cumulative function which has the value:

        * `0` before `interval.end()`,
        * `height` after `interval.end()`.

        If the `interval` or the `height` is *absent*, the created cumulative function is `0` everywhere.

        ## Example

        Let us consider a set of tasks. Each task either costs a certain amount of money or makes some money. Money is consumed at the start of a task and produced at the end. We have an initial `budget`, and we want to schedule the tasks so that we do not run out of money (i.e., the amount is always non-negative).

        Tasks cannot overlap. Our goal is to find the shortest schedule possible.

        .. code-block:: python

            import optalcp as cp

            # The input data:
            budget = 100
            tasks = [
                {"length": 10, "money": -150},
                {"length": 20, "money":   40},
                {"length": 15, "money":   20},
                {"length": 30, "money":  -10},
                {"length": 20, "money":   30},
                {"length": 25, "money":  -20},
                {"length": 10, "money":   10},
                {"length": 20, "money":   50},
            ]

            model = cp.Model()
            task_vars = []
            # A set of steps, one for each task:
            steps = []

            for i in range(len(tasks)):
                interval = model.interval_var(name=f"T{i+1}", length=tasks[i]["length"])
                task_vars.append(interval)
                if tasks[i]["money"] < 0:
                    # Task costs some money:
                    steps.append(model.step_at_start(interval, tasks[i]["money"]))
                else:
                    # Tasks makes some money:
                    steps.append(model.step_at_end(interval, tasks[i]["money"]))

            # The initial budget increases the cumul at time 0:
            steps.append(model.step_at(0, budget))
            # The money must be non-negative at any time:
            model.enforce(model.sum(steps) >= 0)
            # Only one task at a time:
            model.no_overlap(task_vars)

            # Minimize the maximum of the ends (makespan):
            model.minimize(model.max([t.end() for t in task_vars]))

            result = model.solve({'searchType': 'FDS'})

        .. seealso::

            - :meth:`IntervalVar.step_at_end` is equivalent function on :class:`IntervalVar`.
            - :meth:`Model.step_at_start`, :meth:`Model.step_at`, :meth:`Model.pulse` for other basic cumulative functions.
            - :class:`CumulExpr` for constraining cumulative functions using comparison operators (`<=`, `>=`).
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntExpr._wrap(height)]
        return CumulExpr(self, "stepAtEnd", out_params)

    def step_at(self, x: int, height: IntExpr | int) -> CumulExpr:
        r"""
        Creates a cumulative function that changes value at a given point.

        :param x: The point at which the cumulative function changes value.
        :type x: int
        :param height: The height value (can be positive, negative, constant, or expression).
        :type height: IntExpr | int
        :rtype: CumulExpr
        :returns: The resulting cumulative expression

        ## Details

        This function is similar to :meth:`Model.step_at_start` and :meth:`Model.step_at_end`, but the time of the change is given by the constant value `x` instead of by the start/end of an interval variable. The height can be a constant or an expression (e.g., created by :meth:`Model.int_var`).

        ### Formal definition

        `step_at` creates a cumulative function which has the value:

        * 0 before `x`,
        * `height` after `x`.

        .. seealso::

            - :meth:`Model.step_at_start`, :meth:`Model.step_at_end` for an example with `step_at`.
            - :class:`CumulExpr` for constraining cumulative functions using comparison operators (`<=`, `>=`).
        """
        out_params: list[_Argument] = [_wrap_int(x), IntExpr._wrap(height)]
        return CumulExpr(self, "stepAt", out_params)

    def _cumul_max_profile(self, cumul: CumulExpr, profile: IntStepFunction) -> Constraint:
        out_params: list[_Argument] = [CumulExpr._wrap(cumul), IntStepFunction._wrap(profile)]
        return Constraint(self, "cumulMaxProfile", out_params)

    def _cumul_min_profile(self, cumul: CumulExpr, profile: IntStepFunction) -> Constraint:
        out_params: list[_Argument] = [CumulExpr._wrap(cumul), IntStepFunction._wrap(profile)]
        return Constraint(self, "cumulMinProfile", out_params)

    def _cumul_stairs(self, atoms: Iterable[CumulExpr]) -> CumulExpr:
        out_params: list[_Argument] = [CumulExpr._wrap_list(atoms)]
        return CumulExpr(self, "cumulStairs", out_params)

    def _precedence_energy_before(self, main: IntervalVar, others: Iterable[IntervalVar], heights: Iterable[int], capacity: int) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap(main), IntervalVar._wrap_list(others), _wrap_int_list(heights), _wrap_int(capacity)]
        return Constraint(self, "precedenceEnergyBefore", out_params)

    def _precedence_energy_after(self, main: IntervalVar, others: Iterable[IntervalVar], heights: Iterable[int], capacity: int) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap(main), IntervalVar._wrap_list(others), _wrap_int_list(heights), _wrap_int(capacity)]
        return Constraint(self, "precedenceEnergyAfter", out_params)

    def integral(self, func: IntStepFunction, interval: IntervalVar) -> IntExpr:
        r"""
        Computes sum of values of the step function `func` over the interval `interval`.

        :param func: The step function.
        :type func: IntStepFunction
        :param interval: The interval variable.
        :type interval: IntervalVar
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The sum is computed over all points in range `interval.start()` .. `interval.end()-1`. The sum includes the function value at the start time but not the value at the end time. If the interval variable has zero length, then the result is 0. If the interval variable is absent, then the result is `absent`.

        **Requirement**: The step function `func` must be non-negative.

        .. seealso::

            - :meth:`IntStepFunction.integral` for the equivalent function on :class:`IntStepFunction`.
        """
        out_params: list[_Argument] = [IntStepFunction._wrap(func), IntervalVar._wrap(interval)]
        return IntExpr(self, "intStepFunctionIntegral", out_params)

    def _step_function_integral_in_range(self, func: IntStepFunction, interval: IntervalVar, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [IntStepFunction._wrap(func), IntervalVar._wrap(interval), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self, "intStepFunctionIntegralInRange", out_params)

    def eval(self, func: IntStepFunction, arg: IntExpr | int) -> IntExpr:
        r"""
        Evaluates a step function at a given point.

        :param func: The step function.
        :type func: IntStepFunction
        :param arg: The point at which to evaluate the step function.
        :type arg: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The result is the value of the step function `func` at the point `arg`. If the value of `arg` is `absent`, then the result is also `absent`.

        By constraining the returned value, it is possible to limit `arg` to be only within certain segments of the segmented function. In particular, functions :meth:`Model.forbid_start` and :meth:`Model.forbid_end` work that way.

        .. seealso::

            - :meth:`IntStepFunction.eval` for the equivalent function on :class:`IntStepFunction`.
            - :meth:`Model.forbid_start`, :meth:`Model.forbid_end` are convenience functions built on top of `eval`.
        """
        out_params: list[_Argument] = [IntStepFunction._wrap(func), IntExpr._wrap(arg)]
        return IntExpr(self, "intStepFunctionEval", out_params)

    def _step_function_eval_in_range(self, func: IntStepFunction, arg: IntExpr | int, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [IntStepFunction._wrap(func), IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self, "intStepFunctionEvalInRange", out_params)

    def _step_function_eval_not_in_range(self, func: IntStepFunction, arg: IntExpr | int, lb: int, ub: int) -> Constraint:
        out_params: list[_Argument] = [IntStepFunction._wrap(func), IntExpr._wrap(arg), _wrap_int(lb), _wrap_int(ub)]
        return Constraint(self, "intStepFunctionEvalNotInRange", out_params)

    def forbid_extent(self, interval: IntervalVar, func: IntStepFunction) -> Constraint:
        r"""
        Forbid the interval variable to overlap with segments of the function where the value is zero.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param func: The step function.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the extent (entire interval).

        ## Details

        This function prevents the specified interval variable from overlapping with segments of the step function where the value is zero. That is, if :math:`[s, e)` is a segment of the step function where the value is zero, then the interval variable either ends before :math:`s` (:math:`\mathtt{interval.end()} \le s`) or starts after :math:`e` (:math:`e \le \mathtt{interval.start()}`).

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
            model.forbid_extent(production, availability)
            model.minimize(production.end())

            result = model.solve()
            # Production runs [0, 3) - finishes before maintenance window

        .. seealso::

            - :meth:`IntervalVar.forbid_extent` for the equivalent function on :class:`IntervalVar`.
            - :meth:`Model.forbid_start`, :meth:`Model.forbid_end` for similar functions that constrain the start/end of an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntStepFunction._wrap(func)]
        return Constraint(self, "forbidExtent", out_params)

    def forbid_start(self, interval: IntervalVar, func: IntStepFunction) -> Constraint:
        r"""
        Constrains the start of the interval variable to be outside of the zero-height segments of the step function.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param func: The step function.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the start point.

        ## Details

        This function is equivalent to:

        .. code-block:: python

            model.enforce(model.eval(func, interval.start()) != 0)

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
            model.forbid_start(task, allowed_starts)
            model.minimize(task.start())

            result = model.solve()
            # Task starts at 6 (earliest allowed start time)

        .. seealso::

            - :meth:`IntervalVar.forbid_start` for the equivalent function on :class:`IntervalVar`.
            - :meth:`Model.forbid_end` for similar function that constrains end an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntStepFunction._wrap(func)]
        return Constraint(self, "forbidStart", out_params)

    def forbid_end(self, interval: IntervalVar, func: IntStepFunction) -> Constraint:
        r"""
        Constrains the end of the interval variable to be outside of the zero-height segments of the step function.

        :param interval: The interval variable.
        :type interval: IntervalVar
        :param func: The step function.
        :type func: IntStepFunction
        :rtype: Constraint
        :returns: The constraint forbidding the end point.

        ## Details

        This function is equivalent to:

        .. code-block:: python

            model.enforce(model.eval(func, interval.end()) != 0)

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
            model.forbid_end(delivery, allowed_ends)
            model.minimize(delivery.end())

            result = model.solve()
            # Delivery ends at 9 (starts at 8, ends at earliest allowed time)

        .. seealso::

            - :meth:`IntervalVar.forbid_end` for the equivalent function on :class:`IntervalVar`.
            - :meth:`Model.forbid_start` for similar function that constrains start an interval variable.
            - :meth:`Model.eval` for evaluation of a step function.
        """
        out_params: list[_Argument] = [IntervalVar._wrap(interval), IntStepFunction._wrap(func)]
        return Constraint(self, "forbidEnd", out_params)

    def _disjunctive_is_before(self, x: IntervalVar, y: IntervalVar) -> BoolExpr:
        out_params: list[_Argument] = [IntervalVar._wrap(x), IntervalVar._wrap(y)]
        return BoolExpr(self, "disjunctiveIsBefore", out_params)

    def _itv_presence_chain(self, intervals: Iterable[IntervalVar]) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(intervals)]
        return Constraint(self, "itvPresenceChain", out_params)

    def _itv_presence_chain_with_count(self, intervals: Iterable[IntervalVar], count: IntExpr | int) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(intervals), IntExpr._wrap(count)]
        return Constraint(self, "itvPresenceChainWithCount", out_params)

    def _end_before_start_chain(self, intervals: Iterable[IntervalVar]) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(intervals)]
        return Constraint(self, "endBeforeStartChain", out_params)

    def _start_before_start_chain(self, intervals: Iterable[IntervalVar]) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(intervals)]
        return Constraint(self, "startBeforeStartChain", out_params)

    def _end_before_end_chain(self, intervals: Iterable[IntervalVar]) -> Constraint:
        out_params: list[_Argument] = [IntervalVar._wrap_list(intervals)]
        return Constraint(self, "endBeforeEndChain", out_params)

    def _decision_present_int_var(self, variable: IntExpr | int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentIntVar", out_params)

    def _decision_absent_int_var(self, variable: IntExpr | int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionAbsentIntVar", out_params)

    def _decision_present_interval_var(self, variable: IntervalVar, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentIntervalVar", out_params)

    def _decision_absent_interval_var(self, variable: IntervalVar, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionAbsentIntervalVar", out_params)

    def _decision_present_le(self, variable: IntExpr | int, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentLE", out_params)

    def _decision_optional_gt(self, variable: IntExpr | int, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalGT", out_params)

    def _decision_present_ge(self, variable: IntExpr | int, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentGE", out_params)

    def _decision_optional_lt(self, variable: IntExpr | int, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntExpr._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalLT", out_params)

    def _decision_present_start_le(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentStartLE", out_params)

    def _decision_optional_start_gt(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalStartGT", out_params)

    def _decision_present_start_ge(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentStartGE", out_params)

    def _decision_optional_start_lt(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalStartLT", out_params)

    def _decision_present_end_le(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentEndLE", out_params)

    def _decision_optional_end_gt(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalEndGT", out_params)

    def _decision_present_end_ge(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentEndGE", out_params)

    def _decision_optional_end_lt(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalEndLT", out_params)

    def _decision_present_length_le(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionPresentLengthLE", out_params)

    def _decision_optional_length_gt(self, variable: IntervalVar, bound: int, is_left: bool) -> _SearchDecision:
        out_params: list[_Argument] = [IntervalVar._wrap(variable), _wrap_int(bound), _wrap_bool(is_left)]
        return _SearchDecision(self, "decisionOptionalLengthGT", out_params)

    def _no_good(self, decisions: Iterable[_SearchDecision]) -> Constraint:
        out_params: list[_Argument] = [_SearchDecision._wrap_list(decisions)]
        return Constraint(self, "noGood", out_params)

    def _related(self, x: IntervalVar, y: IntervalVar) -> _Directive:
        out_params: list[_Argument] = [IntervalVar._wrap(x), IntervalVar._wrap(y)]
        return _Directive(self, "related", out_params)

    def _pack(self, load: Iterable[IntExpr | int], where: Iterable[IntExpr | int], sizes: Iterable[int]) -> Constraint:
        out_params: list[_Argument] = [IntExpr._wrap_list(load), IntExpr._wrap_list(where), _wrap_int_list(sizes)]
        return Constraint(self, "pack", out_params)


