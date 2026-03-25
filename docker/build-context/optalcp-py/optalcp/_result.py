"""
Result type definitions.

This module provides type definitions for solve results and summaries.
The actual solving implementation is in _solver.py (Solver class).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NotRequired, final

from typing_extensions import TypedDict

from ._model import Model
from ._parameters import Parameters, _parameters_from_json, _parameters_to_json
from ._solution import Solution


@final
@dataclass(frozen=True, slots=True)
class ObjectiveEntry:
    r"""
    Single entry in the objective value history.

    Tracks when each improving solution was found during the solve, along with
    its objective value and validation status.

    There is one entry for each solution found. The entries are ordered by
    solve time.

    .. seealso::

        - :attr:`SolveResult.objective_history` for accessing the history.
    """

    solve_time: float
    r"""
    Duration of the solve when this solution was found, in seconds.

    :rtype: float
    :returns: Seconds elapsed.
    """

    objective: int | None
    r"""
    The objective value of this solution.

    :rtype: int | None
    :returns: The objective value, or None if not applicable.

    ## Details

    The value is `None` when:

    - No objective was specified in the model (no :meth:`Model.minimize` or :meth:`Model.maximize` call).
    - The objective expression has an absent value in this solution.
    """

    valid: bool | None = None
    r"""
    Whether this solution was verified (if verification is enabled).

    :rtype: bool | None
    :returns: True if verified, None if not verified.

    ## Details

    When parameter :attr:`Parameters.verifySolutions` is set to `True` (the
    default), the solver verifies all solutions found. The verification checks
    that all constraints in the model are satisfied and that the objective value
    is computed correctly.

    The verification is done using separate code (not used during the search).
    The point is to independently verify the correctness of the solution.

    Possible values are:

    - `None` - the solution was not verified (because the parameter
       :attr:`Parameters.verifySolutions` was not set).
    - `True` - the solution was verified and correct.

    The value can never be `False` because, in this case, the solver would
    stop with an error.
    """


@final
@dataclass(frozen=True, slots=True)
class ObjectiveBoundEntry:
    r"""
    Single entry in the objective bound history.

    Tracks when a new (better) bound on the objective was proved, along with
    the solve time and bound value. For minimization problems, this is the
    lower bound; for maximization, the upper bound.

    .. seealso::

        - :attr:`SolveResult.objective_bound_history` for accessing the history.
    """

    solve_time: float
    r"""
    Duration of the solve at the time the bound was found, in seconds.

    :rtype: float
    :returns: Seconds elapsed.
    """

    value: int
    r"""
    The new bound value.

    :rtype: int
    :returns: Bound value.

    ## Details

    For minimization problems, this is a lower bound on the objective.
    For maximization problems, this is an upper bound on the objective.
    """


@final
class _RawSolveSummary(TypedDict):
    """
    Internal: Raw summary statistics from solver (camelCase wire format).

    This matches the JSON format from the solver and is used internally.
    Users receive the snake_case SolveSummary version instead.

    Most fields are required, matching TypeScript SolveSummary.
    Only objective, lowerBound, and objectiveSense are optional.
    """
    # Core results (required)
    nbSolutions: int
    proof: bool
    duration: float

    # Search statistics (required)
    nbBranches: int
    nbFails: int
    nbLNSSteps: int
    nbRestarts: int

    # Resource usage (required)
    memoryUsed: int

    # Objective information (optional - only present for optimization problems)
    objective: NotRequired[int]
    lowerBound: NotRequired[int]
    objectiveSense: NotRequired[str]

    # Model statistics (required)
    nbIntVars: int
    nbIntervalVars: int
    nbConstraints: int

    # Environment information (required)
    solver: str
    nbWorkers: int
    cpu: str


@final
class SolveSummary:
    r"""
    Summary statistics from the solver at completion.

    Contains statistics about the solve including the number of solutions found,
    the total duration, search statistics (branches, fails, restarts), and
    information about the model and environment.

    This class is passed to the `on_summary` callback. For a richer interface
    with additional tracking data (solution history, objective bounds history),
    see :class:`SolveResult`.
    """

    def __init__(self, data: _RawSolveSummary):
        self._data = data

    @property
    def nb_solutions(self) -> int:
        r"""
        Number of solutions found during the solve.

        :rtype: int
        :returns: Solution count.
        """
        return self._data['nbSolutions']

    @property
    def proof(self) -> bool:
        r"""
        Whether the solve ended with a proof (optimality or infeasibility).

        :rtype: bool
        :returns: True if the solve completed with a proof.

        ## Details

        When `True`, the solver has either:

        - Proved optimality (found a solution within the bounds defined by
           :attr:`Parameters.absoluteGapTolerance` and :attr:`Parameters.relativeGapTolerance`), or
        - Proved infeasibility (no solution exists)

        When `False`, the solve was interrupted (e.g., by time limit) before
        a proof could be established.
        """
        return self._data['proof']

    @property
    def duration(self) -> float:
        r"""
        Total duration of the solve in seconds.

        :rtype: float
        :returns: Seconds elapsed.
        """
        return self._data['duration']

    @property
    def nb_branches(self) -> int:
        r"""
        Total number of branches explored during the solve.

        :rtype: int
        :returns: Branch count.
        """
        return self._data['nbBranches']

    @property
    def nb_fails(self) -> int:
        r"""
        Total number of failures encountered during the solve.

        :rtype: int
        :returns: Failure count.
        """
        return self._data['nbFails']

    @property
    def nb_lns_steps(self) -> int:
        r"""
        Total number of Large Neighborhood Search steps.

        :rtype: int
        :returns: LNS step count.
        """
        return self._data['nbLNSSteps']

    @property
    def nb_restarts(self) -> int:
        r"""
        Total number of restarts performed during the solve.

        :rtype: int
        :returns: Restart count.
        """
        return self._data['nbRestarts']

    @property
    def memory_used(self) -> int:
        r"""
        Memory used by the solver in bytes.

        :rtype: int
        :returns: Bytes used.
        """
        return self._data['memoryUsed']

    @property
    def objective(self) -> int | None:
        r"""
        Best objective value found (for optimization problems).

        :rtype: int | None
        :returns: The objective value, or None if not applicable.

        ## Details

        The value is `None` when:

        - No objective was specified in the model (no :meth:`Model.minimize` or :meth:`Model.maximize` call).
        - No solution was found.
        - The objective expression has an absent value in the best solution.
        """
        return self._data.get('objective')

    @property
    def objective_bound(self) -> int | None:
        r"""
        Proved bound on the objective value.

        :rtype: int | None
        :returns: The objective bound, or None if no bound was proved.

        ## Details

        For minimization problems, this is a lower bound: the solver proved that
        no solution exists with an objective value less than this bound.

        For maximization problems, this is an upper bound: the solver proved that
        no solution exists with an objective value greater than this bound.

        The value is `None` when no bound was proved or for satisfaction problems.
        """
        return self._data.get('lowerBound')

    @property
    def objective_sense(self) -> str | None:
        r"""
        Objective direction.

        :rtype: str | None
        :returns: 'minimize', 'maximize', or None for satisfaction problems.

        ## Details

        Indicates whether the model was a minimization problem, maximization problem,
        or a satisfaction problem (no objective).
        """
        return self._data.get('objectiveSense')

    @property
    def nb_int_vars(self) -> int:
        r"""
        Number of integer variables in the model.

        :rtype: int
        :returns: Integer variable count.
        """
        return self._data['nbIntVars']

    @property
    def nb_interval_vars(self) -> int:
        r"""
        Number of interval variables in the model.

        :rtype: int
        :returns: Interval variable count.
        """
        return self._data['nbIntervalVars']

    @property
    def nb_constraints(self) -> int:
        r"""
        Number of constraints in the model.

        :rtype: int
        :returns: Constraint count.
        """
        return self._data['nbConstraints']

    @property
    def solver(self) -> str:
        r"""
        Solver name and version string.

        :rtype: str
        :returns: The solver identification string.

        ## Details

        Contains the solver name followed by its version number.
        """
        return self._data['solver']

    @property
    def actual_workers(self) -> int:
        r"""
        Number of worker threads actually used during solving.

        :rtype: int
        :returns: Worker count.

        ## Details

        This is the actual number of workers used by the solver, which may differ
        from the requested :attr:`Parameters.nbWorkers` if that parameter was not
        specified (auto-detect) or if the system has fewer cores than requested.
        """
        return self._data['nbWorkers']

    @property
    def cpu(self) -> str:
        r"""
        CPU name detected by the solver.

        :rtype: str
        :returns: CPU model name.

        ## Details

        Contains the CPU model name as detected by the operating system.
        """
        return self._data['cpu']

    def __repr__(self) -> str:
        if self.nb_solutions > 0:
            obj_str = f", objective={self.objective}" if self.objective is not None else ""
            return f"<SolveSummary: {self.nb_solutions} solution(s){obj_str}, duration={self.duration:.2f}s>"
        else:
            return f"<SolveSummary: no solution, proof={self.proof}, duration={self.duration:.2f}s>"


class SolveResult:
    r"""
    The result returned by :meth:`Model.solve` or :meth:`Solver.solve`.

    Contains comprehensive information about the solve:

    **Solution data:**

    - :attr:`SolveResult.solution`: The best solution found (or `None` if no solution exists)
    - :attr:`SolveSummary.objective`: The objective value of the best solution
    - :attr:`SolveSummary.objective_bound`: The proved bound on the objective

    **Solve statistics:**

    - :attr:`SolveSummary.nb_solutions`: Total number of solutions found
    - :attr:`SolveSummary.proof`: Whether optimality or infeasibility was proved
    - :attr:`SolveSummary.duration`: Total solve time in seconds

    **History tracking:**

    - :attr:`SolveResult.objective_history`: When each improving solution was found
    - :attr:`SolveResult.objective_bound_history`: When each bound improvement was proved

    ## Example

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build model ...

        result = model.solve()

        if result.solution is not None:
            print(f"Found solution with objective {result.objective}")
            print(f"Best solution found at {result.solution_time:.2f}s")
            if result.proof:
                print("Solution is optimal!")
        else:
            if result.proof:
                print("Problem is infeasible")
            else:
                print("No solution found within time limit")
    """

    def __init__(self, data: _RawSolveSummary,
                 solution: Solution | None = None,
                 objective_history: list[ObjectiveEntry] | None = None,
                 objective_bound_history: list[ObjectiveBoundEntry] | None = None,
                 solution_time: float | None = None,
                 bound_time: float | None = None,
                 solution_valid: bool | None = None):
        self._data = data
        self._solution = solution
        self._objective_history = objective_history if objective_history is not None else []
        self._objective_bound_history = objective_bound_history if objective_bound_history is not None else []
        self._solution_time = solution_time
        self._bound_time = bound_time
        self._solution_valid = solution_valid

    @property
    def nb_solutions(self) -> int:
        r"""
        Number of solutions found during the solve.

        :rtype: int
        :returns: Solution count.
        """
        return self._data['nbSolutions']

    @property
    def proof(self) -> bool:
        r"""
        Whether the solve ended with a proof (optimality or infeasibility).

        :rtype: bool
        :returns: True if the solve completed with a proof.

        ## Details

        When `True`, the solver has either:

        - Proved optimality (found a solution within the bounds defined by
           :attr:`Parameters.absoluteGapTolerance` and :attr:`Parameters.relativeGapTolerance`), or
        - Proved infeasibility (no solution exists)

        When `False`, the solve was interrupted (e.g., by time limit) before
        a proof could be established.
        """
        return self._data['proof']

    @property
    def duration(self) -> float:
        r"""
        Total duration of the solve in seconds.

        :rtype: float
        :returns: Seconds elapsed.
        """
        return self._data['duration']

    @property
    def nb_branches(self) -> int:
        r"""
        Total number of branches explored during the solve.

        :rtype: int
        :returns: Branch count.
        """
        return self._data['nbBranches']

    @property
    def nb_fails(self) -> int:
        r"""
        Total number of failures encountered during the solve.

        :rtype: int
        :returns: Failure count.
        """
        return self._data['nbFails']

    @property
    def objective(self) -> int | None:
        r"""
        Best objective value found (for optimization problems).

        :rtype: int | None
        :returns: The objective value, or None if not applicable.

        ## Details

        The value is `None` when:

        - No objective was specified in the model (no :meth:`Model.minimize` or :meth:`Model.maximize` call).
        - No solution was found.
        - The objective expression has an absent value in the best solution.
        """
        return self._data.get('objective')

    @property
    def objective_bound(self) -> int | None:
        r"""
        Proved bound on the objective value.

        :rtype: int | None
        :returns: The objective bound, or None if no bound was proved.

        ## Details

        For minimization problems, this is a lower bound: the solver proved that
        no solution exists with an objective value less than this bound.

        For maximization problems, this is an upper bound: the solver proved that
        no solution exists with an objective value greater than this bound.

        The value is `None` when no bound was proved or for satisfaction problems.
        """
        return self._data.get('lowerBound')

    @property
    def solution(self) -> Solution | None:
        r"""
        The best solution found during the solve.

        :rtype: Solution | None
        :returns: The best solution, or None if no solution was found.

        ## Details

        For optimization problems, this is the solution with the best objective value.
        For satisfaction problems, this is the last solution found.

        Returns `None` when no solution was found (the problem may be infeasible
        or the solve was interrupted before finding any solution).
        """
        return self._solution

    @property
    def nb_lns_steps(self) -> int:
        r"""
        Total number of Large Neighborhood Search steps.

        :rtype: int
        :returns: LNS step count.
        """
        return self._data['nbLNSSteps']

    @property
    def nb_restarts(self) -> int:
        r"""
        Total number of restarts performed during the solve.

        :rtype: int
        :returns: Restart count.
        """
        return self._data['nbRestarts']

    @property
    def memory_used(self) -> int:
        r"""
        Memory used by the solver in bytes.

        :rtype: int
        :returns: Bytes used.
        """
        return self._data['memoryUsed']

    @property
    def nb_int_vars(self) -> int:
        r"""
        Number of integer variables in the model.

        :rtype: int
        :returns: Integer variable count.
        """
        return self._data['nbIntVars']

    @property
    def nb_interval_vars(self) -> int:
        r"""
        Number of interval variables in the model.

        :rtype: int
        :returns: Interval variable count.
        """
        return self._data['nbIntervalVars']

    @property
    def nb_constraints(self) -> int:
        r"""
        Number of constraints in the model.

        :rtype: int
        :returns: Constraint count.
        """
        return self._data['nbConstraints']

    @property
    def solver(self) -> str:
        r"""
        Solver name and version string.

        :rtype: str
        :returns: The solver identification string.

        ## Details

        Contains the solver name followed by its version number.
        """
        return self._data['solver']

    @property
    def actual_workers(self) -> int:
        r"""
        Number of worker threads actually used during solving.

        :rtype: int
        :returns: Worker count.

        ## Details

        This is the actual number of workers used by the solver, which may differ
        from the requested :attr:`Parameters.nbWorkers` if that parameter was not
        specified (auto-detect) or if the system has fewer cores than requested.
        """
        return self._data['nbWorkers']

    @property
    def cpu(self) -> str:
        r"""
        CPU name detected by the solver.

        :rtype: str
        :returns: CPU model name.

        ## Details

        Contains the CPU model name as detected by the operating system.
        """
        return self._data['cpu']

    @property
    def objective_sense(self) -> str | None:
        r"""
        Objective direction.

        :rtype: str | None
        :returns: 'minimize', 'maximize', or None for satisfaction problems.

        ## Details

        Indicates whether the model was a minimization problem, maximization problem,
        or a satisfaction problem (no objective).
        """
        return self._data.get('objectiveSense')

    @property
    def objective_history(self) -> Sequence[ObjectiveEntry]:
        r"""
        History of objective value improvements during the solve.

        :rtype: Sequence[ObjectiveEntry]
        :returns: Sequence of objective entries, one per solution found.

        ## Details

        Returns a sequence of :class:`ObjectiveEntry` objects, one for each solution
        found during the solve.

        Each entry contains:

        - :attr:`ObjectiveEntry.solve_time`: When the solution was found
        - :attr:`ObjectiveEntry.objective`: The objective value of that solution
        - :attr:`ObjectiveEntry.valid`: Whether the solution was verified

        The entries are ordered chronologically by solve time.
        """
        return self._objective_history

    @property
    def objective_bound_history(self) -> Sequence[ObjectiveBoundEntry]:
        r"""
        History of objective bound improvements during the solve.

        :rtype: Sequence[ObjectiveBoundEntry]
        :returns: Sequence of bound entries, one per bound improvement.

        ## Details

        Returns a sequence of :class:`ObjectiveBoundEntry` objects, one for each
        bound improvement proved during the solve.

        Each entry contains:

        - :attr:`ObjectiveBoundEntry.solve_time`: When the bound was proved
        - :attr:`ObjectiveBoundEntry.value`: The bound value

        For minimization problems, these are lower bounds. For maximization problems,
        these are upper bounds. The entries are ordered chronologically by solve time.
        """
        return self._objective_bound_history

    @property
    def solution_time(self) -> float | None:
        r"""
        Time when the best solution was found.

        :rtype: float | None
        :returns: The time in seconds, or None if no solution was found.

        ## Details

        The time is measured from the start of the solve, in seconds.

        Returns `None` when no solution was found.
        """
        return self._solution_time

    @property
    def bound_time(self) -> float | None:
        r"""
        Time of the last objective bound improvement.

        :rtype: float | None
        :returns: The time in seconds, or None if no bound was proved.

        ## Details

        The time is measured from the start of the solve, in seconds.

        Returns `None` when no bound was proved during the solve.
        """
        return self._bound_time

    @property
    def solution_valid(self) -> bool | None:
        r"""
        Whether the best solution was verified.

        :rtype: bool | None
        :returns: True if verified, None if verification was not performed.

        ## Details

        When parameter :attr:`Parameters.verifySolutions` is set to `True` (the
        default), the solver verifies all solutions found. The verification checks
        that all constraints in the model are satisfied and that the objective value
        is computed correctly.

        Possible values:

        - `None` - verification was not performed (parameter was not set)
        - `True` - the solution was verified and correct

        The value can never be `False` because, in that case, the solver would
        stop with an error.
        """
        return self._solution_valid

    def __repr__(self) -> str:
        if self.nb_solutions > 0:
            obj_str = f", objective={self.objective}" if self.objective is not None else ""
            return f"<SolveResult: {self.nb_solutions} solution(s){obj_str}, duration={self.duration:.2f}s>"
        else:
            return f"<SolveResult: no solution, proof={self.proof}, duration={self.duration:.2f}s>"


def _to_json_impl(model: Model,
                  params: Parameters | None = None,
                  warm_start: Solution | None = None) -> str:
    """Internal implementation for Model.to_json()."""
    model_data = model._to_dict()

    if params is not None:
        model_data['parameters'] = _parameters_to_json(params)

    if warm_start is not None:
        model_data['warmStart'] = warm_start._to_dict()  # JSON uses camelCase

    # Return string (not bytes) for easier file writing
    return json.dumps(model_data)


def _from_json_impl(json_str: str) -> tuple[Model, Parameters | None, Solution | None]:
    """Internal implementation for Model.from_json()."""
    data = json.loads(json_str)

    # Deserialize model
    model = Model()
    model._from_dict(data)

    # Deserialize parameters if present
    params: Parameters | None = None
    if 'parameters' in data:
        params = _parameters_from_json(data['parameters'])

    # Deserialize warm start if present
    warm_start: Solution | None = None
    if 'warmStart' in data:
        warm_start = Solution()
        warm_start._init_from_dict(data['warmStart'])

    return (model, params, warm_start)
