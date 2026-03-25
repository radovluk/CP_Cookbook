"""
OptalCP Python API

A Pythonic interface to the OptalCP constraint programming solver.
"""

from __future__ import annotations

__version__: str = '2026.1.0'

# Import main classes
from ._model import Model as Model
from ._expressions import (
    ModelElement as ModelElement,
    IntExpr as IntExpr,
    BoolExpr as BoolExpr,
    Constraint as Constraint,
    CumulExpr as CumulExpr,
    Objective as Objective,
)

from ._int_bool_var import IntVar as IntVar, BoolVar as BoolVar
from ._scheduling import IntervalVar as IntervalVar, SequenceVar as SequenceVar, IntStepFunction as IntStepFunction

# Import constants
from ._constants import (
    IntVarMax as IntVarMax,
    IntVarMin as IntVarMin,
    IntervalMax as IntervalMax,
    IntervalMin as IntervalMin,
    LengthMax as LengthMax,
)

# Import parameters
from ._parameters import (
    Parameters as Parameters,
    WorkerParameters as WorkerParameters,
    copy_parameters as copy_parameters,
    merge_parameters as merge_parameters,
    parse_parameters as parse_parameters,
    parse_known_parameters as parse_known_parameters,
)

# Import solver result types and functions
from ._result import (
    SolveResult as SolveResult,
    ObjectiveEntry as ObjectiveEntry,
    ObjectiveBoundEntry as ObjectiveBoundEntry,
    SolveSummary as SolveSummary,
)
from ._solver import (
    Solver as Solver,
    SolutionEvent as SolutionEvent,
)
from ._solution import Solution as Solution


__all__: list[str] = [
    # Main classes
    'Model',
    'ModelElement',
    'IntVar',
    'BoolVar',
    'IntervalVar',
    'IntExpr',
    'BoolExpr',
    'Constraint',
    'CumulExpr',
    'Objective',
    'SequenceVar',
    'IntStepFunction',
    # Constants
    'IntVarMax',
    'IntVarMin',
    'IntervalMax',
    'IntervalMin',
    'LengthMax',
    # Parameters
    'Parameters',
    'WorkerParameters',
    'copy_parameters',
    'merge_parameters',
    'parse_parameters',
    'parse_known_parameters',
    # Solver
    'Solver',
    'SolveResult',
    'Solution',
    'SolutionEvent',
    'ObjectiveEntry',
    'ObjectiveBoundEntry',
    'SolveSummary',
]
