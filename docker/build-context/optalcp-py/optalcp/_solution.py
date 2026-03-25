# Copyright (C) CoEnzyme SAS - All Rights Reserved

"""Solution class for OptalCP."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict, cast, overload

from ._int_bool_var import BoolVar, IntVar
from ._scheduling import IntervalVar

# Type definitions matching JSON sent by the solver.

class _IntervalValue(TypedDict):
    """Value of an interval variable in a serialized solution."""
    start: int
    end: int

class _SolutionVarValue(TypedDict):
    """A single variable value in a serialized solution."""
    id: int
    value: None | int | _IntervalValue

class _SerializedSolution(TypedDict):
    """
    Serialized solution format from the solver.

    Matches TypeScript type SerializedSolution from api.ts.
    """
    values: list[_SolutionVarValue]
    objective: NotRequired[int]

class Solution:
    r"""
    Solution of a :class:`Model`. When a model is solved, the solution is stored
    in this object. The solution contains values of all variables in the model
    (including optional variables) and the value of the objective (if the model
    specified one).

    ### Preview version of OptalCP

    Note that in the preview version of OptalCP, the values of variables in
    the solution are masked and replaced by value *absent* (`None`).
    """

    def __init__(self) -> None:
        r"""
        Creates an empty solution.

        Creates a solution where all variables are absent, and the
        objective value is `None`/`None`.

        Use this constructor to create an external solution that can be passed to
        the solver as a warm start (see :meth:`Model.solve`)
        or sent during solving using :meth:`Solver.send_solution`.

        .. code-block:: python

            import optalcp as cp

            model = cp.Model()
            x = model.interval_var(length=10, name="x")
            model.minimize(x.end())

            # Create an external solution
            solution = cp.Solution()
            solution.set_value(x, 0, 10)  # x starts at 0, ends at 10

            # Use it as a warm start
            result = model.solve({'timeLimit': 60}, solution)
        """
        # The values can be:
        #   - None (absent variable)
        #   - int (IntVar)
        #   - bool (BoolVar)
        #   - tuple[int, int] (IntervalVar: (start, end))
        self._values: dict[int, (None | int | bool | tuple[int, int])] = {}
        self._objective: int | None = None

    def get_objective(self) -> int | None:
        r"""
        Returns the objective value of the solution.

        :rtype: int | None
        :returns: The objective value

        ## Details

        Returns `None` if no objective was specified or if the objective expression
        is *absent* (see optional :class:`IntExpr`).

        The correct value is reported even in the preview version of OptalCP.
        """
        return self._objective

    def is_present(self, variable: IntVar | BoolVar | IntervalVar) -> bool:
        r"""
        Returns `True` if the given variable is present in the solution.

        :param variable: The variable to check
        :type variable: IntVar | BoolVar | IntervalVar
        :rtype: bool
        :returns: True if the variable is present

        ## Details

        In the preview version of OptalCP, this method always returns `False`
        because real values of variables are masked and replaced by value *absent*.
        """
        return variable._get_id() in self._values

    def is_absent(self, variable: IntVar | BoolVar | IntervalVar) -> bool:
        r"""
        Returns `True` if the given variable is absent in the solution.

        :param variable: The variable to check
        :type variable: IntVar | BoolVar | IntervalVar
        :rtype: bool
        :returns: True if the variable is absent

        ## Details

        In the preview version of OptalCP, this method always returns `True`
        because real values of variables are masked and replaced by value *absent*.
        """
        return variable._get_id() not in self._values

    @overload
    def get_value(self, variable: IntVar) -> int | None:
        r"""
        Gets an integer variable's value from the solution.

        :param variable: The integer variable to get the value of
        :type variable: IntVar
        :rtype: int | None
        :returns: The value, or None if the variable is absent
        """
        ...

    @overload
    def get_value(self, variable: BoolVar) -> bool | None:
        r"""
        Gets a boolean variable's value from the solution.

        :param variable: The boolean variable to get the value of
        :type variable: BoolVar
        :rtype: bool | None
        :returns: The value, or None if the variable is absent
        """
        ...

    @overload
    def get_value(self, variable: IntervalVar) -> tuple[int, int] | None:
        r"""
        Gets an interval variable's start and end from the solution.

        :param variable: The interval variable to get the value of
        :type variable: IntervalVar
        :rtype: tuple[int, int] | None
        :returns: A tuple (start, end), or None if the interval is absent
        """
        ...

    def get_value(self, variable: IntVar | BoolVar | IntervalVar) -> int | bool | tuple[int, int] | None:  # type: ignore[misc]

        result = self._values.get(variable._get_id())
        if isinstance(variable, BoolVar):
            # Solver sends bools as 0/1 integers
            return None if result is None else bool(result)
        if not isinstance(variable, (IntVar, IntervalVar)): # type: ignore[misc]
            raise TypeError(f"Expected IntVar, BoolVar, or IntervalVar, got {type(variable).__name__}")
        return result

    def get_start(self, variable: IntervalVar) -> int | None:
        r"""
        Gets an interval variable's start time from the solution.

        :param variable: The interval variable to query
        :type variable: IntervalVar
        :rtype: int | None
        :returns: The start value, or None if absent

        ## Details

        If the variable is *absent* in the solution, it returns `None`.

        In the preview version of OptalCP, this function always returns `None`
        because real values of variables are masked and replaced by value *absent*.
        """
        if not isinstance(variable, IntervalVar): # type: ignore[misc]
            raise TypeError(f"Expected IntervalVar, got {type(variable).__name__}")

        value = self._values.get(variable._get_id())
        if value is None:
            return None
        return cast(tuple[int, int], value)[0]

    def get_end(self, variable: IntervalVar) -> int | None:
        r"""
        Gets an interval variable's end time from the solution.

        :param variable: The interval variable to query
        :type variable: IntervalVar
        :rtype: int | None
        :returns: The end value, or None if absent

        ## Details

        If the variable is *absent* in the solution, it returns `None`.

        In the preview version of OptalCP, this function always returns `None`
        because real values of variables are masked and replaced by value *absent*.
        """
        if not isinstance(variable, IntervalVar): # type: ignore[misc]
            raise TypeError(f"Expected IntervalVar, got {type(variable).__name__}")

        value = self._values.get(variable._get_id())
        if value is None:
            return None
        return cast(tuple[int, int], value)[1]

    def get_length(self, variable: IntervalVar) -> int | None:
        r"""
        Gets an interval variable's length from the solution.

        :param variable: The interval variable to query
        :type variable: IntervalVar
        :rtype: int | None
        :returns: The length value, or None if absent

        ## Details

        If the variable is *absent* in the solution, it returns `None`.

        In the preview version of OptalCP, this function always returns `None`
        because real values of variables are masked and replaced by value *absent*.
        """
        if not isinstance(variable, IntervalVar): # type: ignore[misc]
            raise TypeError(f"Expected IntervalVar, got {type(variable).__name__}")

        value = self._values.get(variable._get_id())
        if value is None:
            return None
        interval = cast(tuple[int, int], value)
        return interval[1] - interval[0]

    def set_objective(self, value: int | None) -> None:
        r"""
        Sets objective value of the solution.

        :param value: The objective value to set
        :type value: int | None

        ## Details

        This function can be used for construction of an external solution that can be
        passed to the solver (see :meth:`Model.solve`, :class:`Solver` and
        :meth:`Solver.send_solution`).
        """
        self._objective = value

    @overload
    def set_value(self, variable: IntVar, value: int) -> None:
        r"""
        Sets the value of the given integer variable in the solution.

        :param variable: The integer variable
        :type variable: IntVar
        :param value: The value to set
        :type value: int

        ## Details

        The variable will be present in the solution with the given value.

        .. seealso::

            - :meth:`Solution.set_absent` to make the variable absent.
        """
        ...

    @overload
    def set_value(self, variable: BoolVar, value: bool) -> None:
        r"""
        Sets the value of the given boolean variable in the solution.

        :param variable: The boolean variable
        :type variable: BoolVar
        :param value: The value to set (True or False)
        :type value: bool

        ## Details

        The variable will be present in the solution with the given value.

        .. seealso::

            - :meth:`Solution.set_absent` to make the variable absent.
        """
        ...

    @overload
    def set_value(self, variable: IntervalVar, start: int, end: int) -> None:
        r"""
        Sets the start and end of the given interval variable in the solution.

        :param variable: The interval variable
        :type variable: IntervalVar
        :param start: The start time
        :type start: int
        :param end: The end time
        :type end: int

        ## Details

        The interval variable will be present in the solution with the given start and end.

        .. seealso::

            - :meth:`Solution.set_absent` to make the variable absent.
        """
        ...

    def set_value(self, variable: IntVar | BoolVar | IntervalVar, *args: Any) -> None:  # type: ignore[misc]
        if isinstance(variable, IntervalVar):
            if len(args) != 2:
                raise ValueError("IntervalVar requires start and end: set_value(var, start, end)")
            start, end = args
            if not isinstance(start, int) or not isinstance(end, int):
                raise TypeError("IntervalVar start and end must be integers")
            self._values[variable._get_id()] = (start, end)
        elif isinstance(variable, BoolVar):
            if len(args) != 1:
                raise ValueError("BoolVar requires a single value: set_value(var, value)")
            value = args[0]
            if not isinstance(value, bool):
                raise TypeError("BoolVar value must be a boolean")
            self._values[variable._get_id()] = value
        elif isinstance(variable, IntVar): # type: ignore[misc]
            if len(args) != 1:
                raise ValueError("IntVar requires a single value: set_value(var, value)")
            value = args[0]
            if not isinstance(value, int):
                raise TypeError("IntVar value must be an integer")
            self._values[variable._get_id()] = value
        else:
            raise TypeError(f"Unknown variable type: {type(variable).__name__}")

    def set_absent(self, variable: IntVar | BoolVar | IntervalVar) -> None:
        r"""
        Sets the given variable to be absent in the solution.

        :param variable: The variable to set as absent
        :type variable: IntVar | BoolVar | IntervalVar

        ## Details

        This function can be used for construction of an external solution that can be
        passed to the solver (see :meth:`Model.solve` and :meth:`Solver.send_solution`).
        """
        if (not isinstance(variable, (IntVar, BoolVar, IntervalVar))): # type: ignore[misc]
            raise TypeError(f"Expected IntVar, BoolVar, or IntervalVar, got {type(variable).__name__}")

        # Remove from dict entirely
        self._values.pop(variable._get_id(), None)

    def _init_from_dict(self, data: _SerializedSolution) -> None:
        """
        Initialize solution from solver message data.

        Internal method used to deserialize solutions from the solver.

        Args:
            data: Serialized solution from solver containing 'values' and 'objective'.
        """
        # Parse values array from solver
        # Format: [{"id": 0, "value": ...}, ...]
        # value can be: null, number (int/bool), or {"start": ..., "end": ...}

        values_list = data.get('values', [])
        for item in values_list:
            var_id = item['id']
            value = item['value']

            if value is None:
                # Absent variable, don't store in dict
                pass
            elif isinstance(value, dict) and 'start' in value:
                # Convert IntervalVar dict to tuple for Pythonic API
                self._values[var_id] = (value['start'], value['end'])
            else:
                # Everything else (None, int, bool) - store as-is
                self._values[var_id] = value

        # Parse objective
        self._objective = data.get('objective')

    def _to_dict(self) -> _SerializedSolution:
        """
        Serialize solution to dictionary for warm start.

        Internal method used to serialize solutions for the solver.

        Returns:
            Serialized solution with 'values' and 'objective' keys.
        """
        values_list: list[_SolutionVarValue] = []

        for var_id, value in self._values.items():
            if value is None:
                # Absent variable, no need to include it
                pass
            elif isinstance(value, tuple) and len(value) == 2: # type: ignore[misc]
                # IntervalVar - convert tuple to dict
                interval_val: _IntervalValue = {"start": value[0], "end": value[1]}
                values_list.append({"id": var_id, "value": interval_val})
            elif isinstance(value, bool):
                # BoolVar - convert to 0/1 for solver
                values_list.append({"id": var_id, "value": 1 if value else 0})
            else:
                # IntVar - store as-is
                values_list.append({"id": var_id, "value": value})

        result: _SerializedSolution = {"values": values_list}
        if self._objective is not None:
            result["objective"] = self._objective

        return result

    def __repr__(self) -> str:
        """String representation of the solution."""
        present_vars = len(self._values)
        obj_str = f", objective={self._objective}" if self._objective is not None else ""
        return f"Solution({present_vars} present{obj_str})"
