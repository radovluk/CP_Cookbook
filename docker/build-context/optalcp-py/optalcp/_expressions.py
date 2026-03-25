"""
Expression and element classes for OptalCP Python API.

This module contains ModelElement and expression classes (IntExpr, BoolExpr, CumulExpr).
Type definitions are in _types.py.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, overload

from ._constants import (
    IntervalMax,
    IntervalMin,
    IntVarMax,
    IntVarMin,
    LengthMax,
)
from ._types import (
    _Argument,
    _ElementProps,
    _IndirectArgument,
    _ScalarArgument,
    _wrap_bool,
    _wrap_int,
    _wrap_int_list,
    _wrap_int_matrix,
)

if TYPE_CHECKING:
    from ._model import Model
    from ._scheduling import IntStepFunction

# Re-export types and constants for backwards compatibility
__all__ = [
    # Constants (from _constants.py)
    'IntVarMax',
    'IntVarMin',
    'IntervalMax',
    'IntervalMin',
    'LengthMax',
    # Types (from _types.py)
    '_ElementProps',
    '_IndirectArgument',
    '_ScalarArgument',
    '_Argument',
    '_wrap_int',
    '_wrap_bool',
    '_wrap_int_list',
    '_wrap_int_matrix',
    # Expression classes
    'ModelElement',
    'Constraint',
    'Objective',
    'IntExpr',
    'BoolExpr',
    'CumulExpr',
    '_Directive',
    '_SearchDecision',
]


class ModelElement:
    r"""
    The base class for all modeling objects.

    ## Example

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        x = model.interval_var(length=10, name="x")
        start = model.start(x)
        result = model.solve()

    Interval variable `x` and expression `start` are both instances of :class:`ModelElement`.
    There are specialized descendant classes such as :class:`IntervalVar` and :class:`IntExpr`.

    Any modeling object can be assigned a name using the :attr:`ModelElement.name` property.
    """

    def __init__(self, model: Model, func: str, args: list[_Argument]):
        self._model = model
        self._props: _ElementProps = {
            'func': func,
            'args': args
        }
        # How this node is referred when used in an expression
        # None: not used yet
        # {'arg': props}: used once (inlined)
        # {'ref': id}: used multiple times (referenced by ID)
        self._arg: _IndirectArgument | None = None

    @property
    def name(self) -> str | None:
        r"""
        The name assigned to this model element.

        The name is optional and primarily useful for debugging purposes. When set,
        it helps identify the element in solver logs, error messages, and when
        inspecting solutions.

        Names can be assigned to any model element including variables, expressions,
        and constraints.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()

            # Name a variable at creation
            task = model.interval_var(length=10, name="assembly")

            # Or set name later
            x = model.int_var(min=0, max=100)
            x.name = "quantity"

            print(task.name)  # "assembly"
            print(x.name)     # "quantity"
        """
        return self._props.get('name')

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError(f"Element name must be str, got {type(value).__name__}")
        self._props['name'] = value

    def _get_props(self) -> _ElementProps:
        """Internal: Get the element properties for serialization."""
        return self._props

    def _as_arg(self) -> _IndirectArgument:
        """
        Internal: Get the argument representation for this element.

        First use: inline the element as {'arg': props}
        Second use: create a reference ID and return {'ref': id}
        """
        if self._arg is None:
            # First time this element is used in an expression
            self._arg = {'arg': self._props}
        elif 'ref' not in self._arg:
            # Second time the element is used - create a reference
            ref_id = self._model._get_new_ref_id(self._props)
            self._arg = {'ref': ref_id}
        return self._arg

    def _force_ref(self) -> None:
        """Internal: Force this element to have a reference ID (for variables)."""
        ref_id = self._model._get_new_ref_id(self._props)
        self._arg = {'ref': ref_id}

    def _get_id(self) -> int:
        """Internal: Get the reference ID of this element."""
        assert self._arg is not None and 'ref' in self._arg
        return self._arg['ref']


class Constraint(ModelElement):
    r"""
    Represents a constraint in the model.

    A constraint is a condition that must be satisfied by a valid solution. Constraints are created by calling constraint-creating methods on the model or on expressions.

    **Important:** Constraints are automatically registered with the model when created. There is no need to explicitly add them using `Model.enforce()` or similar methods.

    Note that comparison operators on integer expressions (like `x <= 10`) return :class:`BoolExpr`, not `Constraint`. Boolean expressions must be explicitly enforced using :meth:`Model.enforce` or :meth:`BoolExpr.enforce`.

    Unlike :class:`BoolExpr`, constraints cannot be combined using logical operators like :meth:`Model.and_`/:meth:`Model.or_` or `&`/`|`.

    Common ways to create constraints:

    - **Scheduling constraints**: :meth:`Model.no_overlap`, :meth:`Model.alternative`, :meth:`Model.span`
    - **Precedence constraints**: :meth:`IntervalVar.end_before_start`, :meth:`IntervalVar.start_at_end`
    - **Cumulative constraints**: `cumul <= capacity`, `cumul >= min_level`

    .. code-block:: python

        model = cp.Model()

        # Scheduling constraint - automatically registered
        tasks = [model.interval_var(length=5, name=f"t_{i}") for i in range(3)]
        model.no_overlap(tasks)

        # Precedence constraint - automatically registered
        task1 = model.interval_var(length=10, name="task1")
        task2 = model.interval_var(length=10, name="task2")
        task1.end_before_start(task2)

        # Cumulative constraint - use model.enforce() for clarity
        resource = model.sum(model.pulse(t, 1) for t in tasks)
        model.enforce(resource <= 2)

    .. seealso::

        - :meth:`Model.enforce` for enforcing boolean expressions as constraints.
        - :class:`BoolExpr` for boolean expressions that can also be enforced as constraints.
    """

    def __init__(self, model: Model, func: str, args: list[_Argument]):
        super().__init__(model, func, args)
        model._add_constraint(self)


class Objective(ModelElement):
    r"""
    Represents an optimization objective in the model.

    An objective specifies what value should be minimized or maximized when solving the model. Objectives are created by calling :meth:`Model.minimize` or :meth:`Model.maximize`, or by using the fluent methods :meth:`IntExpr.minimize` or :meth:`IntExpr.maximize`.

    A model can have at most one objective.

    .. code-block:: python

        model = cp.Model()
        x = model.interval_var(length=10, name="x")
        y = model.interval_var(length=20, name="y")

        # Create objective using Model.minimize() - automatically registered:
        model.minimize(y.end())

        # Or using fluent style on expressions - automatically registered:
        y.end().minimize()

    .. seealso::

        - :meth:`Model.minimize` for creating minimization objectives.
        - :meth:`Model.maximize` for creating maximization objectives.
        - :meth:`IntExpr.minimize` for fluent-style minimization.
        - :meth:`IntExpr.maximize` for fluent-style maximization.
    """

    def __init__(self, model: Model, func: str, expr_arg: list[_Argument]):
        super().__init__(model, func, expr_arg)
        model._set_objective(self)


class IntExpr(ModelElement):
    r"""
    A class representing an integer expression in the model.

    The expression may depend on the value of a variable (or variables), so the
    value of the expression is not known until a solution is found. The value must
    be in the range :const:`IntVarMin` to :const:`IntVarMax`.

    Use standard arithmetic operators (`+`, `-`, `*`, `//`, `%`, unary `-`) and
    comparison operators (`<`, `<=`, `==`, `!=`, `>`, `>=`).

    ## Example

    The following code creates two interval variables `x` and `y`
    and an integer expression `makespan` that is equal to the maximum of the end
    times of `x` and `y` (see :meth:`Model.max2`):

    .. code-block:: python

        model = cp.Model()
        x = model.interval_var(length=10, name="x")
        y = model.interval_var(length=20, name="y")
        makespan = model.max2(x.end(), y.end())

    ## Optional integer expressions

    Underlying variables of an integer expression may be optional, i.e., they may
    or may not be present in a solution (for example, an optional task
    can be omitted entirely from the solution). In this case, the value of the
    integer expression is *absent*. The value *absent* means that the variable
    has no meaning; it does not exist in the solution.

    Except :meth:`IntExpr.guard` expression, any value of an integer
    expression that depends on an absent variable is also *absent*.
    As we don't know the value of the expression before the solution is found,
    we call such expression *optional*.

    ## Example

    In the following model, there is an optional interval variable `x` and
    a non-optional interval variable `y`.  We add a constraint that the end of `x` plus
    10 must be less or equal to the start of `y`:

    .. code-block:: python

        model = cp.Model()
        x = model.interval_var(length=10, name="x", optional=True)
        y = model.interval_var(length=20, name="y")
        finish = x.end()
        ready = finish + 10
        begin = y.start()
        precedes = ready <= begin
        model.enforce(precedes)
        result = model.solve()

    In this model:

    * `finish` is an optional integer expression because it depends on
      an optional variable `x`.
    * The expression `ready` is optional for the same reason.
    * The expression `begin` is not optional because it depends only on a
      non-optional variable `y`.
    * Boolean expression `precedes` is also optional. Its value could be
      `True`, `False` or *absent*.

    The expression `precedes` is turned into a constraint using
    :meth:`Model.enforce`. Therefore, it cannot be `False`
    in the solution. However, it can still be *absent*. Therefore the constraint
    `precedes` can be satisfied in two ways:

    1. Both `x` and `y` are present, `x` is before `y`, and the delay between them
    is at least 10. In this case, `precedes` is `True`.
    2. `x` is absent and `y` is present. In this case, `precedes` is *absent*.
    """

    @staticmethod
    def _wrap(expr: int | IntExpr) -> _ScalarArgument:
        """Internal: Convert an int or IntExpr to an argument."""
        if isinstance(expr, (int, bool)):
            return expr
        if isinstance(expr, IntExpr): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected IntExpr, int, or bool. Got {type(expr).__name__}")

    @staticmethod
    def _wrap_list(exprs: Iterable[int | IntExpr]) -> _Argument:
        """Internal: Convert a list of int/bool/IntExpr to a list of arguments (makes a copy)."""
        return [IntExpr._wrap(e) for e in exprs]

    def __add__(self, other: IntExpr | int) -> IntExpr:
        r"""
        Add two integer expressions using the `+` operator.

        :param other: The expression or constant to add.
        :type other: IntExpr | int
        :rtype: IntExpr
        :returns: A new expression representing the sum.

        ## Details

        Returns a new :class:`IntExpr` representing `self + other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr + other` calls `__add__`
        - `5 + expr` calls `__radd__`

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr + IntExpr
            sum_expr = x + y

            # Forward: IntExpr + constant
            incremented = x + 1

            # Reverse: constant + IntExpr
            also_incremented = 1 + x

        .. seealso::

            - :meth:`Model.sum` for summing multiple expressions. Note: `Model.sum([x, absent])` equals `x`, while `x + absent` is *absent*.
        """
        return IntExpr(self._model, 'intPlus', [self._as_arg(), IntExpr._wrap(other)])

    def __radd__(self, other: int) -> IntExpr:
        r"""
        Reverse addition for `constant + expr`.

        :param other: The constant to add.
        :type other: int
        :rtype: IntExpr
        :returns: A new expression representing the sum.

        ## Details

        Called when a constant is on the left: `5 + expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__add__` for the forward operator.
        """
        return IntExpr(self._model, 'intPlus', [_wrap_int(other), self._as_arg()])

    def __sub__(self, other: IntExpr | int) -> IntExpr:
        r"""
        Subtract integer expressions using the `-` operator.

        :param other: The expression or constant to subtract.
        :type other: IntExpr | int
        :rtype: IntExpr
        :returns: A new expression representing the difference.

        ## Details

        Returns a new :class:`IntExpr` representing `self - other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr - other` calls `__sub__`
        - `5 - expr` calls `__rsub__`

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr - IntExpr
            diff = x - y

            # Forward: IntExpr - constant
            decremented = x - 1

            # Reverse: constant - IntExpr
            inverse = 10 - x
        """
        return IntExpr(self._model, 'intMinus', [self._as_arg(), IntExpr._wrap(other)])

    def __rsub__(self, other: int) -> IntExpr:
        r"""
        Reverse subtraction for `constant - expr`.

        :param other: The constant to subtract from.
        :type other: int
        :rtype: IntExpr
        :returns: A new expression representing the difference.

        ## Details

        Called when a constant is on the left: `10 - expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__sub__` for the forward operator.
        """
        return IntExpr(self._model, 'intMinus', [_wrap_int(other), self._as_arg()])

    def __mul__(self, other: IntExpr | int) -> IntExpr:
        r"""
        Multiply integer expressions using the `*` operator.

        :param other: The expression or constant to multiply by.
        :type other: IntExpr | int
        :rtype: IntExpr
        :returns: A new expression representing the product.

        ## Details

        Returns a new :class:`IntExpr` representing `self * other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr * other` calls `__mul__`
        - `5 * expr` calls `__rmul__`

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr * IntExpr
            product = x * y

            # Forward: IntExpr * constant
            doubled = x * 2

            # Reverse: constant * IntExpr
            also_doubled = 2 * x
        """
        return IntExpr(self._model, 'intTimes', [self._as_arg(), IntExpr._wrap(other)])

    def __rmul__(self, other: int) -> IntExpr:
        r"""
        Reverse multiplication for `constant * expr`.

        :param other: The constant to multiply.
        :type other: int
        :rtype: IntExpr
        :returns: A new expression representing the product.

        ## Details

        Called when a constant is on the left: `2 * expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__mul__` for the forward operator.
        """
        return IntExpr(self._model, 'intTimes', [_wrap_int(other), self._as_arg()])

    def __floordiv__(self, other: IntExpr | int) -> IntExpr:
        r"""
        Integer division using the `//` operator.

        :param other: The divisor expression or constant.
        :type other: IntExpr | int
        :rtype: IntExpr
        :returns: A new expression representing the integer quotient.

        ## Details

        Returns a new :class:`IntExpr` representing `self // other` (integer division).

        If either operand has value *absent*, the result is also *absent*.

        The result is always rounded toward negative infinity (floor division).

        Both forward and reverse operators are supported:

        - `expr // other` calls `__floordiv__`
        - `100 // expr` calls `__rfloordiv__`

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(1, 10, name="x")
            y = model.int_var(1, 10, name="y")

            # Forward: IntExpr // IntExpr
            quotient = x // y

            # Forward: IntExpr // constant
            halved = x // 2

            # Reverse: constant // IntExpr
            inverse_div = 100 // x
        """
        return IntExpr(self._model, 'intDiv', [self._as_arg(), IntExpr._wrap(other)])

    def __rfloordiv__(self, other: int) -> IntExpr:
        r"""
        Reverse integer division for `constant // expr`.

        :param other: The dividend constant.
        :type other: int
        :rtype: IntExpr
        :returns: A new expression representing the integer quotient.

        ## Details

        Called when a constant is on the left: `100 // expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__floordiv__` for the forward operator.
        """
        return IntExpr(self._model, 'intDiv', [_wrap_int(other), self._as_arg()])

    def __neg__(self) -> IntExpr:
        r"""
        Negate an integer expression using the unary `-` operator.

        :rtype: IntExpr
        :returns: A new expression representing the negation.

        ## Details

        Returns a new :class:`IntExpr` representing `-self`.

        If the operand has value *absent*, the result is also *absent*.

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")

            # Negate the expression
            neg_x = -x

            # Use in constraints
            model.enforce(neg_x >= -5)  # equivalent to x <= 5
        """
        return IntExpr(self._model, 'intNeg', [self._as_arg()])

    def __lt__(self, other: IntExpr | int) -> BoolExpr:
        r"""
        Create a less-than constraint using the `<` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self < other.

        ## Details

        Returns a :class:`BoolExpr` representing `self < other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr < other` calls `__lt__`
        - `5 < expr` calls `__rlt__` (equivalent to `expr > 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr < IntExpr
            model.enforce(x < y)

            # Forward: IntExpr < constant
            model.enforce(x < 5)

            # Reverse: constant < IntExpr
            model.enforce(3 < x)  # equivalent to x > 3
        """
        return BoolExpr(self._model, 'intLt', [self._as_arg(), IntExpr._wrap(other)])

    def __le__(self, other: IntExpr | int) -> BoolExpr:
        r"""
        Create a less-than-or-equal constraint using the `<=` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self <= other.

        ## Details

        Returns a :class:`BoolExpr` representing `self <= other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr <= other` calls `__le__`
        - `5 <= expr` calls `__rle__` (equivalent to `expr >= 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr <= IntExpr
            model.enforce(x <= y)

            # Forward: IntExpr <= constant
            model.enforce(x <= 5)

            # Reverse: constant <= IntExpr
            model.enforce(3 <= x)  # equivalent to x >= 3
        """
        return BoolExpr(self._model, 'intLe', [self._as_arg(), IntExpr._wrap(other)])

    def __gt__(self, other: IntExpr | int) -> BoolExpr:
        r"""
        Create a greater-than constraint using the `>` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self > other.

        ## Details

        Returns a :class:`BoolExpr` representing `self > other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr > other` calls `__gt__`
        - `5 > expr` calls `__rgt__` (equivalent to `expr < 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr > IntExpr
            model.enforce(x > y)

            # Forward: IntExpr > constant
            model.enforce(x > 5)

            # Reverse: constant > IntExpr
            model.enforce(7 > x)  # equivalent to x < 7
        """
        return BoolExpr(self._model, 'intGt', [self._as_arg(), IntExpr._wrap(other)])

    @overload
    def __ge__(self, other: IntExpr | int) -> BoolExpr:
        r"""
        Create a greater-than-or-equal comparison using the `>=` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self >= other.

        ## Details

        Returns a :class:`BoolExpr` representing `self >= other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr >= other` calls `__ge__`
        - `5 >= expr` calls `__rge__` (equivalent to `expr <= 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr >= IntExpr
            model.enforce(x >= y)

            # Forward: IntExpr >= constant
            model.enforce(x >= 5)

            # Reverse: constant >= IntExpr
            model.enforce(7 >= x)  # equivalent to x <= 7
        """
        ...

    @overload
    def __ge__(self, other: CumulExpr) -> Constraint:
        r"""
        Create a cumulative capacity constraint using `capacity >= cumul`.

        :param other: The cumulative expression to constrain.
        :type other: CumulExpr
        :rtype: Constraint
        :returns: A constraint ensuring the cumulative expression never exceeds self.

        ## Details

        Returns a :class:`Constraint` that ensures the cumulative expression is at most `self` (i.e., `cumul <= self`). This allows writing `capacity >= cumul` in a natural order.

        This overload enables variable capacity constraints where the capacity is an :class:`IntExpr` (such as an :class:`IntVar`).

        **Limitations:**

        - Variable capacity is only supported for discrete resources (pulses). Reservoir resources (steps) require a constant capacity.
        - The capacity expression must not be optional or absent.

        .. code-block:: python

            model = cp.Model()
            tasks = [model.interval_var(length=5, name=f"task_{i}") for i in range(3)]
            cumul = model.sum(model.pulse(t, 2) for t in tasks)

            # Variable capacity constraint: capacity >= cumul
            capacity = model.int_var(min=4, max=10, name="capacity")
            model.enforce(capacity >= cumul)

        .. seealso::

            - :meth:`CumulExpr.__le__` for the equivalent using `cumul <= capacity`.
            - :meth:`CumulExpr.__rge__` for the reverse operator on CumulExpr.
        """
        ...

    def __ge__(self, other: IntExpr | int | CumulExpr) -> BoolExpr | Constraint:
        if isinstance(other, CumulExpr):
            return Constraint(self._model, 'cumulLe', [other._as_arg(), self._as_arg()])
        return BoolExpr(self._model, 'intGe', [self._as_arg(), IntExpr._wrap(other)])

    def __eq__(self, other: IntExpr | int) -> BoolExpr:  # type: ignore
        r"""
        Create an equality constraint using the `==` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self == other.

        ## Details

        Returns a :class:`BoolExpr` representing `self == other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr == other` calls `__eq__`
        - `5 == expr` calls `__req__` (equivalent to `expr == 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr == IntExpr
            model.enforce(x == y)

            # Forward: IntExpr == constant
            model.enforce(x == 5)

            # Reverse: constant == IntExpr
            model.enforce(5 == x)  # equivalent to x == 5
        """
        return BoolExpr(self._model, 'intEq', [self._as_arg(), IntExpr._wrap(other)])

    def __ne__(self, other: IntExpr | int) -> BoolExpr:  # type: ignore
        r"""
        Create a not-equal constraint using the `!=` operator.

        :param other: The expression or constant to compare against.
        :type other: IntExpr | int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when self != other.

        ## Details

        Returns a :class:`BoolExpr` representing `self != other`.

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr != other` calls `__ne__`
        - `5 != expr` calls `__rne__` (equivalent to `expr != 5`)

        .. code-block:: python

            model = cp.Model()
            x = model.int_var(0, 10, name="x")
            y = model.int_var(0, 10, name="y")

            # Forward: IntExpr != IntExpr
            model.enforce(x != y)

            # Forward: IntExpr != constant
            model.enforce(x != 5)

            # Reverse: constant != IntExpr
            model.enforce(5 != x)  # equivalent to x != 5
        """
        return BoolExpr(self._model, 'intNe', [self._as_arg(), IntExpr._wrap(other)])

    def __rlt__(self, other: int) -> BoolExpr:
        r"""
        Reverse less-than for `constant < expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant < expr.

        ## Details

        Called when a constant is on the left: `5 < expr` (equivalent to `expr > 5`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__lt__` for the forward operator.
        """
        return BoolExpr(self._model, 'intGt', [self._as_arg(), _wrap_int(other)])

    def __rle__(self, other: int) -> BoolExpr:
        r"""
        Reverse less-than-or-equal for `constant <= expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant <= expr.

        ## Details

        Called when a constant is on the left: `5 <= expr` (equivalent to `expr >= 5`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__le__` for the forward operator.
        """
        return BoolExpr(self._model, 'intGe', [self._as_arg(), _wrap_int(other)])

    def __rgt__(self, other: int) -> BoolExpr:
        r"""
        Reverse greater-than for `constant > expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant > expr.

        ## Details

        Called when a constant is on the left: `7 > expr` (equivalent to `expr < 7`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__gt__` for the forward operator.
        """
        return BoolExpr(self._model, 'intLt', [self._as_arg(), _wrap_int(other)])

    def __rge__(self, other: int) -> BoolExpr:
        r"""
        Reverse greater-than-or-equal for `constant >= expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant >= expr.

        ## Details

        Called when a constant is on the left: `7 >= expr` (equivalent to `expr <= 7`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__ge__` for the forward operator.
        """
        return BoolExpr(self._model, 'intLe', [self._as_arg(), _wrap_int(other)])

    def __req__(self, other: int) -> BoolExpr:
        r"""
        Reverse equality for `constant == expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant == expr.

        ## Details

        Called when a constant is on the left: `5 == expr` (equivalent to `expr == 5`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__eq__` for the forward operator.
        """
        return BoolExpr(self._model, 'intEq', [self._as_arg(), _wrap_int(other)])

    def __rne__(self, other: int) -> BoolExpr:
        r"""
        Reverse not-equal for `constant != expr`.

        :param other: The constant to compare.
        :type other: int
        :rtype: BoolExpr
        :returns: A boolean expression that is true when constant != expr.

        ## Details

        Called when a constant is on the left: `5 != expr` (equivalent to `expr != 5`).

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`IntExpr.__ne__` for the forward operator.
        """
        return BoolExpr(self._model, 'intNe', [self._as_arg(), _wrap_int(other)])

    def minimize(self) -> Objective:
        r"""
        Creates a minimization objective for this expression.

        :rtype: Objective
        :returns: An Objective that minimizes this expression.

        ## Details

        Creates an objective to minimize the value of this integer expression.
        A model can have at most one objective. New objective replaces the old one.

        This is a fluent-style alternative to :meth:`Model.minimize` that allows
        creating objectives directly from expressions.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="x")
            y = model.interval_var(length=20, name="y")

            # Fluent style - minimize the end of y
            y.end().minimize()

            # Equivalent Model.minimize() style:
            model.minimize(y.end())

        .. seealso::

            - :meth:`Model.minimize` for Model-centric minimization.
            - :meth:`IntExpr.maximize` for maximization.
        """
        return Objective(self._model, 'minimize', [self._as_arg()])

    def maximize(self) -> Objective:
        r"""
        Creates a maximization objective for this expression.

        :rtype: Objective
        :returns: An Objective that maximizes this expression.

        ## Details

        Creates an objective to maximize the value of this integer expression.
        A model can have at most one objective. New objective replaces the old one.

        This is a fluent-style alternative to :meth:`Model.maximize` that allows
        creating objectives directly from expressions.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(start=(0, 100), length=10, name="x")

            # Fluent style - maximize the start of x
            x.start().maximize()

            # Equivalent Model.maximize() style:
            model.maximize(x.start())

        .. seealso::

            - :meth:`Model.maximize` for Model-centric maximization.
            - :meth:`IntExpr.minimize` for minimization.
        """
        return Objective(self._model, 'maximize', [self._as_arg()])

    def _reusable_int_expr(self) -> IntExpr:
        out_params: list[_Argument] = [self._as_arg()]
        return IntExpr(self._model, "reusableIntExpr", out_params)

    def presence(self) -> BoolExpr:
        r"""
        Returns an expression which is `True` if the expression is *present* and `False` when it is *absent*.

        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        The resulting expression is never *absent*.

        Same as :meth:`Model.presence`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return BoolExpr(self._model, "intPresenceOf", out_params)

    def guard(self, absent_value: int = 0) -> IntExpr:
        r"""
        Creates an expression that replaces value *absent* by a constant.

        :param absent_value: The value to use when the expression is absent.
        :type absent_value: int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        The resulting expression is:

        * equal to the expression if the expression is *present*
        * and equal to `absent_value` otherwise (i.e. when the expression is *absent*).

        The default value of `absent_value` is 0.

        The resulting expression is never *absent*.

        Same as :meth:`Model.guard`.
        """
        out_params: list[_Argument] = [self._as_arg(), _wrap_int(absent_value)]
        return IntExpr(self._model, "intGuard", out_params)

    def identity(self, rhs: IntExpr | int) -> Constraint:
        r"""
        Constrains two expressions to be identical, including their presence status.

        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: Constraint
        :returns: The constraint object

        ## Details

        Identity is different than equality. For example, if `x` is *absent*, then `x == 0` is *absent*, but `x.identity(0)` is `False`.

        Same as :meth:`Model.identity`.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(rhs)]
        return Constraint(self._model, "intIdentity", out_params)

    def in_range(self, lb: int, ub: int) -> BoolExpr:
        r"""
        Creates Boolean expression `lb` ≤ `this` ≤ `ub`.

        :param lb: The lower bound of the range.
        :type lb: int
        :param ub: The upper bound of the range.
        :type ub: int
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the expression has value *absent*, then the resulting expression has also value *absent*.

        Use :meth:`Model.enforce` to add this expression as a constraint to the model.

        Same as :meth:`Model.in_range`.
        """
        out_params: list[_Argument] = [self._as_arg(), _wrap_int(lb), _wrap_int(ub)]
        return BoolExpr(self._model, "intInRange", out_params)

    def _not_in_range(self, lb: int, ub: int) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg(), _wrap_int(lb), _wrap_int(ub)]
        return BoolExpr(self._model, "intNotInRange", out_params)

    def abs(self) -> IntExpr:
        r"""
        Creates an integer expression which is absolute value of the expression.

        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the expression has value *absent*, the resulting expression also has value *absent*.

        Same as :meth:`Model.abs`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return IntExpr(self._model, "intAbs", out_params)

    def min2(self, rhs: IntExpr | int) -> IntExpr:
        r"""
        Creates an integer expression which is the minimum of the expression and `arg`.

        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the expression or `arg` has value *absent*, then the resulting expression has also value *absent*.

        Same as :meth:`Model.min2`. See :meth:`Model.min` for the n-ary minimum.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(rhs)]
        return IntExpr(self._model, "intMin2", out_params)

    def max2(self, rhs: IntExpr | int) -> IntExpr:
        r"""
        Creates an integer expression which is the maximum of the expression and `arg`.

        :param rhs: The second integer expression.
        :type rhs: IntExpr | int
        :rtype: IntExpr
        :returns: The resulting integer expression

        ## Details

        If the expression or `arg` has value *absent*, then the resulting expression has also value *absent*.

        Same as :meth:`Model.max2`. See :meth:`Model.max` for n-ary maximum.
        """
        out_params: list[_Argument] = [self._as_arg(), IntExpr._wrap(rhs)]
        return IntExpr(self._model, "intMax2", out_params)




class BoolExpr(IntExpr):
    r"""
    A class that represents a boolean expression in the model.
    The expression may depend on one or more variables; therefore, its value
    may be unknown until a solution is found.

    ## Example

    For example, the following code creates two interval variables, `x` and `y`
    and a boolean expression `precedes` that is true if `x` ends before `y` starts,
    that is, if the end of `x` is less than or equal to
    the start of `y`:

    Use standard comparison operators on expressions: `x.end() <= y.start()`.

    Boolean expressions can be used to create constraints using :meth:`Model.enforce`. In the example above, we may require that `precedes` is
    true or *absent*:

    .. code-block:: python

        model.enforce(precedes)

    ### Optional boolean expressions

    *OptalCP* is using 3-value logic: a boolean expression can be `True`, `False`
    or *absent*. Typically, the expression is *absent* only if one or
    more underlying variables are *absent*.  The value *absent*
    means that the expression doesn't have a meaning because one or more
    underlying variables are absent (not part of the solution).

    ### Difference between constraints and boolean expressions

    Boolean expressions can take arbitrary value (`True`, `False`, or *absent*)
    and can be combined into composed expressions (e.g., using :meth:`BoolExpr.and_` or
    :meth:`BoolExpr.or_`).

    Constraints can only be `True` or *absent* (in a solution) and cannot
    be combined into composed expressions.

    Some functions create constraints directly, e.g. :meth:`Model.no_overlap`.
    It is not possible to combine constraints using logical operators like `or_`.

    ## Example

    Let's consider a similar example to the one above but with an optional interval
    variables `a` and `b`:

    .. code-block:: python

        model = cp.Model()
        a = model.interval_var(length=10, name="a", optional=True)
        b = model.interval_var(length=20, name="b", optional=True)
        precedes = a.end() <= b.start()
        model.enforce(precedes)
        result = model.solve()

    Adding a boolean expression as a constraint requires that the expression
    cannot be `False` in a solution. It could be *absent* though.
    Therefore, in our example, there are four kinds of solutions:

    1. Both `a` and `b` are present, and `a` ends before `b` starts.
    2. Only `a` is present, and `b` is absent.
    3. Only `b` is present, and `a` is absent.
    4. Both `a` and `b` are absent.

    In case 1, the expression `precedes` is `True`. In all the other cases
    `precedes` is *absent* as at least one of the variables `a` and `b` is
    absent, and then `precedes` doesn't have a meaning.

    ### Boolean expressions as integer expressions

    Class `BoolExpr` derives from :class:`IntExpr`. Therefore, boolean expressions can be used
    as integer expressions. In this case, `True` is equal to `1`, `False` is
    equal to `0`, and *absent* remains *absent*.
    """

    @staticmethod
    def _wrap(expr: bool | BoolExpr) -> _ScalarArgument: # type: ignore[override]
        """Internal: Convert a bool or BoolExpr to an argument."""
        if isinstance(expr, bool):
            return expr
        if isinstance(expr, BoolExpr): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected BoolExpr or bool. Got {type(expr).__name__}")

    @staticmethod
    def _wrap_list(exprs: Iterable[bool | BoolExpr]) -> _Argument: # type: ignore[override]
        """Internal: Convert a list of bool/BoolExpr to a list of arguments (makes a copy)."""
        return [BoolExpr._wrap(e) for e in exprs]

    def __invert__(self) -> BoolExpr:
        r"""
        Logical NOT using the `~` operator.

        :rtype: BoolExpr
        :returns: A new expression representing the negation.

        ## Details

        Returns a new :class:`BoolExpr` representing `~self` (logical NOT).

        If the operand has value *absent*, the result is also *absent*.

        .. code-block:: python

            model = cp.Model()
            x = model.bool_var(name="x")

            # Negate using ~ operator
            not_x = ~x

            # Use in constraints
            model.enforce(~x)  # x must be False

        **Operator precedence:** In Python, `~` has higher precedence than comparison operators. Use parentheses when combining with comparisons, or use the method/function form:

        .. code-block:: python

            # Wrong: ~a == b parses as (~a) == b
            # Correct ways to negate an equality:
            model.enforce(~(a == b))        # parentheses
            model.enforce((a == b).not_())  # method
            model.enforce(model.not_(a == b))  # function

        .. seealso::

            - :meth:`BoolExpr.not_` and :meth:`Model.not_` for alternatives that avoid precedence issues.
        """
        return BoolExpr(self._model, 'boolNot', [self._as_arg()])

    def __or__(self, other: BoolExpr | bool) -> BoolExpr:
        r"""
        Logical OR using the `|` operator.

        :param other: The expression or constant to OR with.
        :type other: BoolExpr | bool
        :rtype: BoolExpr
        :returns: A new expression representing the disjunction.

        ## Details

        Returns a new :class:`BoolExpr` representing `self | other` (logical OR).

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr | other` calls `__or__`
        - `True | expr` calls `__ror__`

        .. code-block:: python

            model = cp.Model()
            x = model.bool_var(name="x")
            y = model.bool_var(name="y")

            # OR of two expressions
            either = x | y

            # OR with constant
            at_least_x = x | True  # always True

            # Reverse: constant | expression
            also_works = False | x  # equivalent to x

        **Operator precedence:** In Python, `|` has lower precedence than comparison operators but higher than `and_`/`or_`. Use parentheses when combining with comparisons, or use the method/function form:

        .. code-block:: python

            # Wrong: a == b | c == d parses as a == (b | c) == d
            # Correct ways:
            model.enforce((a == b) | (c == d))         # parentheses
            model.enforce((a == b).or_(c == d))        # method
            model.enforce(model.or_(a == b, c == d))   # function

        .. seealso::

            - :meth:`BoolExpr.or_` and :meth:`Model.or_` for alternatives that avoid precedence issues.
        """
        return BoolExpr(self._model, 'boolOr', [self._as_arg(), BoolExpr._wrap(other)])

    def __ror__(self, other: bool) -> BoolExpr:
        r"""
        Reverse logical OR for `constant | expr`.

        :param other: The constant to OR with.
        :type other: bool
        :rtype: BoolExpr
        :returns: A new expression representing the disjunction.

        ## Details

        Called when a constant is on the left: `True | expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`BoolExpr.__or__` for the forward operator.
        """
        return BoolExpr(self._model, 'boolOr', [_wrap_bool(other), self._as_arg()])

    def __and__(self, other: BoolExpr | bool) -> BoolExpr:
        r"""
        Logical AND using the `&` operator.

        :param other: The expression or constant to AND with.
        :type other: BoolExpr | bool
        :rtype: BoolExpr
        :returns: A new expression representing the conjunction.

        ## Details

        Returns a new :class:`BoolExpr` representing `self & other` (logical AND).

        If either operand has value *absent*, the result is also *absent*.

        Both forward and reverse operators are supported:

        - `expr & other` calls `__and__`
        - `True & expr` calls `__rand__`

        .. code-block:: python

            model = cp.Model()
            x = model.bool_var(name="x")
            y = model.bool_var(name="y")

            # AND of two expressions
            both = x & y

            # AND with constant
            must_be_x = x & True  # equivalent to x

            # Reverse: constant & expression
            also_works = True & x  # equivalent to x

        **Operator precedence:** In Python, `&` has lower precedence than comparison operators. Use parentheses when combining with comparisons, or use the method/function form:

        .. code-block:: python

            # Wrong: a == b & c == d parses as a == (b & c) == d
            # Correct ways:
            model.enforce((a == b) & (c == d))          # parentheses
            model.enforce((a == b).and_(c == d))        # method
            model.enforce(model.and_(a == b, c == d))   # function

        .. seealso::

            - :meth:`BoolExpr.and_` and :meth:`Model.and_` for alternatives that avoid precedence issues.
        """
        return BoolExpr(self._model, 'boolAnd', [self._as_arg(), BoolExpr._wrap(other)])

    def __rand__(self, other: bool) -> BoolExpr:
        r"""
        Reverse logical AND for `constant & expr`.

        :param other: The constant to AND with.
        :type other: bool
        :rtype: BoolExpr
        :returns: A new expression representing the conjunction.

        ## Details

        Called when a constant is on the left: `True & expr`.

        If the expression has value *absent*, the result is also *absent*.

        .. seealso::

            - :meth:`BoolExpr.__and__` for the forward operator.
        """
        return BoolExpr(self._model, 'boolAnd', [_wrap_bool(other), self._as_arg()])

    def enforce(self) -> None:
        r"""
        Adds this boolean expression as a constraint to the model.

        This method adds the boolean expression as a constraint to the model. It provides
        a fluent-style alternative to :meth:`Model.enforce`.

        A constraint is satisfied if it is not `False`. In other words, a constraint is
        satisfied if it is `True` or *absent*.

        A boolean expression that is *not* added as a constraint can have
        arbitrary value in a solution (`True`, `False`, or *absent*). Once added
        as a constraint, it can only be `True` or *absent* in the solution.

        ## Example

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.int_var(min=0, max=10, name="x")
            y = model.int_var(min=0, max=10, name="y")

            # Enforce constraint using fluent style
            (x + y <= 15).enforce()

            # Equivalent to:
            # model.enforce(x + y <= 15)

            result = model.solve()

        .. seealso::

            - :meth:`Model.enforce` for the Model-centric style of adding constraints.
            - :class:`BoolExpr` for more about boolean expressions.
        """
        self._model.enforce(self)

    def _reusable_bool_expr(self) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg()]
        return BoolExpr(self._model, "reusableBoolExpr", out_params)

    def not_(self) -> BoolExpr:
        r"""
        Returns negation of the expression.

        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the expression has value *absent* then the resulting expression has also value *absent*.

        Same as :meth:`Model.not_`.
        """
        out_params: list[_Argument] = [self._as_arg()]
        return BoolExpr(self._model, "boolNot", out_params)

    def or_(self, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Returns logical _OR_ of the expression and `arg`.

        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the expression or `arg` has value *absent* then the resulting expression has also value *absent*.

        Same as :meth:`Model.or_`.
        """
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolOr", out_params)

    def and_(self, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Returns logical _AND_ of the expression and `arg`.

        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the expression or `arg` has value *absent*, then the resulting expression has also value *absent*.

        Same as :meth:`Model.and_`.
        """
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolAnd", out_params)

    def implies(self, rhs: BoolExpr | bool) -> BoolExpr:
        r"""
        Returns implication between the expression and `arg`.

        :param rhs: The second boolean expression.
        :type rhs: BoolExpr | bool
        :rtype: BoolExpr
        :returns: The resulting Boolean expression

        ## Details

        If the expression or `arg` has value *absent*, then the resulting expression has also value *absent*.

        Same as :meth:`Model.implies`.
        """
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolImplies", out_params)

    def _eq(self, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolEq", out_params)

    def _ne(self, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolNe", out_params)

    def _nand(self, rhs: BoolExpr | bool) -> BoolExpr:
        out_params: list[_Argument] = [self._as_arg(), BoolExpr._wrap(rhs)]
        return BoolExpr(self._model, "boolNand", out_params)




class CumulExpr(ModelElement):
    r"""
    Cumulative expression.

    Cumulative expression represents resource usage over time.  The resource
    could be a machine, a group of workers, a material, or anything of a limited
    capacity.  The resource usage is not known in advance as it depends on the
    variables of the problem.  Cumulative expressions allow us to model the resource
    usage and constrain it.

    Basic cumulative expressions are:

    * ***Pulse***: the resource is used over an interval of time.
      For example, a pulse can represent a task requiring a certain
      number of workers during its execution.  At the beginning of the interval,
      the resource usage increases by a given amount, and at the end of the
      interval, the resource usage decreases by the same amount.
      Pulse can be created by function :meth:`Model.pulse`
      or :meth:`IntervalVar.pulse`.
    * ***Step***: a given amount of resource is consumed or produced at a specified
      time (e.g., at the start of an interval variable).
      Steps may represent an inventory of a material that is
      consumed or produced by some tasks (a *reservoir*).
      Steps can be created by functions
      :meth:`Model.step_at_start`,
      :meth:`IntervalVar.step_at_start`,
      :meth:`Model.step_at_end`,
      :meth:`IntervalVar.step_at_end`. and
      :meth:`Model.step_at`.

    Cumulative expressions can be combined using operators (`+`, `-`, unary `-`) and
    :meth:`Model.sum`. The resulting cumulative expression represents
    a sum of the resource usage of the combined expressions.

    Cumulative expressions can be constrained using comparison operators (`<=`, `>=`)
    to specify the minimum and maximum allowed resource usage.

    **Limitations:**

    * Pulse-based and step-based cumulative expressions cannot be mixed.
    * Pulses cannot have negative height. Use `-` and unary `-` only with step-based expressions.
    """

    @staticmethod
    def _wrap(expr: CumulExpr) -> _ScalarArgument:
        """Internal: Convert a CumulExpr to an argument."""
        if isinstance(expr, CumulExpr): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected CumulExpr. Got {type(expr).__name__}")

    @staticmethod
    def _wrap_list(exprs: Iterable[CumulExpr]) -> _Argument:
        """Internal: Convert a list of CumulExpr to a list of arguments (makes a copy)."""
        return [CumulExpr._wrap(e) for e in exprs]

    def __add__(self, other: CumulExpr) -> CumulExpr:
        r"""
        Add two cumulative expressions using the `+` operator.

        :param other: The cumulative expression to add.
        :type other: CumulExpr
        :rtype: CumulExpr
        :returns: A new cumulative expression representing the sum.

        ## Details

        Returns a new :class:`CumulExpr` representing `self + other`.

        Use this to combine resource usages from different sources. For example, combining the cumulative usage of two different task types on the same resource.

        **Limitation:** Currently, pulse-based and step-based cumulative expressions cannot be mixed. You can add pulses to pulses and steps to steps, but not pulses to steps.

        .. code-block:: python

            model = cp.Model()
            tasks_a = [model.interval_var(length=5, name=f"a_{i}") for i in range(3)]
            tasks_b = [model.interval_var(length=3, name=f"b_{i}") for i in range(4)]

            # Each task type contributes to resource usage
            cumul_a = model.sum(model.pulse(t, 1) for t in tasks_a)
            cumul_b = model.sum(model.pulse(t, 2) for t in tasks_b)

            # Combined resource usage
            total_usage = cumul_a + cumul_b

            # Limit total capacity
            model.enforce(total_usage <= 5)

        .. seealso::

            - :meth:`Model.sum` for summing multiple cumulative expressions.
        """
        return CumulExpr(self._model, 'cumulPlus', [self._as_arg(), CumulExpr._wrap(other)])

    def __sub__(self, other: CumulExpr) -> CumulExpr:
        r"""
        Subtract one cumulative expression from another using the `-` operator.

        :param other: The cumulative expression to subtract.
        :type other: CumulExpr
        :rtype: CumulExpr
        :returns: A new cumulative expression representing the difference.

        ## Details

        Returns a new :class:`CumulExpr` representing `self - other`.

        **Limitation:** This operator can only be used with step-based cumulative expressions, not with pulses. Pulses cannot have negative height.

        Use this to compute the net effect of additions and removals. For example, tracking inventory where items are added and removed over time.

        .. code-block:: python

            model = cp.Model()
            arrivals = [model.interval_var(length=1, name=f"arrive_{i}") for i in range(3)]
            departures = [model.interval_var(length=1, name=f"depart_{i}") for i in range(3)]

            # Items arrive (step up) and depart (step down)
            arriving = model.step_at(cp.IntervalMin, 0)
            for t in arrivals:
                arriving = arriving + model.step_at_start(t, 1)

            departing = model.step_at(cp.IntervalMin, 0)
            for t in departures:
                departing = departing + model.step_at_start(t, 1)

            # Net inventory level
            inventory = arriving - departing

            # Inventory must stay non-negative
            model.enforce(inventory >= 0)
        """
        return CumulExpr(self._model, 'cumulMinus', [self._as_arg(), CumulExpr._wrap(other)])

    def __neg__(self) -> CumulExpr:
        r"""
        Negate a cumulative expression using the unary `-` operator.

        :rtype: CumulExpr
        :returns: A new cumulative expression representing the negation.

        ## Details

        Returns a new :class:`CumulExpr` representing `-self`.

        **Limitation:** This operator should only be used with step-based cumulative expressions, not with pulses. Pulses cannot have negative height.

        Negating a cumulative expression flips the sign of all its values over time. This is useful when you want to convert resource consumption to resource availability, or vice versa.

        .. code-block:: python

            model = cp.Model()
            tasks = [model.interval_var(length=5, name=f"task_{i}") for i in range(3)]

            # Track consumption using steps (not pulses, since we need negation)
            consumption = model.step_at(cp.IntervalMin, 0)
            for t in tasks:
                consumption = consumption + model.step_at_start(t, 2) + model.step_at_end(t, -2)

            # Available capacity = total - consumption
            total_capacity = model.step_at(cp.IntervalMin, 10)
            available = total_capacity + (-consumption)

            # Ensure we always have some available capacity
            model.enforce(available >= 2)
        """
        return CumulExpr(self._model, 'cumulNeg', [self._as_arg()])

    def __le__(self, other: int | IntExpr) -> Constraint:
        r"""
        Constrain cumulative expression to be at most a capacity using `<=`.

        :param other: The maximum capacity value.
        :type other: int | IntExpr
        :rtype: Constraint
        :returns: A constraint ensuring the cumulative expression never exceeds the capacity.

        ## Details

        Returns a :class:`Constraint` that ensures the cumulative expression is everywhere less than or equal to the given capacity. Use :meth:`Model.enforce` to add this constraint to the model for code clarity.

        Use this to specify the maximum limit of resource usage at any time. For example, to limit the number of workers working simultaneously, or the maximum amount of material in stock.

        **Limitations:**

        - Variable capacity (using `IntExpr`) is only supported for discrete resources (pulses). Reservoir resources (steps) require a constant capacity.
        - The capacity expression must not be optional or absent.

        Both forward and reverse operators are supported:

        - `cumul <= capacity` calls `__le__`
        - `capacity >= cumul` calls `__rge__` (equivalent)

        .. code-block:: python

            model = cp.Model()
            tasks = [model.interval_var(length=10, name=f"task_{i}") for i in range(5)]

            # Each task uses 2 units of a resource
            resource_usage = model.sum(model.pulse(t, 2) for t in tasks)

            # Resource has capacity of 6 units
            model.enforce(resource_usage <= 6)

            # Equivalent using reverse operator:
            # model.enforce(6 >= resource_usage)

        Variable capacity example:

        .. code-block:: python

            model = cp.Model()
            task1 = model.interval_var(length=5, name="task1")
            task2 = model.interval_var(length=10, name="task2")

            # Variable capacity
            extra_capacity = model.int_var(min=0, max=3, name="extra_capacity")
            total_capacity = 4 + extra_capacity

            resource_usage = model.sum([model.pulse(task1, 2), model.pulse(task2, 3)])
            model.enforce(resource_usage <= total_capacity)

            model.minimize(extra_capacity)

        .. seealso::

            - :meth:`CumulExpr.__ge__` for the minimum capacity constraint.
        """
        return Constraint(self._model, 'cumulLe', [self._as_arg(), IntExpr._wrap(other)])

    def __ge__(self, other: int) -> Constraint:
        r"""
        Constrain cumulative expression to be at least a capacity using `>=`.

        :param other: The minimum capacity value.
        :type other: int
        :rtype: Constraint
        :returns: A constraint ensuring the cumulative expression is never below the capacity.

        ## Details

        Returns a :class:`Constraint` that ensures the cumulative expression is everywhere greater than or equal to the given capacity. Use :meth:`Model.enforce` to add this constraint to the model for code clarity.

        **Limitation:** This constraint can only be used with step-based cumulative expressions, not with pulses.

        **Important:** The constraint requires the minimum level to be maintained *everywhere*, including at the beginning of time. If the required level is greater than 0, you must include a step at `IntervalMin` (not at 0) to establish the initial level:

        .. code-block:: python

            model = cp.Model()
            tasks = [model.interval_var(length=5, name=f"task_{i}") for i in range(3)]

            # Track inventory with steps
            inventory = model.step_at(cp.IntervalMin, 10)  # Start with 10 units
            for t in tasks:
                inventory = inventory + model.step_at_start(t, -2)  # Each task consumes 2

            # Inventory must never drop below 2
            model.enforce(inventory >= 2)

        Both forward and reverse operators are supported:

        - `cumul >= capacity` calls `__ge__`
        - `capacity <= cumul` calls `__rle__` (equivalent)

        .. seealso::

            - :meth:`CumulExpr.__le__` for the maximum capacity constraint.
        """
        return Constraint(self._model, 'cumulGe', [self._as_arg(), _wrap_int(other)])

    def __rle__(self, other: int) -> Constraint:
        r"""
        Reverse less-than-or-equal for `capacity <= cumul`.

        :param other: The minimum capacity value.
        :type other: int
        :rtype: Constraint
        :returns: A constraint ensuring the cumulative expression is never below the capacity.

        ## Details

        Called when a constant is on the left: `capacity <= cumul`.

        This is equivalent to `cumul >= capacity`.

        **Limitation:** This constraint can only be used with step-based cumulative expressions, not with pulses.

        **Important:** The constraint requires the minimum level to be maintained *everywhere*, including at the beginning of time. If the required level is greater than 0, you must include a step at `IntervalMin` (not at 0) to establish the initial level.

        .. seealso::

            - :meth:`CumulExpr.__ge__` for the forward operator and examples.
        """
        return Constraint(self._model, 'cumulGe', [self._as_arg(), _wrap_int(other)])

    def __rge__(self, other: int | IntExpr) -> Constraint:
        r"""
        Reverse greater-than-or-equal for `capacity >= cumul`.

        :param other: The maximum capacity value.
        :type other: int | IntExpr
        :rtype: Constraint
        :returns: A constraint ensuring the cumulative expression never exceeds the capacity.

        ## Details

        Called when a constant is on the left: `capacity >= cumul`.

        This is equivalent to `cumul <= capacity`.

        **Limitations:**

        - Variable capacity (using `IntExpr`) is only supported for discrete resources (pulses). Reservoir resources (steps) require a constant capacity.
        - The capacity expression must not be optional or absent.

        .. seealso::

            - :meth:`CumulExpr.__le__` for the forward operator.
        """
        return Constraint(self._model, 'cumulLe', [self._as_arg(), IntExpr._wrap(other)])

    def _cumul_max_profile(self, profile: IntStepFunction) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntStepFunction._wrap(profile)]
        return Constraint(self._model, "cumulMaxProfile", out_params)

    def _cumul_min_profile(self, profile: IntStepFunction) -> Constraint:
        out_params: list[_Argument] = [self._as_arg(), IntStepFunction._wrap(profile)]
        return Constraint(self._model, "cumulMinProfile", out_params)




class _SearchDecision(ModelElement): # type: ignore[reportUnusedClass]
    @staticmethod
    def _wrap(expr: _SearchDecision) -> _ScalarArgument:
        if isinstance(expr, _SearchDecision): # type: ignore[misc]
            return expr._as_arg()
        raise TypeError(f"Expected _SearchDecision. Got {type(expr).__name__}")
    @staticmethod
    def _wrap_list(exprs: Iterable[_SearchDecision]) -> _Argument:
        return [_SearchDecision._wrap(e) for e in exprs]


class _Directive(ModelElement): # type: ignore[reportUnusedClass]
    def __init__(self, model: Model, func: str, args: list[_Argument]):
        super().__init__(model, func, args)
        model._add_directive(self)
