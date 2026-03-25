"""
Integer and boolean variable classes for OptalCP Python API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._constants import IntVarMax, _PresenceStatus
from ._expressions import BoolExpr, IntExpr, _ElementProps

if TYPE_CHECKING:
    from ._model import Model


class IntVar(IntExpr):
    r"""
    Integer variable represents an unknown (integer) value that solver has to find.

    The value of the integer variable can be constrained using arithmetic operators (`+`, `-`, `*`, `//`) and comparison operators (`<`, `<=`, `==`, `!=`, `>`, `>=`).

    OptalCP solver focuses on scheduling problems and concentrates on :class:`IntervalVar` variables.
    Therefore, interval variables should be the primary choice for modeling in OptalCP.
    However, integer variables can be used for other purposes, such as counting or indexing.
    In particular, integer variables can be helpful for cumulative expressions with variable heights; see :meth:`Model.pulse`, :meth:`Model.step_at_start`, :meth:`Model.step_at_end`, and :meth:`Model.step_at`.

    The integer variable can be optional.
    In this case, the solver can make the variable absent, which is usually interpreted as the fact that the solver does not use the variable at all.
    Functions :meth:`Model.presence` and :meth:`IntExpr.presence` can constrain the presence of the variable.

    Integer variables can be created using the function :meth:`Model.int_var`.

    ## Example

    In the following example we create three integer variables `x`, `y` and `z`.
    Variables `x` and `y` are present, but variable `z` is optional.
    Each variable has a different range of possible values.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        x = model.int_var(name="x", min=1, max=3)
        y = model.int_var(name="y", min=0, max=100)
        z = model.int_var(name="z", min=10, max=20, optional=True)
    """

    def __init__(self, model: Model, props: _ElementProps, ref_id: int | None = None):
        # Don't call super().__init__ - we're creating from props directly
        self._model = model
        self._props = props
        self._arg = None
        if ref_id is not None:
            # Loading from JSON - use existing ref_id
            self._arg = {'ref': ref_id}
        else:
            # Variables always get a reference ID
            self._force_ref()

    def _is_absent(self) -> bool:
        """Internal helper to check if variable is absent."""
        return self._props.get('status') == _PresenceStatus.Absent

    @property
    def min(self) -> int | None:
        r"""
        The minimum value of the integer variable's domain.

        Gets or sets the minimum value of the integer variable's domain.

        The initial value is set during construction by :meth:`Model.int_var`.
        If the variable is absent, the getter returns `None`.

        **Note:** This property reflects the variable's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntVarMin` to :const:`IntVarMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.int_var(min=5, max=10, name="x")

            print(x.min)  # 5

            x.min = 7
            print(x.min)  # 7

        .. seealso::

            - :attr:`IntVar.max`, :attr:`IntVar.optional`.
        """
        if self._is_absent():
            return None
        return self._props.get('min', 0)

    @min.setter
    def min(self, value: int) -> None:
        self._props['min'] = int(value)

    @property
    def max(self) -> int | None:
        r"""
        The maximum value of the integer variable's domain.

        Gets or sets the maximum value of the integer variable's domain.

        The initial value is set during construction by :meth:`Model.int_var`.
        If the variable is absent, the getter returns `None`.

        **Note:** This property reflects the variable's domain in the model
        (before the solve), not in the solution.

        The value must be in the range :const:`IntVarMin` to :const:`IntVarMax`.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.int_var(min=5, max=10, name="x")

            print(x.max)  # 10

            x.max = 8
            print(x.max)  # 8

        .. seealso::

            - :attr:`IntVar.min`, :attr:`IntVar.optional`.
        """
        if self._is_absent():
            return None
        return self._props.get('max', IntVarMax)

    @max.setter
    def max(self, value: int) -> None:
        self._props['max'] = int(value)

    @property
    def optional(self) -> bool | None:
        r"""
        The presence status of the integer variable.

        Gets or sets the presence status of the integer variable using a tri-state value:

        - `True` / `True`: The variable is *optional* - the solver decides whether it is present or absent in the solution.
        - `False` / `False`: The variable is *present* - it must have a value in the solution.
        - `None` / `None`: The variable is *absent* - it will be omitted from the solution.

        **Note:** This property reflects the presence status in the model
        (before the solve), not in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.int_var(min=0, max=10, name="x")
            y = model.int_var(min=0, max=10, optional=True, name="y")

            print(x.optional)  # False (present by default)
            print(y.optional)  # True (optional)

            # Make x optional
            x.optional = True
            print(x.optional)  # True

            # Make y absent
            y.optional = None
            print(y.optional)  # None

        .. seealso::

            - :attr:`IntVar.min`, :attr:`IntVar.max`.
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


class BoolVar(BoolExpr):
    r"""
    Boolean variable represents an unknown truth value (`True` or `False`) that the solver must find.

    Boolean variables are useful for modeling decisions, choices, or logical conditions in your problem. For example, you can use boolean variables to represent whether a machine is used, whether a task is assigned to a particular worker, or whether a constraint should be enforced.

    Boolean variables can be created using the function :meth:`Model.bool_var`.
    By default, boolean variables are *present* (not optional).
    To create an optional boolean variable, specify `optional=True` in the arguments of the function.

    ### Logical operators

    Boolean variables support the following logical operators:

    - `~x` for logical NOT
    - `x | y` for logical OR
    - `x & y` for logical AND

    These operators can be used to create complex boolean expressions and constraints.

    ### Boolean variables as integer expressions

    Class `BoolVar` derives from :class:`BoolExpr`, which derives from :class:`IntExpr`.
    Therefore, boolean variables can be used as integer expressions:
    *True* is equal to *1*, *False* is equal to *0*, and *absent* remains *absent*.

    This is useful for counting how many conditions are satisfied or for weighted sums.

    ### Optional boolean variables

    A boolean variable can be optional. In this case, the solver can decide to make the variable *absent*, which means the variable doesn't participate in the solution. When a boolean variable is absent, its value is neither `True` nor `False` — it is *absent*.

    Most expressions that depend on an absent variable are also *absent*. For example, if `x` is an absent boolean variable, then `~x`, `x | y`, and `x & y` are all *absent*, regardless of the value of `y`. However, some functions handle absent values specially, such as :meth:`IntExpr.presence` or :meth:`Model.sum`.

    When a boolean expression is added as a constraint using :meth:`Model.enforce`, the constraint requires that the expression is not `False` in the solution. The expression can be `True` or *absent*. This means that constraints involving optional variables are automatically satisfied when the underlying variables are absent.

    Functions :meth:`Model.presence` and :meth:`IntExpr.presence` can constrain the presence of the variable.

    ## Example

    In the following example, we create two boolean variables representing whether to use each of two machines. We require that at least one machine is used, but not both:

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        use_machine_a = model.bool_var(name="use_machine_a")
        use_machine_b = model.bool_var(name="use_machine_b")

        # Constraint: must use at least one machine
        model.enforce(use_machine_a | use_machine_b)

        # Constraint: cannot use both machines (exclusive choice)
        model.enforce(~(use_machine_a & use_machine_b))

        result = model.solve()

    ## Example

    Boolean variables can be used in arithmetic expressions by treating `True` as 1 and `False` as 0:

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        options = [model.bool_var(name=f"option_{i}") for i in range(5)]

        # Constraint: select exactly 2 options
        model.enforce(model.sum(options) == 2)

        result = model.solve()

    .. seealso::

        - :meth:`Model.bool_var` to create boolean variables.
        - :class:`BoolExpr` for boolean expressions and their operations.
        - :class:`IntVar` for integer decision variables.
        - :class:`IntervalVar` for the primary variable type for scheduling problems.
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

    def _is_absent(self) -> bool:
        """Internal helper to check if variable is absent."""
        return self._props.get('status') == _PresenceStatus.Absent

    @property
    def min(self) -> bool | None:
        r"""
        The minimum value of the boolean variable's domain.

        Gets or sets the minimum value of the boolean variable's domain.

        For a free (unconstrained) boolean variable, returns `False`.
        If set to `True`, the variable is fixed to `True`.
        If the variable is absent, the getter returns `None`.

        **Note:** This property reflects the variable's domain in the model
        (before the solve), not in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.bool_var(name="x")

            print(x.min)  # False (default minimum)

            x.min = True
            print(x.min)  # True (variable is now fixed to True)

        .. seealso::

            - :attr:`BoolVar.max`, :attr:`BoolVar.optional`.
        """
        if self._is_absent():
            return None
        return self._props.get('min', 0) > 0

    @min.setter
    def min(self, value: bool) -> None:
        self._props['min'] = bool(value)

    @property
    def max(self) -> bool | None:
        r"""
        The maximum value of the boolean variable's domain.

        Gets or sets the maximum value of the boolean variable's domain.

        For a free (unconstrained) boolean variable, returns `True`.
        If set to `False`, the variable is fixed to `False`.
        If the variable is absent, the getter returns `None`.

        **Note:** This property reflects the variable's domain in the model
        (before the solve), not in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.bool_var(name="x")

            print(x.max)  # True (default maximum)

            x.max = False
            print(x.max)  # False (variable is now fixed to False)

        .. seealso::

            - :attr:`BoolVar.min`, :attr:`BoolVar.optional`.
        """
        if self._is_absent():
            return None
        return self._props.get('max', 1) > 0

    @max.setter
    def max(self, value: bool) -> None:
        self._props['max'] = bool(value)

    @property
    def optional(self) -> bool | None:
        r"""
        The presence status of the boolean variable.

        Gets or sets the presence status of the boolean variable using a tri-state value:

        - `True` / `True`: The variable is *optional* - the solver decides whether it is present or absent in the solution.
        - `False` / `False`: The variable is *present* - it must have a value in the solution.
        - `None` / `None`: The variable is *absent* - it will be omitted from the solution.

        **Note:** This property reflects the presence status in the model
        (before the solve), not in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.bool_var(name="x")
            y = model.bool_var(optional=True, name="y")

            print(x.optional)  # False (present by default)
            print(y.optional)  # True (optional)

            # Make x optional
            x.optional = True
            print(x.optional)  # True

            # Make y absent
            y.optional = None
            print(y.optional)  # None

        .. seealso::

            - :attr:`BoolVar.min`, :attr:`BoolVar.max`.
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
