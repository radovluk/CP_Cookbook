"""
Solver parameters.

Parameters control solver behavior including time limits, search strategies,
number of workers, and worker-specific settings.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import IO, Any, Literal, cast

from typing_extensions import TypedDict


class WorkerParameters(TypedDict, total=False):
    r"""
    WorkerParameters specify the behavior of each worker separately.
    It is part of the :class:`Parameters` object.

    If a parameter is not listed here, then it can be set only globally (in :class:`Parameters`), not per worker.  For example, *timeLimit* or *logPeriod* are
    global parameters.
    """

    searchType: Literal['Auto', 'LNS', 'FDS', 'FDSDual', 'SetTimes', 'FDSLB']
    r"""
    Type of search to use

    This parameter controls which search algorithm the solver uses. Different search types have different strengths:

    - `Auto`: Automatically determined based on the :attr:`Parameters.preset` (the default). With the `Default` preset, workers are distributed across LNS, FDS, and FDSDual. With the `Large` preset, all workers use LNS.

    - `LNS`: Large Neighborhood Search. Starts from an initial solution and iteratively improves it by relaxing and re-optimizing parts of the solution. Good for finding high-quality solutions quickly, especially on large problems. Works best when a good initial solution can be found.

    - `FDS`: Failure-Directed Search. A systematic search that learns from failures to guide exploration. Uses restarts with no-good learning. Often effective at proving optimality and works well with strong propagation.

    - `FDSDual`: Failure-Directed Search working on objective bounds. Similar to FDS but focuses on proving bounds on the objective value. Useful for optimization problems where you want to know how far from optimal your solutions are.

    - `SetTimes`: Depth-first set-times search (not restarted). A simple chronological search that assigns start times in order. Can be effective for tightly constrained problems but generally less robust than other methods.

    **Interaction with presets:**

    When `searchType` is set to `Auto`, the actual search type is determined by the :attr:`Parameters.preset`:

    - `Default` preset: Distributes workers across different search types. Half use LNS, 3/8 use FDS, and the rest use FDSDual. This portfolio approach provides robustness across different problem types.

    - `Large` preset: All workers use LNS. For very large problems, the overhead of systematic search methods like FDS becomes prohibitive, so LNS is used exclusively.

    If you explicitly set `searchType` to a specific value (not `Auto`), that value is used regardless of the preset.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model ...

        # Let the preset decide (default behavior)
        result = model.solve()

        # Or explicitly use FDS for systematic search
        result = model.solve(searchType="FDS")

        # Or use LNS for quick solutions on large problems
        result = model.solve(searchType="LNS")

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of search and propagation.
        - :attr:`Parameters.noOverlapPropagationLevel` which works well with FDS at higher levels.
    """

    randomSeed: int
    r"""
    Random seed

    The solver breaks ties randomly using a pseudorandom number generator. This parameter sets the seed of the generator.

    Note that when :attr:`Parameters.nbWorkers` is more than 1 then there is also another source of randomness: the time it takes for a message to pass from one worker to another. Therefore with 1 worker the solver is deterministic (random behavior depends only on random seed). With more workers the solver is not deterministic.

    Even with the same random seed, the solver may behave differently on different platforms. This can be due to different implementations of certain functions such as `std::sort`.

    The parameter takes an integer value.

    The default value is `1`.
    """

    _workerFailLimit: int
    _workerBranchLimit: int
    _workerSolutionLimit: int
    _workerLNSStepLimit: int
    _workerRestartLimit: int
    noOverlapPropagationLevel: int
    r"""
    How much to propagate noOverlap constraints

    This parameter controls the amount of propagation done for noOverlap constraints. Higher levels use more sophisticated algorithms that can detect more infeasibilities and prune more values from domains, but at the cost of increased computation time.

    **Propagation levels:**

    - Level 1: Basic timetable propagation only
    - Level 2: Adds detectable precedences algorithm
    - Level 3: Adds edge-finding reasoning
    - Level 4: Maximum propagation with all available algorithms

    **Automatic selection (level 0):**

    When set to 0 (the default), the propagation level is determined automatically based on the :attr:`Parameters.preset`:

    - `Default` preset: Uses level 4 (maximum propagation)
    - `Large` preset: Uses level 1 (minimum propagation for scalability)

    **Performance considerations:**

    More propagation doesn't necessarily mean better overall performance. The trade-off depends on your problem:

    - **Dense scheduling problems** with many overlapping intervals often benefit from higher propagation levels because the extra pruning reduces the search space significantly.

    - **Sparse problems** or **very large problems** may perform better with lower propagation levels because the overhead of sophisticated algorithms outweighs the benefit.

    - **FDS search** (see :attr:`Parameters.searchType`) typically benefits from higher propagation levels because it relies on strong propagation to guide the search.

    If you're unsure, start with the automatic selection (level 0) and let the preset choose. You can then experiment with explicit levels if needed.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model with noOverlap constraints ...

        # Let the preset decide (default)
        result = model.solve()

        # Or use maximum propagation for dense problems
        result = model.solve(noOverlapPropagationLevel=4)

        # Or use minimum propagation for very large problems
        result = model.solve(noOverlapPropagationLevel=1)

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of propagation levels.
        - :attr:`Parameters.searchType` for choosing the search algorithm.
        - :meth:`Model.no_overlap` for creating noOverlap constraints.
    """

    cumulPropagationLevel: int
    r"""
    How much to propagate constraints on cumul functions

    This parameter controls the amount of propagation done for cumulative constraints (e.g., `cumul <= limit`) when used with a sum of :meth:`Model.pulse` pulses.

    Higher levels use more sophisticated algorithms that can detect more infeasibilities and prune more values from domains, but at the cost of increased computation time.

    **Propagation levels:**

    - Level 1: Basic timetable propagation
    - Level 2: Adds time-table edge-finding
    - Level 3: Maximum propagation with all available algorithms

    **Automatic selection (level 0):**

    When set to 0 (the default), the propagation level is determined automatically based on the :attr:`Parameters.preset`:

    - `Default` preset: Uses level 3 (maximum propagation)
    - `Large` preset: Uses level 1 (minimum propagation for scalability)

    **Performance considerations:**

    More propagation doesn't necessarily mean better overall performance. The trade-off depends on your problem:

    - **Resource-constrained problems** with tight capacity limits often benefit from higher propagation levels because cumulative reasoning can prune many infeasible assignments.

    - **Problems with loose resource constraints** may not benefit much from higher levels because the extra computation doesn't lead to significant pruning.

    - **Very large problems** may perform better with lower propagation levels because the overhead becomes prohibitive.

    - **FDS search** (see :attr:`Parameters.searchType`) typically benefits from higher propagation levels.

    If you're unsure, start with the automatic selection (level 0) and let the preset choose.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model with cumulative constraints ...

        # Let the preset decide (default)
        result = model.solve()

        # Or use maximum propagation for resource-constrained problems
        result = model.solve(cumulPropagationLevel=3)

        # Or use minimum propagation for very large problems
        result = model.solve(cumulPropagationLevel=1)

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of propagation levels.
        - :attr:`Parameters.searchType` for choosing the search algorithm.
        - :meth:`Model.pulse` for creating pulse contributions to cumulative functions.
    """

    reservoirPropagationLevel: int
    r"""
    How much to propagate constraints on cumul functions

    This parameter controls the amount of propagation done for cumulative constraints (e.g., `cumul <= limit`, `cumul >= limit`) when used together with steps (:meth:`Model.step_at_start`, :meth:`Model.step_at_end`, :meth:`Model.step_at`).
    The bigger the value, the more algorithms are used for propagation.
    It means that more time is spent by the propagation, and possibly more values are removed from domains.
    More propagation doesn't necessarily mean better performance.
    FDS search (see :attr:`Parameters.searchType`) usually benefits from higher propagation levels.

    The parameter takes an integer value in range `1..2`.

    The default value is `1`.
    """

    positionPropagationLevel: int
    r"""
    How much to propagate position expressions on noOverlap constraints

    This parameter controls the amount of propagation done for position expressions on noOverlap constraints.
    The bigger the value, the more algorithms are used for propagation.
    It means that more time is spent by the propagation, and possibly more values are removed from domains.
    However, more propagation doesn't necessarily mean better performance.
    FDS search (see :attr:`Parameters.searchType`) usually benefits from higher propagation levels.

    The parameter takes an integer value in range `1..3`.

    The default value is `2`.
    """

    integralPropagationLevel: int
    r"""
    How much to propagate integral expression

    This parameter controls the amount of propagation done for :meth:`Model.integral` expressions.
    In particular, it controls whether the propagation also affects the minimum and the maximum length of the associated interval variable:

    * `1`: The length is updated only once during initial constraint propagation.
    * `2`: The length is updated every time the expression is propagated.

    The parameter takes an integer value in range `1..2`.

    The default value is `1`.
    """

    _packPropagationLevel: int
    _itvMappingPropagationLevel: int
    searchTraceLevel: int
    r"""
    Level of search trace

    This parameter is available only in the development edition of the solver.

    When set to a value bigger than zero, the solver prints a trace of the search.
    The trace contains information about every choice taken by the solver.
    The higher the value, the more information is printed.

    The parameter takes an integer value in range `0..5`.

    The default value is `0`.
    """

    propagationTraceLevel: int
    r"""
    Level of propagation trace

    This parameter is available only in the development edition of the solver.

    When set to a value bigger than zero, the solver prints a trace of the propagation,
    that is a line for every domain change.
    The higher the value, the more information is printed.

    The parameter takes an integer value in range `0..5`.

    The default value is `0`.
    """

    fdsInitialRating: float
    r"""
    Initial rating for newly created choices

    Default rating for newly created choices. Both left and right branches get the same rating.
    Choice is initially permuted so that bigger domain change is the left branch.

    The parameter takes a floating point value in range `0.0..2.0`.

    The default value is `0.5`.
    """

    fdsReductionWeight: float
    r"""
    Weight of the reduction factor in rating computation

    When computing the local rating of a branch, multiply reduction factor by the given weight.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `1`.
    """

    fdsRatingAverageLength: int
    r"""
    Length of average rating computed for choices

    For the computation of rating of a branch. Arithmetic average is used until the branch
    is taken at least FDSRatingAverageLength times. After that exponential moving average
    is used with parameter alpha = 1 - 1 / FDSRatingAverageLength.

    The parameter takes an integer value in range `0..254`.

    The default value is `25`.
    """

    fdsFixedAlpha: float
    r"""
    When non-zero, alpha factor for rating updates

    When this parameter is set to a non-zero, parameter FDSRatingAverageLength is ignored.
    Instead, the rating of a branch is computed as an exponential moving average with the given parameter alpha.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0`.
    """

    fdsRatingAverageComparison: Literal['Off', 'Global', 'Depth']
    r"""
    Whether to compare the local rating with the average

    Possible values are:

     * `Off` (the default): No comparison is done.
     * `Global`: Compare with the global average.
     * `Depth`: Compare with the average on the current search depth

    Arithmetic average is used for global and depth averages.

    The default value is `Off`.
    """

    fdsReductionFactor: Literal['Normal', 'Zero', 'Random']
    r"""
    Reduction factor R for rating computation

    Possible values are:

     * `Normal` (the default): Normal reduction factor.
     * `Zero`: Factor is not used (it is 0 all the time).
     * `Random`: A random number in the range [0,1] is used instead.

    The default value is `Normal`.
    """

    fdsReuseClosing: bool
    r"""
    Whether always reuse closing choice

    Most of the time, FDS reuses closing choice automatically. This parameter enforces it all the time.

    The default value is `False`.
    """

    fdsUniformChoiceStep: bool
    r"""
    Whether all initial choices have the same step length

    When set, then initial choices generated on interval variables will have the same step size.

    The default value is `True`.
    """

    fdsLengthStepRatio: float
    r"""
    Choice step relative to average length

    Ratio of initial choice step size to the minimum length of interval variable. When FDSUniformChoiceStep is set, this ratio is used to compute global choice step using the average of interval var length. When FDSUniformChoiceStep is not set, this ratio is used to compute the choice step for every interval var individually.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `0.699999988079071`.
    """

    fdsMaxInitialChoicesPerVariable: int
    r"""
    Maximum number of choices generated initially per a variable

    Initial domains are often very large (e.g., `0..IntervalMax`). Therefore initial
    number of generated choices is limited: only choices near startMin are kept.

    The parameter takes an integer value in range `2..2147483647`.

    The default value is `90`.
    """

    fdsAdditionalStepRatio: float
    r"""
    Domain split ratio when run out of choices

    When all choices are decided, and a greedy algorithm cannot find a solution, then
    more choices are generated by splitting domains into the specified number of pieces.

    The parameter takes a floating point value in range `2.0..Infinity`.

    The default value is `7`.
    """

    fdsPresenceStatusChoices: bool
    r"""
    Whether to generate choices on presence status

    Choices on start time also include a choice on presence status. Therefore, dedicated choices on presence status only are not mandatory.

    The default value is `True`.
    """

    fdsMaxInitialLengthChoices: int
    r"""
    Maximum number of initial choices on length of an interval variable

    When non-zero, this parameter limits the number of initial choices generated on length of an interval variable.
    When zero (the default), no choices on length are generated.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `0`.
    """

    fdsMinLengthChoiceStep: int
    r"""
    Maximum step when generating initial choices for length of an interval variable

    Steps between choices for length of an interval variable are never bigger than the specified value.

    The parameter takes an integer value in range `1..1073741823`.

    The default value is `1073741823`.
    """

    fdsMinIntVarChoiceStep: int
    r"""
    Minimum step when generating choices for integer variables.

    Steps between choices for integer variables are never smaller than the specified value.

    The parameter takes an integer value in range `1..1073741823`.

    The default value is `1073741823`.
    """

    fdsEventTimeInfluence: float
    r"""
    Influence of event time to initial choice rating

    When non-zero, the initial choice rating is influenced by the date of the choice.
    This way, very first choices in the search should be taken chronologically.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0`.
    """

    fdsBothFailRewardFactor: float
    r"""
    How much to improve rating when both branches fail immediately

    This parameter sets a bonus reward for a choice when both left and right branches fail immediately.
    Current rating of both branches is multiplied by the specified value.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0.98`.
    """

    fdsEpsilon: float
    r"""
    How often to chose a choice randomly

    Probability that a choice is taken randomly. A randomly selected choice is not added to the search tree automatically. Instead, the choice is tried, its rating is updated,
    but it is added to the search tree only if one of the branches fails.
    The mechanism is similar to strong branching.

    The parameter takes a floating point value in range `0.0..0.99999`.

    The default value is `0.1`.
    """

    fdsStrongBranchingSize: int
    r"""
    Number of choices to try in strong branching

    Strong branching means that instead of taking a choice with the best rating,
    we take the specified number (FDSStrongBranchingSize) of best choices,
    try them in dry-run mode, measure their local rating, and
    then chose the one with the best local rating.

    The parameter takes an integer value.

    The default value is `10`.
    """

    fdsStrongBranchingDepth: int
    r"""
    Up-to what search depth apply strong branching

    Strong branching is typically used in the root node. This parameter controls
    the maximum search depth when strong branching is used.

    The parameter takes an integer value.

    The default value is `6`.
    """

    fdsStrongBranchingCriterion: Literal['Both', 'Left', 'Right']
    r"""
    How to choose the best choice in strong branching

    Possible values are:

    * `Both`: Choose the the choice with best combined rating.
    * `Left` (the default): Choose the choice with the best rating of the left branch.
    * `Right`: Choose the choice with the best rating of the right branch.

    The default value is `Left`.
    """

    fdsInitialRestartLimit: int
    r"""
    Fail limit for the first restart

    Failure-directed search is periodically restarted: explored part of the current search tree is turned into a no-good constraint, and the search starts again in the root node.
    This parameter specifies the size of the very first search tree (measured in number of failures).

    The parameter takes an integer value in range `1..9223372036854775807`.

    The default value is `100`.
    """

    fdsRestartStrategy: Literal['Geometric', 'Nested', 'Luby']
    r"""
    Restart strategy to use

    This parameter specifies how the restart limit (maximum number of failures) changes from restart to restart.
    Possible values are:

    * `Geometric` (the default): After each restart, restart limit is multiplied by :attr:`Parameters.fdsRestartGrowthFactor`.
    * `Nested`: Similar to `Geometric` but the limit is changed back to :attr:`Parameters.fdsInitialRestartLimit` each time a new maximum limit is reached.
    * `Luby`: Luby restart strategy is used. Parameter :attr:`Parameters.fdsRestartGrowthFactor` is ignored.

    The default value is `Geometric`.
    """

    fdsRestartGrowthFactor: float
    r"""
    Growth factor for fail limit after each restart

    After each restart, the fail limit for the restart is multiplied by the specified factor.
    This parameter is ignored when :attr:`Parameters.fdsRestartStrategy` is `Luby`.

    The parameter takes a floating point value in range `1.0..Infinity`.

    The default value is `1.15`.
    """

    fdsMaxCounterAfterRestart: int
    r"""
    Truncate choice use counts after a restart to this value

    The idea is that ratings learned in the previous restart are less valid in the new restart.
    Using this parameter, it is possible to truncate use counts on choices so that new local ratings will have bigger weights (when FDSFixedAlpha is not used).

    The parameter takes an integer value.

    The default value is `255`.
    """

    fdsMaxCounterAfterSolution: int
    r"""
    Truncate choice use counts after a solution is found

    Similar to :attr:`Parameters.fdsMaxCounterAfterRestart`, this parameter allows truncating use counts on choices when a solution is found.

    The parameter takes an integer value.

    The default value is `255`.
    """

    fdsResetRestartsAfterSolution: bool
    r"""
    Reset restart size after a solution is found (ignored in Luby)

    When this parameter is set (the default), then restart limit is set back to :attr:`Parameters.fdsInitialRestartLimit` when a solution is found.

    The default value is `True`.
    """

    fdsUseNogoods: bool
    r"""
    Whether to use or not nogood constraints

    By default, no-good constraint is generated after each restart. This parameter allows to turn no-good constraints off.

    The default value is `True`.
    """

    _fdsFreezeRatingsAfterProof: bool
    _fdsContinueAfterProof: bool
    _fdsRepeatLimit: int
    _fdsCompletelyRandom: bool
    fdsBranchOnObjective: bool
    r"""
    Whether to generate choices for objective expression/variable

    This option controls the generation of choices on the objective. It works regardless of the objective is given by an expression or a variable.

    The default value is `False`.
    """

    _fdsImproveNogoods: bool
    fdsBranchOrdering: Literal['FailureFirst', 'FailureLast', 'Random']
    r"""
    Controls which side of a choice is explored first (considering the rating).

    This option can take the following values:

    * `FailureFirst`: Explore the failure side first.
    * `FailureLast`: Explore the failure side last.
    * `Random`: Explore either side randomly.

    The default value is `FailureFirst`.
    """

    _fdsDiveBySetTimes: bool
    fdsDualStrategy: Literal['Minimum', 'Random', 'Split']
    r"""
    A strategy to choose objective cuts during FDSDual search.

    Possible values are:

    * `Minimum`: Always change the cut by the minimum amount.
    * `Random`: At each restart, randomly choose a value in range LB..UB. The default.
    * `Split`: Always split the current range LB..UB in half.

    The default value is `Random`.
    """

    fdsDualResetRatings: bool
    r"""
    Whether to reset ratings when a new LB is proved

    When this parameter is on, and FDSDual proves a new lower bound, then all ratings are reset to default values.

    The default value is `False`.
    """

    _lnsInitNoOverlapPropagationLevel: int
    _lnsInitCumulPropagationLevel: int
    _lnsFirstFailLimit: int
    _lnsFailLimitGrowthFactor: float
    _lnsFailLimitCoefficient: float
    _lnsIterationsAfterFirstSolution: int
    _lnsAggressiveDominance: bool
    _lnsSameSolutionPeriod: int
    _lnsTier1Size: int
    _lnsTier2Size: int
    _lnsTier3Size: int
    _lnsTier2Effort: float
    _lnsTier3Effort: float
    _lnsStepFailLimitFactor: float
    _lnsApplyCutProbability: float
    _lnsSmallStructureLimit: int
    _lnsResourceOptimization: bool
    _lnsRestoreAbsentIntervals: bool
    _lnsRestoreIntervalLengths: bool
    _lnsRestoreIntVarValues: bool
    lnsUseWarmStartOnly: bool
    r"""
    Use only the user-provided warm start as the initial solution in LNS

    When this parameter is on, the solver will use only the user-specified warm start solution for the initial solution phase in LNS. If no warm start is provided, the solver will search for its own initial solution as usual.

    The default value is `False`.
    """

    _lnsHeuristicsEpsilon: float
    _lnsHeuristicsAlpha: float
    _lnsHeuristicsTemperature: float
    _lnsHeuristicsUniform: bool
    _lnsHeuristicsInitialQ: float
    _lnsPortionEpsilon: float
    _lnsPortionAlpha: float
    _lnsPortionTemperature: float
    _lnsPortionUniform: bool
    _lnsPortionInitialQ: float
    _lnsPortionHandicapLimit: float
    _lnsPortionHandicapValue: float
    _lnsPortionHandicapInitialQ: float
    _lnsNeighborhoodStrategy: int
    _lnsNeighborhoodEpsilon: float
    _lnsNeighborhoodAlpha: float
    _lnsNeighborhoodTemperature: float
    _lnsNeighborhoodUniform: bool
    _lnsNeighborhoodInitialQ: float
    _lnsDivingLimit: int
    _lnsDivingFailLimitRatio: float
    _lnsLearningRun: bool
    _lnsStayOnObjective: bool
    _lnsFDS: bool
    _lnsFreezeIntervalsBeforeFragment: bool
    _lnsRelaxSlack: float
    _lnsPortionMultiplier: float
    simpleLBWorker: int
    r"""
    Which worker computes simple lower bound

    Simple lower bound is a bound such that infeasibility of a better objective can be proved by propagation only (without the search). The given worker computes simple lower bound before it starts the normal search. If a worker with the given number doesn't exist, then the lower bound is not computed.

    The parameter takes an integer value in range `-1..2147483647`.

    The default value is `0`.
    """

    simpleLBMaxIterations: int
    r"""
    Maximum number of feasibility checks

    Simple lower bound is computed by binary search for the best objective value that is not infeasible by propagation. This parameter limits the maximum number of iterations of the binary search. When the value is 0, then simple lower bound is not computed at all.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `2147483647`.
    """

    simpleLBShavingRounds: int
    r"""
    Number of shaving rounds

    When non-zero, the solver shaves on variable domains to improve the lower bound. This parameter controls the number of shaving rounds.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `0`.
    """

    _debugTraceLevel: int
    _memoryTraceLevel: int
    _propagationDetailTraceLevel: int
    _setTimesTraceLevel: int
    _communicationTraceLevel: int
    _conversionTraceLevel: int
    _expressionBuilderTraceLevel: int
    _memorizationTraceLevel: int
    _searchDetailTraceLevel: int
    _fdsTraceLevel: int
    _shavingTraceLevel: int
    _fdsRatingsTraceLevel: int
    _lnsTraceLevel: int
    _heuristicReplayTraceLevel: int
    _allowSetTimesProofs: bool
    _setTimesAggressiveDominance: bool
    _setTimesExtendsCoef: float
    _setTimesHeightStrategy: Literal['FromMax', 'FromMin', 'Random']
    _setTimesItvMappingStrategy: Literal['FromMax', 'FromMin', 'Random']
    _setTimesInitDensity: float
    _setTimesDensityLength: int
    _setTimesDensityReliabilityThreshold: int
    _setTimesNbExtendsFactor: float
    _discreteLowCapacityLimit: int
    _lnsTrainingObjectiveLimit: float
    _posAbsentRelated: bool
    _defaultCallbackBlockSize: int
    _useReservoirPegging: bool
    _useTimeNet: bool
    _timeNetVarsToPreprocess: int
    _timeNetSubPriorityBits: int



class Parameters(TypedDict, total=False):
    r"""
    Parameters specify how the solver should behave.  For example, the
    number of workers (threads) to use, the time limit, etc.

    Parameters can be passed to the solver functions :meth:`Model.solve`
    and :meth:`Solver.solve`.

    ## Example

    In the following example, we are using the *TimeLimit* parameter to specify
    that the solver should stop after 5 minutes. We also specify that the solver
    should use 4 threads. Finally, we specify that the solver should use
    *FDS* search (in all threads).

    .. code-block:: python

        import optalcp as cp

        params: cp.Parameters = {
            'timeLimit': 300,  # In seconds, i.e. 5 minutes
            'nbWorkers': 4,    # Use 4 threads
            'searchType': 'FDS',
        }
        result = my_model.solve(params)

    ### Worker-specific parameters

    Some parameters can be specified differently for each worker.  For example,
    some workers may use *LNS* search while others use *FDS* search.  To specify
    worker-specific parameters, use the *workers* parameter and pass an array
    of :class:`WorkerParameters`.

    Not all parameters can be specified per worker. For example, *TimeLimit* is a
    global parameter. See :class:`WorkerParameters` for the list of parameters
    that can be specified per worker.

    If a parameter is not set specifically for a worker, the global value is used.

    ## Example

    In the following example, we are going to use 4 workers; two of them will run
    *FDS* search and the remaining two will run *LNS* search.  In addition, workers
    that use *FDS* search will use increased propagation levels.

    .. code-block:: python

        import optalcp as cp

        # Parameters for a worker that uses FDS search.
        # FDS works best with increased propagation levels, so set them:
        fds_worker: cp.WorkerParameters = {
            'searchType': 'FDS',
            'noOverlapPropagationLevel': 4,
            'cumulPropagationLevel': 3,
            'reservoirPropagationLevel': 2,
        }
        # Global parameters:
        params: cp.Parameters = {
            'timeLimit': 60,      # In seconds, i.e. 1 minute
            'searchType': 'LNS',  # The default search type. It is not necessary, as "LNS" is the default value.
            'nbWorkers': 4,       # Use 4 threads
            # The first two workers will use FDS search.
            # The remaining two workers will use the defaults, i.e., LNS search with default propagation levels.
            'workers': [fds_worker, fds_worker],
        }
        result = my_model.solve(params)

    .. seealso::

        - :class:`WorkerParameters` for worker-specific parameters.
    """

    color: Literal['Never', 'Auto', 'Always']
    r"""
    Whether to colorize output to the terminal

    This parameter controls when terminal output is colorized. Possible values are:

    *  `Never`: don't colorize the output.
    *  `Auto`: colorize if the output is a supported terminal.
    *  `Always`: always colorize the output.

    The default value is `Auto`.
    """

    nbWorkers: int
    r"""
    Number of threads dedicated to search

    When this parameter is 0 (the default), the number of workers is determined the following way:

     * If environment variable `OPTALCP_NB_WORKERS` is set, its value is used.
     * Otherwise, all available cores are used.

    The parameter takes an integer value.

    The default value is `0`.
    """

    _nbHelpers: int
    preset: Literal['Auto', 'Default', 'Large']
    r"""
    Preset configuration for solver parameters

    Presets provide reasonable default values for multiple solver parameters at once. Instead of manually tuning individual parameters, you can select a preset that matches your problem characteristics. The solver will then configure search strategies and propagation levels appropriately.

    **Available presets:**

    - `Auto`: The solver automatically selects a preset based on problem size (the default). Problems with more than 100,000 variables use `Large`, otherwise `Default`.

    - `Default`: Balanced configuration for most problems. Uses maximum propagation levels and distributes workers across different search strategies: half use LNS, 3/8 use FDS, and the rest use FDSDual. This provides a good mix of exploration and exploitation.

    - `Large`: Optimized for big problems with more than 100,000 variables. Uses minimum propagation to reduce overhead, and all workers use LNS search. This trades propagation strength for scalability.

    **Parameters affected by presets:**

    The preset sets default values for the following parameters:

    - :attr:`Parameters.searchType`: How workers are distributed across LNS, FDS, and FDSDual
    - :attr:`Parameters.noOverlapPropagationLevel`: Propagation strength for noOverlap constraints
    - :attr:`Parameters.cumulPropagationLevel`: Propagation strength for cumulative constraints

    When you explicitly set any of these parameters, your value takes precedence over the preset's default. This allows you to use a preset as a starting point and fine-tune specific parameters as needed.

    **When to use presets:**

    Presets are a good starting point for most problems. They are not guaranteed to be optimal for your specific problem, but they provide reasonable defaults that work well in practice. If you find that the default preset is not working well for your problem, consider:

    - Trying the `Large` preset for very big problems, even if they have fewer than 100,000 variables
    - Explicitly setting :attr:`Parameters.searchType` to use a specific search strategy
    - Adjusting propagation levels based on your problem structure

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model ...

        # Use automatic preset selection
        result = model.solve()

        # Or explicitly select a preset for a large problem
        result = model.solve(preset="Large")

        # Or use Default preset but override search type
        result = model.solve(preset="Default", searchType="FDS")

    .. seealso::

        - :attr:`Parameters.searchType` for choosing the search algorithm.
        - :attr:`Parameters.noOverlapPropagationLevel` for tuning noOverlap propagation.
        - :attr:`Parameters.cumulPropagationLevel` for tuning cumulative propagation.
    """

    searchType: Literal['Auto', 'LNS', 'FDS', 'FDSDual', 'SetTimes', 'FDSLB']
    r"""
    Type of search to use

    This parameter controls which search algorithm the solver uses. Different search types have different strengths:

    - `Auto`: Automatically determined based on the :attr:`Parameters.preset` (the default). With the `Default` preset, workers are distributed across LNS, FDS, and FDSDual. With the `Large` preset, all workers use LNS.

    - `LNS`: Large Neighborhood Search. Starts from an initial solution and iteratively improves it by relaxing and re-optimizing parts of the solution. Good for finding high-quality solutions quickly, especially on large problems. Works best when a good initial solution can be found.

    - `FDS`: Failure-Directed Search. A systematic search that learns from failures to guide exploration. Uses restarts with no-good learning. Often effective at proving optimality and works well with strong propagation.

    - `FDSDual`: Failure-Directed Search working on objective bounds. Similar to FDS but focuses on proving bounds on the objective value. Useful for optimization problems where you want to know how far from optimal your solutions are.

    - `SetTimes`: Depth-first set-times search (not restarted). A simple chronological search that assigns start times in order. Can be effective for tightly constrained problems but generally less robust than other methods.

    **Interaction with presets:**

    When `searchType` is set to `Auto`, the actual search type is determined by the :attr:`Parameters.preset`:

    - `Default` preset: Distributes workers across different search types. Half use LNS, 3/8 use FDS, and the rest use FDSDual. This portfolio approach provides robustness across different problem types.

    - `Large` preset: All workers use LNS. For very large problems, the overhead of systematic search methods like FDS becomes prohibitive, so LNS is used exclusively.

    If you explicitly set `searchType` to a specific value (not `Auto`), that value is used regardless of the preset.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model ...

        # Let the preset decide (default behavior)
        result = model.solve()

        # Or explicitly use FDS for systematic search
        result = model.solve(searchType="FDS")

        # Or use LNS for quick solutions on large problems
        result = model.solve(searchType="LNS")

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of search and propagation.
        - :attr:`Parameters.noOverlapPropagationLevel` which works well with FDS at higher levels.
    """

    randomSeed: int
    r"""
    Random seed

    The solver breaks ties randomly using a pseudorandom number generator. This parameter sets the seed of the generator.

    Note that when :attr:`Parameters.nbWorkers` is more than 1 then there is also another source of randomness: the time it takes for a message to pass from one worker to another. Therefore with 1 worker the solver is deterministic (random behavior depends only on random seed). With more workers the solver is not deterministic.

    Even with the same random seed, the solver may behave differently on different platforms. This can be due to different implementations of certain functions such as `std::sort`.

    The parameter takes an integer value.

    The default value is `1`.
    """

    logLevel: int
    r"""
    Level of the log

    This parameter controls the amount of text the solver writes on standard output. The solver is completely silent when this option is set to 0.

    The parameter takes an integer value in range `0..3`.

    The default value is `2`.
    """

    warningLevel: int
    r"""
    Level of warnings

    This parameter controls the types of warnings the solver emits. When this parameter is set to 0 then no warnings are emitted.

    The parameter takes an integer value in range `0..3`.

    The default value is `2`.
    """

    logPeriod: float
    r"""
    How often to print log messages (in seconds)

    When :attr:`Parameters.logLevel` &ge; 2 then solver writes a log message every `logPeriod` seconds. The log message contains the current statistics about the solve: number of branches, number of fails, memory used, etc.

    The parameter takes a floating point value in range `0.01..Infinity`.

    The default value is `10`.
    """

    verifySolutions: bool
    r"""
    When on, the correctness of solutions is verified

    Verification is an independent algorithm that checks whether all constraints in the model are satisfied (or absent), and that objective value was computed correctly. Verification is a somewhat redundant process as all solutions should be correct. Its purpose is to double-check and detect bugs in the solver.

    The default value is `False`.
    """

    verifyExternalSolutions: bool
    r"""
    Whether to verify correctness of external solutions

    External solutions can be passed to the solver as a warm start via :meth:`Model.solve`, or using :meth:`Solver.send_solution` during the search. Normally, all external solutions are checked before they are used. However, the check may be time consuming, especially if too many external solutions are sent simultaneously. This parameter allows to turn the check off.

    The default value is `True`.
    """

    allocationBlockSize: int
    r"""
    The minimal amount of memory in kB for a single allocation

    The solver allocates memory in blocks. This parameter sets the minimal size of a block. Larger blocks mean a higher risk of wasting memory. However, larger blocks may also lead to better performance, particularly when the size matches the page size supported by the operating system.

    The value of this parameter must be a power of 2.

    The default value of 2048 means 2MB, which means that up to ~12MB can be wasted per worker in the worst case.

    The parameter takes an integer value in range `4..1073741824`.

    The default value is `2048`.
    """

    processExitTimeout: float
    r"""
    Timeout for solver process to exit after finishing

    After the solver finishes, wait up to this many seconds for the process to exit. If it doesn't exit in time, it is silently killed.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `3`.
    """

    timeLimit: float
    r"""
    Wall clock limit for execution in seconds

    Caps the total wall-clock time spent by the solver. The timer starts as soon as the solve begins, and it includes presolve, search, and verification. When the limit is reached, all workers stop cooperatively. Leave it at the default `Infinity` to run without a time bound.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `Infinity`.
    """

    solutionLimit: int
    r"""
    Stop the search after the given number of solutions

    Terminates the solve after the specified number of solutions have been found and reported.

    **Automatic behavior (value 0):**

    When set to 0 (the default), the limit is determined automatically based on the problem type:

    - **Decision problems** (no objective): The solver stops after finding the first solution. This is usually what you want for feasibility problems.

    - **Optimization problems**: No limit is applied. The solver continues searching for better solutions until it proves optimality, hits another limit (like :attr:`Parameters.timeLimit`), or is stopped manually.

    **Explicit values:**

    You can set an explicit limit to control solution enumeration:

    - `1`: Stop after the first solution. Useful when you just need any feasible solution quickly, even for optimization problems.

    - `N > 1`: Find up to N solutions. Useful for:
       - Generating multiple alternative solutions for warm starts
       - Enumerating all solutions to small problems
       - Finding a diverse set of solutions for analysis

    **Note on optimization problems:**

    For optimization problems, only improving solutions are counted. If you set `solutionLimit=5`, the solver will stop after finding 5 solutions, each better than the previous. Non-improving solutions (which can occur during the search) are not counted toward the limit.

    **Note on LNS and decision problems:**

    When using LNS search (see :attr:`Parameters.searchType`) on decision problems (no objective), be aware that LNS may report duplicate solutions. LNS works by iteratively improving a solution, and for decision problems without an objective to guide the search, it may find the same solution multiple times. If you need unique solutions, consider using FDS search instead, or filter duplicates in your application code.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model ...

        # Automatic behavior (default)
        # - Decision problem: stops after 1 solution
        # - Optimization: no limit
        result = model.solve()

        # Stop after first solution (useful for quick feasibility check)
        result = model.solve(solutionLimit=1)

        # Find up to 10 solutions for warm starts
        result = model.solve(solutionLimit=10)

    .. seealso::

        - :attr:`Parameters.timeLimit` for limiting solve time.
    """

    _workerFailLimit: int
    _workerBranchLimit: int
    _workerSolutionLimit: int
    _workerLNSStepLimit: int
    _workerRestartLimit: int
    absoluteGapTolerance: float
    r"""
    Stop the search when the gap is below the tolerance

    The search is stopped if the absolute difference between the current solution
    value and current lower/upper bound is not bigger than the specified value.

    This parameter works together with :attr:`Parameters.relativeGapTolerance` as an OR condition: the search stops when *either* the absolute gap or the relative gap is within tolerance.

    The parameter takes a floating point value.

    The default value is `0`.
    """

    relativeGapTolerance: float
    r"""
    Stop the search when the gap is below the tolerance

    The search is stopped if the relative difference between the current solution
    value and current lower/upper bound is not bigger than the specified value.

    This parameter works together with :attr:`Parameters.absoluteGapTolerance` as an OR condition: the search stops when *either* the absolute gap or the relative gap is within tolerance.

    The parameter takes a floating point value.

    The default value is `0.0001`.
    """

    _tagsFromNames: Literal['Never', 'Auto', 'Merge', 'Force']
    noOverlapPropagationLevel: int
    r"""
    How much to propagate noOverlap constraints

    This parameter controls the amount of propagation done for noOverlap constraints. Higher levels use more sophisticated algorithms that can detect more infeasibilities and prune more values from domains, but at the cost of increased computation time.

    **Propagation levels:**

    - Level 1: Basic timetable propagation only
    - Level 2: Adds detectable precedences algorithm
    - Level 3: Adds edge-finding reasoning
    - Level 4: Maximum propagation with all available algorithms

    **Automatic selection (level 0):**

    When set to 0 (the default), the propagation level is determined automatically based on the :attr:`Parameters.preset`:

    - `Default` preset: Uses level 4 (maximum propagation)
    - `Large` preset: Uses level 1 (minimum propagation for scalability)

    **Performance considerations:**

    More propagation doesn't necessarily mean better overall performance. The trade-off depends on your problem:

    - **Dense scheduling problems** with many overlapping intervals often benefit from higher propagation levels because the extra pruning reduces the search space significantly.

    - **Sparse problems** or **very large problems** may perform better with lower propagation levels because the overhead of sophisticated algorithms outweighs the benefit.

    - **FDS search** (see :attr:`Parameters.searchType`) typically benefits from higher propagation levels because it relies on strong propagation to guide the search.

    If you're unsure, start with the automatic selection (level 0) and let the preset choose. You can then experiment with explicit levels if needed.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model with noOverlap constraints ...

        # Let the preset decide (default)
        result = model.solve()

        # Or use maximum propagation for dense problems
        result = model.solve(noOverlapPropagationLevel=4)

        # Or use minimum propagation for very large problems
        result = model.solve(noOverlapPropagationLevel=1)

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of propagation levels.
        - :attr:`Parameters.searchType` for choosing the search algorithm.
        - :meth:`Model.no_overlap` for creating noOverlap constraints.
    """

    cumulPropagationLevel: int
    r"""
    How much to propagate constraints on cumul functions

    This parameter controls the amount of propagation done for cumulative constraints (e.g., `cumul <= limit`) when used with a sum of :meth:`Model.pulse` pulses.

    Higher levels use more sophisticated algorithms that can detect more infeasibilities and prune more values from domains, but at the cost of increased computation time.

    **Propagation levels:**

    - Level 1: Basic timetable propagation
    - Level 2: Adds time-table edge-finding
    - Level 3: Maximum propagation with all available algorithms

    **Automatic selection (level 0):**

    When set to 0 (the default), the propagation level is determined automatically based on the :attr:`Parameters.preset`:

    - `Default` preset: Uses level 3 (maximum propagation)
    - `Large` preset: Uses level 1 (minimum propagation for scalability)

    **Performance considerations:**

    More propagation doesn't necessarily mean better overall performance. The trade-off depends on your problem:

    - **Resource-constrained problems** with tight capacity limits often benefit from higher propagation levels because cumulative reasoning can prune many infeasible assignments.

    - **Problems with loose resource constraints** may not benefit much from higher levels because the extra computation doesn't lead to significant pruning.

    - **Very large problems** may perform better with lower propagation levels because the overhead becomes prohibitive.

    - **FDS search** (see :attr:`Parameters.searchType`) typically benefits from higher propagation levels.

    If you're unsure, start with the automatic selection (level 0) and let the preset choose.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build your model with cumulative constraints ...

        # Let the preset decide (default)
        result = model.solve()

        # Or use maximum propagation for resource-constrained problems
        result = model.solve(cumulPropagationLevel=3)

        # Or use minimum propagation for very large problems
        result = model.solve(cumulPropagationLevel=1)

    .. seealso::

        - :attr:`Parameters.preset` for automatic configuration of propagation levels.
        - :attr:`Parameters.searchType` for choosing the search algorithm.
        - :meth:`Model.pulse` for creating pulse contributions to cumulative functions.
    """

    reservoirPropagationLevel: int
    r"""
    How much to propagate constraints on cumul functions

    This parameter controls the amount of propagation done for cumulative constraints (e.g., `cumul <= limit`, `cumul >= limit`) when used together with steps (:meth:`Model.step_at_start`, :meth:`Model.step_at_end`, :meth:`Model.step_at`).
    The bigger the value, the more algorithms are used for propagation.
    It means that more time is spent by the propagation, and possibly more values are removed from domains.
    More propagation doesn't necessarily mean better performance.
    FDS search (see :attr:`Parameters.searchType`) usually benefits from higher propagation levels.

    The parameter takes an integer value in range `1..2`.

    The default value is `1`.
    """

    positionPropagationLevel: int
    r"""
    How much to propagate position expressions on noOverlap constraints

    This parameter controls the amount of propagation done for position expressions on noOverlap constraints.
    The bigger the value, the more algorithms are used for propagation.
    It means that more time is spent by the propagation, and possibly more values are removed from domains.
    However, more propagation doesn't necessarily mean better performance.
    FDS search (see :attr:`Parameters.searchType`) usually benefits from higher propagation levels.

    The parameter takes an integer value in range `1..3`.

    The default value is `2`.
    """

    integralPropagationLevel: int
    r"""
    How much to propagate integral expression

    This parameter controls the amount of propagation done for :meth:`Model.integral` expressions.
    In particular, it controls whether the propagation also affects the minimum and the maximum length of the associated interval variable:

    * `1`: The length is updated only once during initial constraint propagation.
    * `2`: The length is updated every time the expression is propagated.

    The parameter takes an integer value in range `1..2`.

    The default value is `1`.
    """

    usePrecedenceEnergy: int
    r"""
    Whether to use precedence energy propagation algorithm

    Precedence energy algorithm improves propagation of precedence constraints when an interval has multiple predecessors (or successors) which use the same resource (noOverlap or cumulative constraint). In this case, the predecessors (or successors) may be in disjunction. Precedence energy algorithm can leverage this information and propagate the precedence constraint more aggressively.

    The parameter takes an integer value: `0` to disable, `1` to enable.

    The default value is `0`.
    """

    _packPropagationLevel: int
    _itvMappingPropagationLevel: int
    searchTraceLevel: int
    r"""
    Level of search trace

    This parameter is available only in the development edition of the solver.

    When set to a value bigger than zero, the solver prints a trace of the search.
    The trace contains information about every choice taken by the solver.
    The higher the value, the more information is printed.

    The parameter takes an integer value in range `0..5`.

    The default value is `0`.
    """

    propagationTraceLevel: int
    r"""
    Level of propagation trace

    This parameter is available only in the development edition of the solver.

    When set to a value bigger than zero, the solver prints a trace of the propagation,
    that is a line for every domain change.
    The higher the value, the more information is printed.

    The parameter takes an integer value in range `0..5`.

    The default value is `0`.
    """

    infoTraceLevel: int
    r"""
    Level of information trace

    This parameter is available only in the development edition of the solver.

    When set to a value bigger than zero, the solver prints various high-level information.
    The higher the value, the more information is printed.

    The parameter takes an integer value in range `0..5`.

    The default value is `0`.
    """

    fdsInitialRating: float
    r"""
    Initial rating for newly created choices

    Default rating for newly created choices. Both left and right branches get the same rating.
    Choice is initially permuted so that bigger domain change is the left branch.

    The parameter takes a floating point value in range `0.0..2.0`.

    The default value is `0.5`.
    """

    fdsReductionWeight: float
    r"""
    Weight of the reduction factor in rating computation

    When computing the local rating of a branch, multiply reduction factor by the given weight.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `1`.
    """

    fdsRatingAverageLength: int
    r"""
    Length of average rating computed for choices

    For the computation of rating of a branch. Arithmetic average is used until the branch
    is taken at least FDSRatingAverageLength times. After that exponential moving average
    is used with parameter alpha = 1 - 1 / FDSRatingAverageLength.

    The parameter takes an integer value in range `0..254`.

    The default value is `25`.
    """

    fdsFixedAlpha: float
    r"""
    When non-zero, alpha factor for rating updates

    When this parameter is set to a non-zero, parameter FDSRatingAverageLength is ignored.
    Instead, the rating of a branch is computed as an exponential moving average with the given parameter alpha.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0`.
    """

    fdsRatingAverageComparison: Literal['Off', 'Global', 'Depth']
    r"""
    Whether to compare the local rating with the average

    Possible values are:

     * `Off` (the default): No comparison is done.
     * `Global`: Compare with the global average.
     * `Depth`: Compare with the average on the current search depth

    Arithmetic average is used for global and depth averages.

    The default value is `Off`.
    """

    fdsReductionFactor: Literal['Normal', 'Zero', 'Random']
    r"""
    Reduction factor R for rating computation

    Possible values are:

     * `Normal` (the default): Normal reduction factor.
     * `Zero`: Factor is not used (it is 0 all the time).
     * `Random`: A random number in the range [0,1] is used instead.

    The default value is `Normal`.
    """

    fdsReuseClosing: bool
    r"""
    Whether always reuse closing choice

    Most of the time, FDS reuses closing choice automatically. This parameter enforces it all the time.

    The default value is `False`.
    """

    fdsUniformChoiceStep: bool
    r"""
    Whether all initial choices have the same step length

    When set, then initial choices generated on interval variables will have the same step size.

    The default value is `True`.
    """

    fdsLengthStepRatio: float
    r"""
    Choice step relative to average length

    Ratio of initial choice step size to the minimum length of interval variable. When FDSUniformChoiceStep is set, this ratio is used to compute global choice step using the average of interval var length. When FDSUniformChoiceStep is not set, this ratio is used to compute the choice step for every interval var individually.

    The parameter takes a floating point value in range `0.0..Infinity`.

    The default value is `0.699999988079071`.
    """

    fdsMaxInitialChoicesPerVariable: int
    r"""
    Maximum number of choices generated initially per a variable

    Initial domains are often very large (e.g., `0..IntervalMax`). Therefore initial
    number of generated choices is limited: only choices near startMin are kept.

    The parameter takes an integer value in range `2..2147483647`.

    The default value is `90`.
    """

    fdsAdditionalStepRatio: float
    r"""
    Domain split ratio when run out of choices

    When all choices are decided, and a greedy algorithm cannot find a solution, then
    more choices are generated by splitting domains into the specified number of pieces.

    The parameter takes a floating point value in range `2.0..Infinity`.

    The default value is `7`.
    """

    fdsPresenceStatusChoices: bool
    r"""
    Whether to generate choices on presence status

    Choices on start time also include a choice on presence status. Therefore, dedicated choices on presence status only are not mandatory.

    The default value is `True`.
    """

    fdsMaxInitialLengthChoices: int
    r"""
    Maximum number of initial choices on length of an interval variable

    When non-zero, this parameter limits the number of initial choices generated on length of an interval variable.
    When zero (the default), no choices on length are generated.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `0`.
    """

    fdsMinLengthChoiceStep: int
    r"""
    Maximum step when generating initial choices for length of an interval variable

    Steps between choices for length of an interval variable are never bigger than the specified value.

    The parameter takes an integer value in range `1..1073741823`.

    The default value is `1073741823`.
    """

    fdsMinIntVarChoiceStep: int
    r"""
    Minimum step when generating choices for integer variables.

    Steps between choices for integer variables are never smaller than the specified value.

    The parameter takes an integer value in range `1..1073741823`.

    The default value is `1073741823`.
    """

    fdsEventTimeInfluence: float
    r"""
    Influence of event time to initial choice rating

    When non-zero, the initial choice rating is influenced by the date of the choice.
    This way, very first choices in the search should be taken chronologically.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0`.
    """

    fdsBothFailRewardFactor: float
    r"""
    How much to improve rating when both branches fail immediately

    This parameter sets a bonus reward for a choice when both left and right branches fail immediately.
    Current rating of both branches is multiplied by the specified value.

    The parameter takes a floating point value in range `0..1`.

    The default value is `0.98`.
    """

    fdsEpsilon: float
    r"""
    How often to chose a choice randomly

    Probability that a choice is taken randomly. A randomly selected choice is not added to the search tree automatically. Instead, the choice is tried, its rating is updated,
    but it is added to the search tree only if one of the branches fails.
    The mechanism is similar to strong branching.

    The parameter takes a floating point value in range `0.0..0.99999`.

    The default value is `0.1`.
    """

    fdsStrongBranchingSize: int
    r"""
    Number of choices to try in strong branching

    Strong branching means that instead of taking a choice with the best rating,
    we take the specified number (FDSStrongBranchingSize) of best choices,
    try them in dry-run mode, measure their local rating, and
    then chose the one with the best local rating.

    The parameter takes an integer value.

    The default value is `10`.
    """

    fdsStrongBranchingDepth: int
    r"""
    Up-to what search depth apply strong branching

    Strong branching is typically used in the root node. This parameter controls
    the maximum search depth when strong branching is used.

    The parameter takes an integer value.

    The default value is `6`.
    """

    fdsStrongBranchingCriterion: Literal['Both', 'Left', 'Right']
    r"""
    How to choose the best choice in strong branching

    Possible values are:

    * `Both`: Choose the the choice with best combined rating.
    * `Left` (the default): Choose the choice with the best rating of the left branch.
    * `Right`: Choose the choice with the best rating of the right branch.

    The default value is `Left`.
    """

    fdsInitialRestartLimit: int
    r"""
    Fail limit for the first restart

    Failure-directed search is periodically restarted: explored part of the current search tree is turned into a no-good constraint, and the search starts again in the root node.
    This parameter specifies the size of the very first search tree (measured in number of failures).

    The parameter takes an integer value in range `1..9223372036854775807`.

    The default value is `100`.
    """

    fdsRestartStrategy: Literal['Geometric', 'Nested', 'Luby']
    r"""
    Restart strategy to use

    This parameter specifies how the restart limit (maximum number of failures) changes from restart to restart.
    Possible values are:

    * `Geometric` (the default): After each restart, restart limit is multiplied by :attr:`Parameters.fdsRestartGrowthFactor`.
    * `Nested`: Similar to `Geometric` but the limit is changed back to :attr:`Parameters.fdsInitialRestartLimit` each time a new maximum limit is reached.
    * `Luby`: Luby restart strategy is used. Parameter :attr:`Parameters.fdsRestartGrowthFactor` is ignored.

    The default value is `Geometric`.
    """

    fdsRestartGrowthFactor: float
    r"""
    Growth factor for fail limit after each restart

    After each restart, the fail limit for the restart is multiplied by the specified factor.
    This parameter is ignored when :attr:`Parameters.fdsRestartStrategy` is `Luby`.

    The parameter takes a floating point value in range `1.0..Infinity`.

    The default value is `1.15`.
    """

    fdsMaxCounterAfterRestart: int
    r"""
    Truncate choice use counts after a restart to this value

    The idea is that ratings learned in the previous restart are less valid in the new restart.
    Using this parameter, it is possible to truncate use counts on choices so that new local ratings will have bigger weights (when FDSFixedAlpha is not used).

    The parameter takes an integer value.

    The default value is `255`.
    """

    fdsMaxCounterAfterSolution: int
    r"""
    Truncate choice use counts after a solution is found

    Similar to :attr:`Parameters.fdsMaxCounterAfterRestart`, this parameter allows truncating use counts on choices when a solution is found.

    The parameter takes an integer value.

    The default value is `255`.
    """

    fdsResetRestartsAfterSolution: bool
    r"""
    Reset restart size after a solution is found (ignored in Luby)

    When this parameter is set (the default), then restart limit is set back to :attr:`Parameters.fdsInitialRestartLimit` when a solution is found.

    The default value is `True`.
    """

    fdsUseNogoods: bool
    r"""
    Whether to use or not nogood constraints

    By default, no-good constraint is generated after each restart. This parameter allows to turn no-good constraints off.

    The default value is `True`.
    """

    _fdsFreezeRatingsAfterProof: bool
    _fdsContinueAfterProof: bool
    _fdsRepeatLimit: int
    _fdsCompletelyRandom: bool
    fdsBranchOnObjective: bool
    r"""
    Whether to generate choices for objective expression/variable

    This option controls the generation of choices on the objective. It works regardless of the objective is given by an expression or a variable.

    The default value is `False`.
    """

    _fdsImproveNogoods: bool
    fdsBranchOrdering: Literal['FailureFirst', 'FailureLast', 'Random']
    r"""
    Controls which side of a choice is explored first (considering the rating).

    This option can take the following values:

    * `FailureFirst`: Explore the failure side first.
    * `FailureLast`: Explore the failure side last.
    * `Random`: Explore either side randomly.

    The default value is `FailureFirst`.
    """

    _fdsDiveBySetTimes: bool
    fdsDualStrategy: Literal['Minimum', 'Random', 'Split']
    r"""
    A strategy to choose objective cuts during FDSDual search.

    Possible values are:

    * `Minimum`: Always change the cut by the minimum amount.
    * `Random`: At each restart, randomly choose a value in range LB..UB. The default.
    * `Split`: Always split the current range LB..UB in half.

    The default value is `Random`.
    """

    fdsDualResetRatings: bool
    r"""
    Whether to reset ratings when a new LB is proved

    When this parameter is on, and FDSDual proves a new lower bound, then all ratings are reset to default values.

    The default value is `False`.
    """

    _lnsInitNoOverlapPropagationLevel: int
    _lnsInitCumulPropagationLevel: int
    _lnsFirstFailLimit: int
    _lnsFailLimitGrowthFactor: float
    _lnsFailLimitCoefficient: float
    _lnsIterationsAfterFirstSolution: int
    _lnsAggressiveDominance: bool
    _lnsSameSolutionPeriod: int
    _lnsTier1Size: int
    _lnsTier2Size: int
    _lnsTier3Size: int
    _lnsTier2Effort: float
    _lnsTier3Effort: float
    _lnsStepFailLimitFactor: float
    _lnsApplyCutProbability: float
    _lnsSmallStructureLimit: int
    _lnsResourceOptimization: bool
    _lnsRestoreAbsentIntervals: bool
    _lnsRestoreIntervalLengths: bool
    _lnsRestoreIntVarValues: bool
    lnsUseWarmStartOnly: bool
    r"""
    Use only the user-provided warm start as the initial solution in LNS

    When this parameter is on, the solver will use only the user-specified warm start solution for the initial solution phase in LNS. If no warm start is provided, the solver will search for its own initial solution as usual.

    The default value is `False`.
    """

    _lnsHeuristicsEpsilon: float
    _lnsHeuristicsAlpha: float
    _lnsHeuristicsTemperature: float
    _lnsHeuristicsUniform: bool
    _lnsHeuristicsInitialQ: float
    _lnsPortionEpsilon: float
    _lnsPortionAlpha: float
    _lnsPortionTemperature: float
    _lnsPortionUniform: bool
    _lnsPortionInitialQ: float
    _lnsPortionHandicapLimit: float
    _lnsPortionHandicapValue: float
    _lnsPortionHandicapInitialQ: float
    _lnsNeighborhoodStrategy: int
    _lnsNeighborhoodEpsilon: float
    _lnsNeighborhoodAlpha: float
    _lnsNeighborhoodTemperature: float
    _lnsNeighborhoodUniform: bool
    _lnsNeighborhoodInitialQ: float
    _lnsDivingLimit: int
    _lnsDivingFailLimitRatio: float
    _lnsLearningRun: bool
    _lnsStayOnObjective: bool
    _lnsFDS: bool
    _lnsFreezeIntervalsBeforeFragment: bool
    _lnsRelaxSlack: float
    _lnsPortionMultiplier: float
    simpleLBWorker: int
    r"""
    Which worker computes simple lower bound

    Simple lower bound is a bound such that infeasibility of a better objective can be proved by propagation only (without the search). The given worker computes simple lower bound before it starts the normal search. If a worker with the given number doesn't exist, then the lower bound is not computed.

    The parameter takes an integer value in range `-1..2147483647`.

    The default value is `0`.
    """

    simpleLBMaxIterations: int
    r"""
    Maximum number of feasibility checks

    Simple lower bound is computed by binary search for the best objective value that is not infeasible by propagation. This parameter limits the maximum number of iterations of the binary search. When the value is 0, then simple lower bound is not computed at all.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `2147483647`.
    """

    simpleLBShavingRounds: int
    r"""
    Number of shaving rounds

    When non-zero, the solver shaves on variable domains to improve the lower bound. This parameter controls the number of shaving rounds.

    The parameter takes an integer value in range `0..2147483647`.

    The default value is `0`.
    """

    _debugTraceLevel: int
    _memoryTraceLevel: int
    _propagationDetailTraceLevel: int
    _setTimesTraceLevel: int
    _communicationTraceLevel: int
    _presolveTraceLevel: int
    _conversionTraceLevel: int
    _expressionBuilderTraceLevel: int
    _memorizationTraceLevel: int
    _searchDetailTraceLevel: int
    _fdsTraceLevel: int
    _shavingTraceLevel: int
    _fdsRatingsTraceLevel: int
    _lnsTraceLevel: int
    _heuristicReplayTraceLevel: int
    _allowSetTimesProofs: bool
    _setTimesAggressiveDominance: bool
    _setTimesExtendsCoef: float
    _setTimesHeightStrategy: Literal['FromMax', 'FromMin', 'Random']
    _setTimesItvMappingStrategy: Literal['FromMax', 'FromMin', 'Random']
    _setTimesInitDensity: float
    _setTimesDensityLength: int
    _setTimesDensityReliabilityThreshold: int
    _setTimesNbExtendsFactor: float
    _discreteLowCapacityLimit: int
    _lnsTrainingObjectiveLimit: float
    _posAbsentRelated: bool
    _defaultCallbackBlockSize: int
    _useReservoirPegging: bool
    _useTimeNet: bool
    _timeNetVarsToPreprocess: int
    _timeNetSubPriorityBits: int


    workers: list[WorkerParameters]
    r"""
    Per-worker parameter overrides.

    Each worker can have its own parameters. If a parameter is not specified
    for a worker, then the global value is used.

    Note that parameter :attr:`Parameters.nbWorkers` specifies the number of
    workers regardless of the length of this list.

    .. seealso::

        - :class:`WorkerParameters` for the list of parameters that can be set per worker.
    """

    pythonStreamBufferSize: int
    r"""
    Size of the buffer for streaming solver output to Python.

    The solver output (logs) is streamed to Python in chunks of this size (in bytes).
    The default value is 2 MB (2097152 bytes).

    This parameter is Python-specific and does not exist in other APIs.
    """

    printLog: IO[str] | bool
    r"""
    Where to write solver log output.

    Controls where solver log messages, warnings, and errors are written during solving.

    - `None` (default): Write to console (`sys.stdout`)
    - `False`: Suppress all output
    - `True`: Write to console (explicit)
    - File-like object: Write to the provided stream

    Note that setting `printLog` to `False` only suppresses writing to the output stream. The solver still emits `log`, `warning`, and `error` events that can be intercepted using callback properties (:attr:`Solver.on_log`, :attr:`Solver.on_warning`, :attr:`Solver.on_error`). To reduce the amount of logging at the source, use :attr:`Parameters.logLevel`.

    **ANSI colors:** When writing to a stream, the solver automatically detects whether the stream supports colors by checking if it is a TTY. To override automatic detection, use the :attr:`Parameters.color` parameter.

    If the output stream becomes non-writable (e.g., a broken pipe), then the solver stops as soon as possible.

    .. code-block:: python

        # Default - logs to console
        result = model.solve()

        # Silent - no output
        result = model.solve({'printLog': False})

        # Custom stream
        with open('solver.log', 'w') as f:
            result = model.solve({'printLog': f})

    .. seealso::

        - :attr:`Parameters.logLevel` to control verbosity.
        - :attr:`Parameters.color` to override automatic color detection.
    """

    solver: str
    r"""
    Path to the solver executable or WebSocket URL.

    Specifies how to connect to the solver.

    The value should be a path to the `optalcp` executable (e.g., `/usr/bin/optalcp`).
    The API spawns the solver as a subprocess.

    If not specified, the solver is searched as described in :meth:`Solver.find_solver`.

    .. seealso::

        - :meth:`Solver.find_solver` for solver discovery logic.
        - :attr:`Parameters.solverArgs` for additional subprocess arguments.
    """

    solverArgs: list[str]
    r"""
    Additional command-line arguments for the solver subprocess.

    These arguments are passed directly to the solver subprocess when it is spawned.
    This parameter is only used in subprocess mode (not when connecting to a remote
    solver via WebSocket).

    This can be useful for debugging or passing special flags to the solver that are
    not exposed through the Parameters API.

    .. code-block:: python

        import optalcp as cp

        model = cp.Model()
        # ... build model ...

        # Pass custom arguments to the solver
        result = model.solve({
            'solverArgs': ['--some-debug-flag'],
            'timeLimit': 60
        })

    .. seealso::

        - :attr:`Parameters.solver` to specify a custom solver path.
    """


# Python-specific fields to exclude from JSON serialization
_PYTHON_SPECIFIC_FIELDS = frozenset({'pythonStreamBufferSize', 'printLog', 'solver', 'solverArgs'})


def _parse_infinities(obj: dict[str, Any]) -> None:
    """Convert JSON infinity strings to Python float values."""
    for key in list(obj.keys()):
        if obj[key] == 'Infinity':
            obj[key] = float('inf')
        elif obj[key] == '-Infinity':
            obj[key] = float('-inf')


def _infinities_to_string(obj: dict[str, Any]) -> None:
    """Convert float infinity values to JSON-compatible strings."""
    for key in list(obj.keys()):
        if obj[key] == float('inf'):
            obj[key] = 'Infinity'
        elif obj[key] == float('-inf'):
            obj[key] = '-Infinity'


def _worker_parameters_to_json(params: WorkerParameters | None) -> dict[str, Any]:
    """Convert WorkerParameters to a JSON-serializable dict."""
    if params is None:
        return {}
    result = dict(params)
    _infinities_to_string(result)
    return result


def _worker_parameters_from_json(data: dict[str, Any] | None) -> WorkerParameters:
    """Convert a JSON dict back to WorkerParameters."""
    if data is None:
        return {}  # type: ignore[return-value]
    result = dict(data)
    _parse_infinities(result)
    return result  # type: ignore[return-value]


def _parameters_to_json(params: Parameters | None) -> dict[str, Any]:
    """
    Convert Parameters to a JSON-serializable dict for the solver.

    - Excludes Python-specific fields
    - Converts infinity values to strings
    - Recursively processes the workers array
    """
    if params is None:
        return {}

    result = {k: v for k, v in params.items() if k not in _PYTHON_SPECIFIC_FIELDS}

    # Handle workers array
    if workers := result.get('workers'):
        result['workers'] = [_worker_parameters_to_json(w) for w in cast(list[Any], workers)]

    # Convert infinities
    _infinities_to_string(result)

    return result


def _parameters_from_json(data: dict[str, Any] | None) -> Parameters:
    """
    Convert a JSON dict back to Parameters.

    - Parses infinity strings back to float values
    - Recursively processes the workers array
    """
    if data is None:
        return {}  # type: ignore[return-value]

    result = dict(data)
    _parse_infinities(result)

    # Handle workers array
    if workers := result.get('workers'):
        result['workers'] = [_worker_parameters_from_json(w) for w in cast(list[Any], workers)]

    return result  # type: ignore[return-value]


# printLog can be IO[str] which is not clonable
_NON_CLONABLE_FIELDS = frozenset({'printLog'})


def copy_parameters(params: Parameters) -> Parameters:
    r"""
    Creates a deep copy of the input Parameters object.

    :param params: The Parameters object to copy
    :type params: Parameters
    :rtype: Parameters
    :returns: A deep copy of the input Parameters object.

    ## Details

    Creates a deep copy of the input :class:`Parameters` object.
    Afterwards, the copy can be modified without affecting
    the original :class:`Parameters` object.

    The `printLog` field, when set to an IO object, is copied by reference
    (not deep-copied).

    .. code-block:: python

        import optalcp as cp

        params: cp.Parameters = {"timeLimit": 60, "nbWorkers": 4}
        copy = cp.copy_parameters(params)
        copy["timeLimit"] = 120  # Does not affect original params
    """
    # Extract non-clonable fields
    non_clonable = {k: params[k] for k in _NON_CLONABLE_FIELDS if k in params}  # type: ignore[literal-required]

    # Deep copy the rest
    to_copy = {k: v for k, v in params.items() if k not in _NON_CLONABLE_FIELDS}
    result: Parameters = copy.deepcopy(to_copy)  # type: ignore[assignment]

    # Restore non-clonable fields (same reference)
    result.update(non_clonable)  # type: ignore[typeddict-item]
    return result


def merge_parameters(base: Parameters, overrides: Parameters) -> Parameters:
    r"""
    Merges two Parameters settings into a new one.

    :param base: Base parameters that can be overridden
    :type base: Parameters
    :param overrides: Parameters that will overwrite values from base
    :type overrides: Parameters
    :rtype: Parameters
    :returns: The merged parameters object

    ## Details

    The new object contains all parameters from both inputs. If the same
    parameter is specified in both input objects, then the value from `overrides`
    is used.

    Input objects are not modified.

    .. code-block:: python

        import optalcp as cp

        defaults: cp.Parameters = {"timeLimit": 60, "nbWorkers": 4}
        overrides: cp.Parameters = {"timeLimit": 120}
        merged = cp.merge_parameters(defaults, overrides)
        # merged = {"timeLimit": 120, "nbWorkers": 4}
    """
    result = copy_parameters(base)
    for key, value in overrides.items():
        if key == 'workers':
            continue
        result[key] = value  # type: ignore[literal-required]

    override_workers = overrides.get('workers')
    if override_workers is not None:
        result_workers: list[WorkerParameters | None] = result.get('workers', [])  # type: ignore[assignment]
        result['workers'] = result_workers  # type: ignore[typeddict-item]
        for i, w in enumerate(override_workers):
            if w is None:
                continue
            # Extend list if needed
            while len(result_workers) <= i:
                result_workers.append(None)
            if result_workers[i] is None:
                result_workers[i] = dict(w)  # type: ignore[call-overload]
            else:
                result_workers[i].update(w)  # type: ignore[union-attr]
    return result


# =============================================================================
# Command-line argument parsing
# =============================================================================


def _parse_int(value: str, param_name: str) -> int:
    """Parse string to int, raising ValueError on failure."""
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Value '{value}' for parameter {param_name} is not an integer.") from e


def _parse_float(value: str, param_name: str) -> float:
    """Parse string to float, raising ValueError on failure."""
    try:
        return float(value)
    except ValueError as e:
        raise ValueError(f"Value '{value}' for parameter {param_name} is not a number.") from e


def _parse_bool(value: str, param_name: str) -> bool:
    """Parse string to bool (case-insensitive)."""
    lower = value.lower()
    if lower in ('1', 't', 'true', 'y', 'yes'):
        return True
    if lower in ('0', 'f', 'false', 'n', 'no'):
        return False
    raise ValueError(f"Value '{value}' for parameter {param_name} is not a boolean.")


def _parse_enum(value: str, param_name: str, valid_values: list[str]) -> str:
    """Parse string to enum value (case-insensitive)."""
    lower_value = value.lower()
    for valid in valid_values:
        if valid.lower() == lower_value:
            return valid
    valid_str = ', '.join(valid_values)
    raise ValueError(f"Value '{value}' for parameter {param_name} is not valid. Valid values: {valid_str}")


def _validate_int_range(value: int, param_name: str, min_val: int, max_val: int) -> int:
    """Validate integer is within range."""
    if value < min_val or value > max_val:
        raise ValueError(f"Parameter {param_name}: value {value} is not in required range {min_val}..{max_val}.")
    return value


def _validate_float_range(value: float, param_name: str, min_val: float, max_val: float) -> float:
    """Validate float is within range."""
    if value < min_val or value > max_val:
        raise ValueError(f"Parameter {param_name}: value {value} is not in required range {min_val}..{max_val}.")
    return value


@dataclass
class _ParserConfigEntry:
    """Parser configuration entry for a single parameter."""

    name: str
    parse: Callable[[str, str], Any]
    set_globally: Callable[[Parameters, Any], None]
    set_on_worker: Callable[[WorkerParameters, Any], None] | None = None


_PARSER_CONFIG: dict[str, _ParserConfigEntry] = {
    'solver': _ParserConfigEntry(
        name='Solver',
        parse=lambda v, n: v,
        set_globally=lambda p, v: p.__setitem__('solver', v),  # type: ignore[typeddict-item]
    ),
    'color': _ParserConfigEntry(
        name='Color',
        parse=lambda v, n: _parse_enum(v, n, ['Never', 'Auto', 'Always']),  # type: ignore[misc]
        set_globally=lambda p, v, k='color': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'nbworkers': _ParserConfigEntry(
        name='NbWorkers',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='nbWorkers': p.__setitem__(k, _validate_int_range(v, 'NbWorkers', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'nbhelpers': _ParserConfigEntry(
        name='NbHelpers',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_nbHelpers': p.__setitem__(k, _validate_int_range(v, 'NbHelpers', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'preset': _ParserConfigEntry(
        name='Preset',
        parse=lambda v, n: _parse_enum(v, n, ['Auto', 'Default', 'Large']),  # type: ignore[misc]
        set_globally=lambda p, v, k='preset': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'searchtype': _ParserConfigEntry(
        name='SearchType',
        parse=lambda v, n: _parse_enum(v, n, ['Auto', 'LNS', 'FDS', 'FDSDual', 'SetTimes', 'FDSLB']),  # type: ignore[misc]
        set_globally=lambda p, v, k='searchType': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='searchType': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'randomseed': _ParserConfigEntry(
        name='RandomSeed',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='randomSeed': p.__setitem__(k, _validate_int_range(v, 'RandomSeed', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='randomSeed': w.__setitem__(k, _validate_int_range(v, 'RandomSeed', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'loglevel': _ParserConfigEntry(
        name='LogLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='logLevel': p.__setitem__(k, _validate_int_range(v, 'LogLevel', 0, 3)),  # type: ignore[misc, attr-defined]
    ),
    'warninglevel': _ParserConfigEntry(
        name='WarningLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='warningLevel': p.__setitem__(k, _validate_int_range(v, 'WarningLevel', 0, 3)),  # type: ignore[misc, attr-defined]
    ),
    'logperiod': _ParserConfigEntry(
        name='LogPeriod',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='logPeriod': p.__setitem__(k, _validate_float_range(v, 'LogPeriod', 0.010000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'verifysolutions': _ParserConfigEntry(
        name='VerifySolutions',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='verifySolutions': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'verifyexternalsolutions': _ParserConfigEntry(
        name='VerifyExternalSolutions',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='verifyExternalSolutions': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'allocationblocksize': _ParserConfigEntry(
        name='AllocationBlockSize',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='allocationBlockSize': p.__setitem__(k, _validate_int_range(v, 'AllocationBlockSize', 4, 1073741824)),  # type: ignore[misc, attr-defined]
    ),
    'processexittimeout': _ParserConfigEntry(
        name='ProcessExitTimeout',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='processExitTimeout': p.__setitem__(k, _validate_float_range(v, 'ProcessExitTimeout', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'timelimit': _ParserConfigEntry(
        name='TimeLimit',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='timeLimit': p.__setitem__(k, _validate_float_range(v, 'TimeLimit', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'solutionlimit': _ParserConfigEntry(
        name='SolutionLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='solutionLimit': p.__setitem__(k, _validate_int_range(v, 'SolutionLimit', 0, 18446744073709551615)),  # type: ignore[misc, attr-defined]
    ),
    'workerfaillimit': _ParserConfigEntry(
        name='WorkerFailLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_workerFailLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_workerFailLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'workerbranchlimit': _ParserConfigEntry(
        name='WorkerBranchLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_workerBranchLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_workerBranchLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'workersolutionlimit': _ParserConfigEntry(
        name='WorkerSolutionLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_workerSolutionLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_workerSolutionLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'workerlnssteplimit': _ParserConfigEntry(
        name='WorkerLNSStepLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_workerLNSStepLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_workerLNSStepLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'workerrestartlimit': _ParserConfigEntry(
        name='WorkerRestartLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_workerRestartLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_workerRestartLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'absolutegaptolerance': _ParserConfigEntry(
        name='AbsoluteGapTolerance',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='absoluteGapTolerance': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'relativegaptolerance': _ParserConfigEntry(
        name='RelativeGapTolerance',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='relativeGapTolerance': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'tagsfromnames': _ParserConfigEntry(
        name='TagsFromNames',
        parse=lambda v, n: _parse_enum(v, n, ['Never', 'Auto', 'Merge', 'Force']),  # type: ignore[misc]
        set_globally=lambda p, v, k='_tagsFromNames': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'nooverlappropagationlevel': _ParserConfigEntry(
        name='NoOverlapPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='noOverlapPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'NoOverlapPropagationLevel', 0, 4)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='noOverlapPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'NoOverlapPropagationLevel', 0, 4)),  # type: ignore[misc, attr-defined]
    ),
    'cumulpropagationlevel': _ParserConfigEntry(
        name='CumulPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='cumulPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'CumulPropagationLevel', 0, 3)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='cumulPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'CumulPropagationLevel', 0, 3)),  # type: ignore[misc, attr-defined]
    ),
    'reservoirpropagationlevel': _ParserConfigEntry(
        name='ReservoirPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='reservoirPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'ReservoirPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='reservoirPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'ReservoirPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
    ),
    'positionpropagationlevel': _ParserConfigEntry(
        name='PositionPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='positionPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'PositionPropagationLevel', 1, 3)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='positionPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'PositionPropagationLevel', 1, 3)),  # type: ignore[misc, attr-defined]
    ),
    'integralpropagationlevel': _ParserConfigEntry(
        name='IntegralPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='integralPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'IntegralPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='integralPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'IntegralPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
    ),
    'useprecedenceenergy': _ParserConfigEntry(
        name='UsePrecedenceEnergy',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='usePrecedenceEnergy': p.__setitem__(k, _validate_int_range(v, 'UsePrecedenceEnergy', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'packpropagationlevel': _ParserConfigEntry(
        name='PackPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_packPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'PackPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_packPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'PackPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
    ),
    'itvmappingpropagationlevel': _ParserConfigEntry(
        name='ItvMappingPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_itvMappingPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'ItvMappingPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_itvMappingPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'ItvMappingPropagationLevel', 1, 2)),  # type: ignore[misc, attr-defined]
    ),
    'searchtracelevel': _ParserConfigEntry(
        name='SearchTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='searchTraceLevel': p.__setitem__(k, _validate_int_range(v, 'SearchTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='searchTraceLevel': w.__setitem__(k, _validate_int_range(v, 'SearchTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'propagationtracelevel': _ParserConfigEntry(
        name='PropagationTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='propagationTraceLevel': p.__setitem__(k, _validate_int_range(v, 'PropagationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='propagationTraceLevel': w.__setitem__(k, _validate_int_range(v, 'PropagationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'infotracelevel': _ParserConfigEntry(
        name='InfoTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='infoTraceLevel': p.__setitem__(k, _validate_int_range(v, 'InfoTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'fdsinitialrating': _ParserConfigEntry(
        name='FDSInitialRating',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsInitialRating': p.__setitem__(k, _validate_float_range(v, 'FDSInitialRating', 0.000000, 2.000000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsInitialRating': w.__setitem__(k, _validate_float_range(v, 'FDSInitialRating', 0.000000, 2.000000)),  # type: ignore[misc, attr-defined]
    ),
    'fdsreductionweight': _ParserConfigEntry(
        name='FDSReductionWeight',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsReductionWeight': p.__setitem__(k, _validate_float_range(v, 'FDSReductionWeight', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsReductionWeight': w.__setitem__(k, _validate_float_range(v, 'FDSReductionWeight', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'fdsratingaveragelength': _ParserConfigEntry(
        name='FDSRatingAverageLength',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsRatingAverageLength': p.__setitem__(k, _validate_int_range(v, 'FDSRatingAverageLength', 0, 254)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsRatingAverageLength': w.__setitem__(k, _validate_int_range(v, 'FDSRatingAverageLength', 0, 254)),  # type: ignore[misc, attr-defined]
    ),
    'fdsfixedalpha': _ParserConfigEntry(
        name='FDSFixedAlpha',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsFixedAlpha': p.__setitem__(k, _validate_float_range(v, 'FDSFixedAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsFixedAlpha': w.__setitem__(k, _validate_float_range(v, 'FDSFixedAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'fdsratingaveragecomparison': _ParserConfigEntry(
        name='FDSRatingAverageComparison',
        parse=lambda v, n: _parse_enum(v, n, ['Off', 'Global', 'Depth']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsRatingAverageComparison': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsRatingAverageComparison': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsreductionfactor': _ParserConfigEntry(
        name='FDSReductionFactor',
        parse=lambda v, n: _parse_enum(v, n, ['Normal', 'Zero', 'Random']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsReductionFactor': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsReductionFactor': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsreuseclosing': _ParserConfigEntry(
        name='FDSReuseClosing',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsReuseClosing': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsReuseClosing': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsuniformchoicestep': _ParserConfigEntry(
        name='FDSUniformChoiceStep',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsUniformChoiceStep': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsUniformChoiceStep': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdslengthstepratio': _ParserConfigEntry(
        name='FDSLengthStepRatio',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsLengthStepRatio': p.__setitem__(k, _validate_float_range(v, 'FDSLengthStepRatio', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsLengthStepRatio': w.__setitem__(k, _validate_float_range(v, 'FDSLengthStepRatio', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'fdsmaxinitialchoicespervariable': _ParserConfigEntry(
        name='FDSMaxInitialChoicesPerVariable',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMaxInitialChoicesPerVariable': p.__setitem__(k, _validate_int_range(v, 'FDSMaxInitialChoicesPerVariable', 2, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMaxInitialChoicesPerVariable': w.__setitem__(k, _validate_int_range(v, 'FDSMaxInitialChoicesPerVariable', 2, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'fdsadditionalstepratio': _ParserConfigEntry(
        name='FDSAdditionalStepRatio',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsAdditionalStepRatio': p.__setitem__(k, _validate_float_range(v, 'FDSAdditionalStepRatio', 2.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsAdditionalStepRatio': w.__setitem__(k, _validate_float_range(v, 'FDSAdditionalStepRatio', 2.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'fdspresencestatuschoices': _ParserConfigEntry(
        name='FDSPresenceStatusChoices',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsPresenceStatusChoices': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsPresenceStatusChoices': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsmaxinitiallengthchoices': _ParserConfigEntry(
        name='FDSMaxInitialLengthChoices',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMaxInitialLengthChoices': p.__setitem__(k, _validate_int_range(v, 'FDSMaxInitialLengthChoices', 0, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMaxInitialLengthChoices': w.__setitem__(k, _validate_int_range(v, 'FDSMaxInitialLengthChoices', 0, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'fdsminlengthchoicestep': _ParserConfigEntry(
        name='FDSMinLengthChoiceStep',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMinLengthChoiceStep': p.__setitem__(k, _validate_int_range(v, 'FDSMinLengthChoiceStep', 1, 1073741823)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMinLengthChoiceStep': w.__setitem__(k, _validate_int_range(v, 'FDSMinLengthChoiceStep', 1, 1073741823)),  # type: ignore[misc, attr-defined]
    ),
    'fdsminintvarchoicestep': _ParserConfigEntry(
        name='FDSMinIntVarChoiceStep',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMinIntVarChoiceStep': p.__setitem__(k, _validate_int_range(v, 'FDSMinIntVarChoiceStep', 1, 1073741823)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMinIntVarChoiceStep': w.__setitem__(k, _validate_int_range(v, 'FDSMinIntVarChoiceStep', 1, 1073741823)),  # type: ignore[misc, attr-defined]
    ),
    'fdseventtimeinfluence': _ParserConfigEntry(
        name='FDSEventTimeInfluence',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsEventTimeInfluence': p.__setitem__(k, _validate_float_range(v, 'FDSEventTimeInfluence', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsEventTimeInfluence': w.__setitem__(k, _validate_float_range(v, 'FDSEventTimeInfluence', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'fdsbothfailrewardfactor': _ParserConfigEntry(
        name='FDSBothFailRewardFactor',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsBothFailRewardFactor': p.__setitem__(k, _validate_float_range(v, 'FDSBothFailRewardFactor', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsBothFailRewardFactor': w.__setitem__(k, _validate_float_range(v, 'FDSBothFailRewardFactor', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'fdsepsilon': _ParserConfigEntry(
        name='FDSEpsilon',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsEpsilon': p.__setitem__(k, _validate_float_range(v, 'FDSEpsilon', 0.000000, 0.999990)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsEpsilon': w.__setitem__(k, _validate_float_range(v, 'FDSEpsilon', 0.000000, 0.999990)),  # type: ignore[misc, attr-defined]
    ),
    'fdsstrongbranchingsize': _ParserConfigEntry(
        name='FDSStrongBranchingSize',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsStrongBranchingSize': p.__setitem__(k, _validate_int_range(v, 'FDSStrongBranchingSize', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsStrongBranchingSize': w.__setitem__(k, _validate_int_range(v, 'FDSStrongBranchingSize', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'fdsstrongbranchingdepth': _ParserConfigEntry(
        name='FDSStrongBranchingDepth',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsStrongBranchingDepth': p.__setitem__(k, _validate_int_range(v, 'FDSStrongBranchingDepth', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsStrongBranchingDepth': w.__setitem__(k, _validate_int_range(v, 'FDSStrongBranchingDepth', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'fdsstrongbranchingcriterion': _ParserConfigEntry(
        name='FDSStrongBranchingCriterion',
        parse=lambda v, n: _parse_enum(v, n, ['Both', 'Left', 'Right']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsStrongBranchingCriterion': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsStrongBranchingCriterion': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsinitialrestartlimit': _ParserConfigEntry(
        name='FDSInitialRestartLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsInitialRestartLimit': p.__setitem__(k, _validate_int_range(v, 'FDSInitialRestartLimit', 1, 9223372036854775807)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsInitialRestartLimit': w.__setitem__(k, _validate_int_range(v, 'FDSInitialRestartLimit', 1, 9223372036854775807)),  # type: ignore[misc, attr-defined]
    ),
    'fdsrestartstrategy': _ParserConfigEntry(
        name='FDSRestartStrategy',
        parse=lambda v, n: _parse_enum(v, n, ['Geometric', 'Nested', 'Luby']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsRestartStrategy': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsRestartStrategy': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsrestartgrowthfactor': _ParserConfigEntry(
        name='FDSRestartGrowthFactor',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsRestartGrowthFactor': p.__setitem__(k, _validate_float_range(v, 'FDSRestartGrowthFactor', 1.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsRestartGrowthFactor': w.__setitem__(k, _validate_float_range(v, 'FDSRestartGrowthFactor', 1.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'fdsmaxcounterafterrestart': _ParserConfigEntry(
        name='FDSMaxCounterAfterRestart',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMaxCounterAfterRestart': p.__setitem__(k, _validate_int_range(v, 'FDSMaxCounterAfterRestart', 0, 255)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMaxCounterAfterRestart': w.__setitem__(k, _validate_int_range(v, 'FDSMaxCounterAfterRestart', 0, 255)),  # type: ignore[misc, attr-defined]
    ),
    'fdsmaxcounteraftersolution': _ParserConfigEntry(
        name='FDSMaxCounterAfterSolution',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsMaxCounterAfterSolution': p.__setitem__(k, _validate_int_range(v, 'FDSMaxCounterAfterSolution', 0, 255)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsMaxCounterAfterSolution': w.__setitem__(k, _validate_int_range(v, 'FDSMaxCounterAfterSolution', 0, 255)),  # type: ignore[misc, attr-defined]
    ),
    'fdsresetrestartsaftersolution': _ParserConfigEntry(
        name='FDSResetRestartsAfterSolution',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsResetRestartsAfterSolution': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsResetRestartsAfterSolution': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsusenogoods': _ParserConfigEntry(
        name='FDSUseNogoods',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsUseNogoods': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsUseNogoods': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsfreezeratingsafterproof': _ParserConfigEntry(
        name='FDSFreezeRatingsAfterProof',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsFreezeRatingsAfterProof': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsFreezeRatingsAfterProof': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdscontinueafterproof': _ParserConfigEntry(
        name='FDSContinueAfterProof',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsContinueAfterProof': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsContinueAfterProof': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsrepeatlimit': _ParserConfigEntry(
        name='FDSRepeatLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsRepeatLimit': p.__setitem__(k, _validate_int_range(v, 'FDSRepeatLimit', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsRepeatLimit': w.__setitem__(k, _validate_int_range(v, 'FDSRepeatLimit', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'fdscompletelyrandom': _ParserConfigEntry(
        name='FDSCompletelyRandom',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsCompletelyRandom': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsCompletelyRandom': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsbranchonobjective': _ParserConfigEntry(
        name='FDSBranchOnObjective',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsBranchOnObjective': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsBranchOnObjective': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsimprovenogoods': _ParserConfigEntry(
        name='FDSImproveNogoods',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsImproveNogoods': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsImproveNogoods': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsbranchordering': _ParserConfigEntry(
        name='FDSBranchOrdering',
        parse=lambda v, n: _parse_enum(v, n, ['FailureFirst', 'FailureLast', 'Random']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsBranchOrdering': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsBranchOrdering': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsdivebysettimes': _ParserConfigEntry(
        name='FDSDiveBySetTimes',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsDiveBySetTimes': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsDiveBySetTimes': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsdualstrategy': _ParserConfigEntry(
        name='FDSDualStrategy',
        parse=lambda v, n: _parse_enum(v, n, ['Minimum', 'Random', 'Split']),  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsDualStrategy': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsDualStrategy': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'fdsdualresetratings': _ParserConfigEntry(
        name='FDSDualResetRatings',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='fdsDualResetRatings': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='fdsDualResetRatings': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsinitnooverlappropagationlevel': _ParserConfigEntry(
        name='LNSInitNoOverlapPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsInitNoOverlapPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'LNSInitNoOverlapPropagationLevel', 0, 4)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsInitNoOverlapPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'LNSInitNoOverlapPropagationLevel', 0, 4)),  # type: ignore[misc, attr-defined]
    ),
    'lnsinitcumulpropagationlevel': _ParserConfigEntry(
        name='LNSInitCumulPropagationLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsInitCumulPropagationLevel': p.__setitem__(k, _validate_int_range(v, 'LNSInitCumulPropagationLevel', 0, 3)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsInitCumulPropagationLevel': w.__setitem__(k, _validate_int_range(v, 'LNSInitCumulPropagationLevel', 0, 3)),  # type: ignore[misc, attr-defined]
    ),
    'lnsfirstfaillimit': _ParserConfigEntry(
        name='LNSFirstFailLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsFirstFailLimit': p.__setitem__(k, _validate_int_range(v, 'LNSFirstFailLimit', 1, 18446744073709551615)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsFirstFailLimit': w.__setitem__(k, _validate_int_range(v, 'LNSFirstFailLimit', 1, 18446744073709551615)),  # type: ignore[misc, attr-defined]
    ),
    'lnsfaillimitgrowthfactor': _ParserConfigEntry(
        name='LNSFailLimitGrowthFactor',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsFailLimitGrowthFactor': p.__setitem__(k, _validate_float_range(v, 'LNSFailLimitGrowthFactor', 1.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsFailLimitGrowthFactor': w.__setitem__(k, _validate_float_range(v, 'LNSFailLimitGrowthFactor', 1.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'lnsfaillimitcoefficient': _ParserConfigEntry(
        name='LNSFailLimitCoefficient',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsFailLimitCoefficient': p.__setitem__(k, _validate_float_range(v, 'LNSFailLimitCoefficient', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsFailLimitCoefficient': w.__setitem__(k, _validate_float_range(v, 'LNSFailLimitCoefficient', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'lnsiterationsafterfirstsolution': _ParserConfigEntry(
        name='LNSIterationsAfterFirstSolution',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsIterationsAfterFirstSolution': p.__setitem__(k, _validate_int_range(v, 'LNSIterationsAfterFirstSolution', -1, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsIterationsAfterFirstSolution': w.__setitem__(k, _validate_int_range(v, 'LNSIterationsAfterFirstSolution', -1, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'lnsaggressivedominance': _ParserConfigEntry(
        name='LNSAggressiveDominance',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsAggressiveDominance': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsAggressiveDominance': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnssamesolutionperiod': _ParserConfigEntry(
        name='LNSSameSolutionPeriod',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsSameSolutionPeriod': p.__setitem__(k, _validate_int_range(v, 'LNSSameSolutionPeriod', 1, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsSameSolutionPeriod': w.__setitem__(k, _validate_int_range(v, 'LNSSameSolutionPeriod', 1, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'lnstier1size': _ParserConfigEntry(
        name='LNSTier1Size',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTier1Size': p.__setitem__(k, _validate_int_range(v, 'LNSTier1Size', 1, 1000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTier1Size': w.__setitem__(k, _validate_int_range(v, 'LNSTier1Size', 1, 1000)),  # type: ignore[misc, attr-defined]
    ),
    'lnstier2size': _ParserConfigEntry(
        name='LNSTier2Size',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTier2Size': p.__setitem__(k, _validate_int_range(v, 'LNSTier2Size', 0, 1000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTier2Size': w.__setitem__(k, _validate_int_range(v, 'LNSTier2Size', 0, 1000)),  # type: ignore[misc, attr-defined]
    ),
    'lnstier3size': _ParserConfigEntry(
        name='LNSTier3Size',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTier3Size': p.__setitem__(k, _validate_int_range(v, 'LNSTier3Size', 0, 1000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTier3Size': w.__setitem__(k, _validate_int_range(v, 'LNSTier3Size', 0, 1000)),  # type: ignore[misc, attr-defined]
    ),
    'lnstier2effort': _ParserConfigEntry(
        name='LNSTier2Effort',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTier2Effort': p.__setitem__(k, _validate_float_range(v, 'LNSTier2Effort', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTier2Effort': w.__setitem__(k, _validate_float_range(v, 'LNSTier2Effort', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
    ),
    'lnstier3effort': _ParserConfigEntry(
        name='LNSTier3Effort',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTier3Effort': p.__setitem__(k, _validate_float_range(v, 'LNSTier3Effort', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTier3Effort': w.__setitem__(k, _validate_float_range(v, 'LNSTier3Effort', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
    ),
    'lnsstepfaillimitfactor': _ParserConfigEntry(
        name='LNSStepFailLimitFactor',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsStepFailLimitFactor': p.__setitem__(k, _validate_float_range(v, 'LNSStepFailLimitFactor', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsStepFailLimitFactor': w.__setitem__(k, _validate_float_range(v, 'LNSStepFailLimitFactor', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'lnsapplycutprobability': _ParserConfigEntry(
        name='LNSApplyCutProbability',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsApplyCutProbability': p.__setitem__(k, _validate_float_range(v, 'LNSApplyCutProbability', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsApplyCutProbability': w.__setitem__(k, _validate_float_range(v, 'LNSApplyCutProbability', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnssmallstructurelimit': _ParserConfigEntry(
        name='LNSSmallStructureLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsSmallStructureLimit': p.__setitem__(k, _validate_int_range(v, 'LNSSmallStructureLimit', 0, 10)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsSmallStructureLimit': w.__setitem__(k, _validate_int_range(v, 'LNSSmallStructureLimit', 0, 10)),  # type: ignore[misc, attr-defined]
    ),
    'lnsresourceoptimization': _ParserConfigEntry(
        name='LNSResourceOptimization',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsResourceOptimization': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsResourceOptimization': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsrestoreabsentintervals': _ParserConfigEntry(
        name='LNSRestoreAbsentIntervals',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsRestoreAbsentIntervals': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsRestoreAbsentIntervals': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsrestoreintervallengths': _ParserConfigEntry(
        name='LNSRestoreIntervalLengths',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsRestoreIntervalLengths': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsRestoreIntervalLengths': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsrestoreintvarvalues': _ParserConfigEntry(
        name='LNSRestoreIntVarValues',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsRestoreIntVarValues': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsRestoreIntVarValues': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsusewarmstartonly': _ParserConfigEntry(
        name='LNSUseWarmStartOnly',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='lnsUseWarmStartOnly': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='lnsUseWarmStartOnly': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsheuristicsepsilon': _ParserConfigEntry(
        name='LNSHeuristicsEpsilon',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsHeuristicsEpsilon': p.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsHeuristicsEpsilon': w.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsheuristicsalpha': _ParserConfigEntry(
        name='LNSHeuristicsAlpha',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsHeuristicsAlpha': p.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsHeuristicsAlpha': w.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsheuristicstemperature': _ParserConfigEntry(
        name='LNSHeuristicsTemperature',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsHeuristicsTemperature': p.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsHeuristicsTemperature': w.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsheuristicsuniform': _ParserConfigEntry(
        name='LNSHeuristicsUniform',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsHeuristicsUniform': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsHeuristicsUniform': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsheuristicsinitialq': _ParserConfigEntry(
        name='LNSHeuristicsInitialQ',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsHeuristicsInitialQ': p.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsHeuristicsInitialQ': w.__setitem__(k, _validate_float_range(v, 'LNSHeuristicsInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionepsilon': _ParserConfigEntry(
        name='LNSPortionEpsilon',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionEpsilon': p.__setitem__(k, _validate_float_range(v, 'LNSPortionEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionEpsilon': w.__setitem__(k, _validate_float_range(v, 'LNSPortionEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionalpha': _ParserConfigEntry(
        name='LNSPortionAlpha',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionAlpha': p.__setitem__(k, _validate_float_range(v, 'LNSPortionAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionAlpha': w.__setitem__(k, _validate_float_range(v, 'LNSPortionAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportiontemperature': _ParserConfigEntry(
        name='LNSPortionTemperature',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionTemperature': p.__setitem__(k, _validate_float_range(v, 'LNSPortionTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionTemperature': w.__setitem__(k, _validate_float_range(v, 'LNSPortionTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionuniform': _ParserConfigEntry(
        name='LNSPortionUniform',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionUniform': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionUniform': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsportioninitialq': _ParserConfigEntry(
        name='LNSPortionInitialQ',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionInitialQ': p.__setitem__(k, _validate_float_range(v, 'LNSPortionInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionInitialQ': w.__setitem__(k, _validate_float_range(v, 'LNSPortionInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionhandicaplimit': _ParserConfigEntry(
        name='LNSPortionHandicapLimit',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionHandicapLimit': p.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapLimit', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionHandicapLimit': w.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapLimit', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionhandicapvalue': _ParserConfigEntry(
        name='LNSPortionHandicapValue',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionHandicapValue': p.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapValue', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionHandicapValue': w.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapValue', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionhandicapinitialq': _ParserConfigEntry(
        name='LNSPortionHandicapInitialQ',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionHandicapInitialQ': p.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionHandicapInitialQ': w.__setitem__(k, _validate_float_range(v, 'LNSPortionHandicapInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhoodstrategy': _ParserConfigEntry(
        name='LNSNeighborhoodStrategy',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodStrategy': p.__setitem__(k, _validate_int_range(v, 'LNSNeighborhoodStrategy', 0, 2)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodStrategy': w.__setitem__(k, _validate_int_range(v, 'LNSNeighborhoodStrategy', 0, 2)),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhoodepsilon': _ParserConfigEntry(
        name='LNSNeighborhoodEpsilon',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodEpsilon': p.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodEpsilon': w.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodEpsilon', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhoodalpha': _ParserConfigEntry(
        name='LNSNeighborhoodAlpha',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodAlpha': p.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodAlpha': w.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodAlpha', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhoodtemperature': _ParserConfigEntry(
        name='LNSNeighborhoodTemperature',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodTemperature': p.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodTemperature': w.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodTemperature', -1, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhooduniform': _ParserConfigEntry(
        name='LNSNeighborhoodUniform',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodUniform': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodUniform': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsneighborhoodinitialq': _ParserConfigEntry(
        name='LNSNeighborhoodInitialQ',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsNeighborhoodInitialQ': p.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsNeighborhoodInitialQ': w.__setitem__(k, _validate_float_range(v, 'LNSNeighborhoodInitialQ', 0, 1)),  # type: ignore[misc, attr-defined]
    ),
    'lnsdivinglimit': _ParserConfigEntry(
        name='LNSDivingLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsDivingLimit': p.__setitem__(k, _validate_int_range(v, 'LNSDivingLimit', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsDivingLimit': w.__setitem__(k, _validate_int_range(v, 'LNSDivingLimit', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'lnsdivingfaillimitratio': _ParserConfigEntry(
        name='LNSDivingFailLimitRatio',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsDivingFailLimitRatio': p.__setitem__(k, _validate_float_range(v, 'LNSDivingFailLimitRatio', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsDivingFailLimitRatio': w.__setitem__(k, _validate_float_range(v, 'LNSDivingFailLimitRatio', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'lnslearningrun': _ParserConfigEntry(
        name='LNSLearningRun',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsLearningRun': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsLearningRun': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsstayonobjective': _ParserConfigEntry(
        name='LNSStayOnObjective',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsStayOnObjective': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsStayOnObjective': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsfds': _ParserConfigEntry(
        name='LNSFDS',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsFDS': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsFDS': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsfreezeintervalsbeforefragment': _ParserConfigEntry(
        name='LNSFreezeIntervalsBeforeFragment',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsFreezeIntervalsBeforeFragment': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsFreezeIntervalsBeforeFragment': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'lnsrelaxslack': _ParserConfigEntry(
        name='LNSRelaxSlack',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsRelaxSlack': p.__setitem__(k, _validate_float_range(v, 'LNSRelaxSlack', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsRelaxSlack': w.__setitem__(k, _validate_float_range(v, 'LNSRelaxSlack', 0.000000, 1.000000)),  # type: ignore[misc, attr-defined]
    ),
    'lnsportionmultiplier': _ParserConfigEntry(
        name='LNSPortionMultiplier',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsPortionMultiplier': p.__setitem__(k, _validate_float_range(v, 'LNSPortionMultiplier', 0.010000, 10.000000)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsPortionMultiplier': w.__setitem__(k, _validate_float_range(v, 'LNSPortionMultiplier', 0.010000, 10.000000)),  # type: ignore[misc, attr-defined]
    ),
    'simplelbworker': _ParserConfigEntry(
        name='SimpleLBWorker',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='simpleLBWorker': p.__setitem__(k, _validate_int_range(v, 'SimpleLBWorker', -1, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='simpleLBWorker': w.__setitem__(k, _validate_int_range(v, 'SimpleLBWorker', -1, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'simplelbmaxiterations': _ParserConfigEntry(
        name='SimpleLBMaxIterations',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='simpleLBMaxIterations': p.__setitem__(k, _validate_int_range(v, 'SimpleLBMaxIterations', 0, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='simpleLBMaxIterations': w.__setitem__(k, _validate_int_range(v, 'SimpleLBMaxIterations', 0, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'simplelbshavingrounds': _ParserConfigEntry(
        name='SimpleLBShavingRounds',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='simpleLBShavingRounds': p.__setitem__(k, _validate_int_range(v, 'SimpleLBShavingRounds', 0, 2147483647)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='simpleLBShavingRounds': w.__setitem__(k, _validate_int_range(v, 'SimpleLBShavingRounds', 0, 2147483647)),  # type: ignore[misc, attr-defined]
    ),
    'debugtracelevel': _ParserConfigEntry(
        name='DebugTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_debugTraceLevel': p.__setitem__(k, _validate_int_range(v, 'DebugTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_debugTraceLevel': w.__setitem__(k, _validate_int_range(v, 'DebugTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'memorytracelevel': _ParserConfigEntry(
        name='MemoryTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_memoryTraceLevel': p.__setitem__(k, _validate_int_range(v, 'MemoryTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_memoryTraceLevel': w.__setitem__(k, _validate_int_range(v, 'MemoryTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'propagationdetailtracelevel': _ParserConfigEntry(
        name='PropagationDetailTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_propagationDetailTraceLevel': p.__setitem__(k, _validate_int_range(v, 'PropagationDetailTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_propagationDetailTraceLevel': w.__setitem__(k, _validate_int_range(v, 'PropagationDetailTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'settimestracelevel': _ParserConfigEntry(
        name='SetTimesTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesTraceLevel': p.__setitem__(k, _validate_int_range(v, 'SetTimesTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesTraceLevel': w.__setitem__(k, _validate_int_range(v, 'SetTimesTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'communicationtracelevel': _ParserConfigEntry(
        name='CommunicationTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_communicationTraceLevel': p.__setitem__(k, _validate_int_range(v, 'CommunicationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_communicationTraceLevel': w.__setitem__(k, _validate_int_range(v, 'CommunicationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'presolvetracelevel': _ParserConfigEntry(
        name='PresolveTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_presolveTraceLevel': p.__setitem__(k, _validate_int_range(v, 'PresolveTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'conversiontracelevel': _ParserConfigEntry(
        name='ConversionTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_conversionTraceLevel': p.__setitem__(k, _validate_int_range(v, 'ConversionTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_conversionTraceLevel': w.__setitem__(k, _validate_int_range(v, 'ConversionTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'expressionbuildertracelevel': _ParserConfigEntry(
        name='ExpressionBuilderTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_expressionBuilderTraceLevel': p.__setitem__(k, _validate_int_range(v, 'ExpressionBuilderTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_expressionBuilderTraceLevel': w.__setitem__(k, _validate_int_range(v, 'ExpressionBuilderTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'memorizationtracelevel': _ParserConfigEntry(
        name='MemorizationTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_memorizationTraceLevel': p.__setitem__(k, _validate_int_range(v, 'MemorizationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_memorizationTraceLevel': w.__setitem__(k, _validate_int_range(v, 'MemorizationTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'searchdetailtracelevel': _ParserConfigEntry(
        name='SearchDetailTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_searchDetailTraceLevel': p.__setitem__(k, _validate_int_range(v, 'SearchDetailTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_searchDetailTraceLevel': w.__setitem__(k, _validate_int_range(v, 'SearchDetailTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'fdstracelevel': _ParserConfigEntry(
        name='FDSTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsTraceLevel': p.__setitem__(k, _validate_int_range(v, 'FDSTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsTraceLevel': w.__setitem__(k, _validate_int_range(v, 'FDSTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'shavingtracelevel': _ParserConfigEntry(
        name='ShavingTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_shavingTraceLevel': p.__setitem__(k, _validate_int_range(v, 'ShavingTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_shavingTraceLevel': w.__setitem__(k, _validate_int_range(v, 'ShavingTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'fdsratingstracelevel': _ParserConfigEntry(
        name='FDSRatingsTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_fdsRatingsTraceLevel': p.__setitem__(k, _validate_int_range(v, 'FDSRatingsTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_fdsRatingsTraceLevel': w.__setitem__(k, _validate_int_range(v, 'FDSRatingsTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'lnstracelevel': _ParserConfigEntry(
        name='LNSTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTraceLevel': p.__setitem__(k, _validate_int_range(v, 'LNSTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTraceLevel': w.__setitem__(k, _validate_int_range(v, 'LNSTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'heuristicreplaytracelevel': _ParserConfigEntry(
        name='HeuristicReplayTraceLevel',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_heuristicReplayTraceLevel': p.__setitem__(k, _validate_int_range(v, 'HeuristicReplayTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_heuristicReplayTraceLevel': w.__setitem__(k, _validate_int_range(v, 'HeuristicReplayTraceLevel', 0, 5)),  # type: ignore[misc, attr-defined]
    ),
    'allowsettimesproofs': _ParserConfigEntry(
        name='AllowSetTimesProofs',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_allowSetTimesProofs': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_allowSetTimesProofs': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'settimesaggressivedominance': _ParserConfigEntry(
        name='SetTimesAggressiveDominance',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesAggressiveDominance': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesAggressiveDominance': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'settimesextendscoef': _ParserConfigEntry(
        name='SetTimesExtendsCoef',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesExtendsCoef': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesExtendsCoef': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'settimesheightstrategy': _ParserConfigEntry(
        name='SetTimesHeightStrategy',
        parse=lambda v, n: _parse_enum(v, n, ['FromMax', 'FromMin', 'Random']),  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesHeightStrategy': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesHeightStrategy': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'settimesitvmappingstrategy': _ParserConfigEntry(
        name='SetTimesItvMappingStrategy',
        parse=lambda v, n: _parse_enum(v, n, ['FromMax', 'FromMin', 'Random']),  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesItvMappingStrategy': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesItvMappingStrategy': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'settimesinitdensity': _ParserConfigEntry(
        name='SetTimesInitDensity',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesInitDensity': p.__setitem__(k, _validate_float_range(v, 'SetTimesInitDensity', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesInitDensity': w.__setitem__(k, _validate_float_range(v, 'SetTimesInitDensity', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'settimesdensitylength': _ParserConfigEntry(
        name='SetTimesDensityLength',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesDensityLength': p.__setitem__(k, _validate_int_range(v, 'SetTimesDensityLength', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesDensityLength': w.__setitem__(k, _validate_int_range(v, 'SetTimesDensityLength', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'settimesdensityreliabilitythreshold': _ParserConfigEntry(
        name='SetTimesDensityReliabilityThreshold',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesDensityReliabilityThreshold': p.__setitem__(k, _validate_int_range(v, 'SetTimesDensityReliabilityThreshold', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesDensityReliabilityThreshold': w.__setitem__(k, _validate_int_range(v, 'SetTimesDensityReliabilityThreshold', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'settimesnbextendsfactor': _ParserConfigEntry(
        name='SetTimesNbExtendsFactor',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_setTimesNbExtendsFactor': p.__setitem__(k, _validate_float_range(v, 'SetTimesNbExtendsFactor', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_setTimesNbExtendsFactor': w.__setitem__(k, _validate_float_range(v, 'SetTimesNbExtendsFactor', 0.000000, float('inf'))),  # type: ignore[misc, attr-defined]
    ),
    'discretelowcapacitylimit': _ParserConfigEntry(
        name='DiscreteLowCapacityLimit',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_discreteLowCapacityLimit': p.__setitem__(k, _validate_int_range(v, 'DiscreteLowCapacityLimit', 0, 16)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_discreteLowCapacityLimit': w.__setitem__(k, _validate_int_range(v, 'DiscreteLowCapacityLimit', 0, 16)),  # type: ignore[misc, attr-defined]
    ),
    'lnstrainingobjectivelimit': _ParserConfigEntry(
        name='LNSTrainingObjectiveLimit',
        parse=_parse_float,  # type: ignore[misc]
        set_globally=lambda p, v, k='_lnsTrainingObjectiveLimit': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_lnsTrainingObjectiveLimit': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'posabsentrelated': _ParserConfigEntry(
        name='POSAbsentRelated',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_posAbsentRelated': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_posAbsentRelated': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'defaultcallbackblocksize': _ParserConfigEntry(
        name='DefaultCallbackBlockSize',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_defaultCallbackBlockSize': p.__setitem__(k, _validate_int_range(v, 'DefaultCallbackBlockSize', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_defaultCallbackBlockSize': w.__setitem__(k, _validate_int_range(v, 'DefaultCallbackBlockSize', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'usereservoirpegging': _ParserConfigEntry(
        name='UseReservoirPegging',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_useReservoirPegging': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_useReservoirPegging': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'usetimenet': _ParserConfigEntry(
        name='UseTimeNet',
        parse=_parse_bool,  # type: ignore[misc]
        set_globally=lambda p, v, k='_useTimeNet': p.__setitem__(k, v),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_useTimeNet': w.__setitem__(k, v),  # type: ignore[misc, attr-defined]
    ),
    'timenetvarstopreprocess': _ParserConfigEntry(
        name='TimeNetVarsToPreprocess',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_timeNetVarsToPreprocess': p.__setitem__(k, _validate_int_range(v, 'TimeNetVarsToPreprocess', 0, 4294967295)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_timeNetVarsToPreprocess': w.__setitem__(k, _validate_int_range(v, 'TimeNetVarsToPreprocess', 0, 4294967295)),  # type: ignore[misc, attr-defined]
    ),
    'timenetsubprioritybits': _ParserConfigEntry(
        name='TimeNetSubPriorityBits',
        parse=_parse_int,  # type: ignore[misc]
        set_globally=lambda p, v, k='_timeNetSubPriorityBits': p.__setitem__(k, _validate_int_range(v, 'TimeNetSubPriorityBits', 4, 20)),  # type: ignore[misc, attr-defined]
        set_on_worker=lambda w, v, k='_timeNetSubPriorityBits': w.__setitem__(k, _validate_int_range(v, 'TimeNetSubPriorityBits', 4, 20)),  # type: ignore[misc, attr-defined]
    ),

}

_PARAMETERS_HELP = """\
Help:
  --help, -h                       Print this help
  --optalcpVersion                 Print OptalCP version information

Solver path:
  --solver string                  Path to the solver

Terminal output:
  --color Never|Auto|Always        Whether to colorize output to the terminal

Major options:
  --nbWorkers uint32               Number of threads dedicated to search
  --preset Auto|Default|Large      Preset configuration for solver parameters
  --searchType Auto|LNS|FDS|FDSDual|SetTimes|FDSLB
                                   Type of search to use
  --randomSeed uint32              Random seed
  --logLevel uint32                Level of the log
  --warningLevel uint32            Level of warnings
  --logPeriod double               How often to print log messages (in seconds)
  --verifySolutions bool           When on, the correctness of solutions is verified
  --verifyExternalSolutions bool   Whether to verify corectness of external solutions
  --allocationBlockSize uint32     The minimal amount of memory in kB for a single allocation
  --processExitTimeout double      Timeout for solver process to exit after finishing

Limits:
  --timeLimit double               Wall clock limit for execution
  --solutionLimit uint64           Stop the search after the given number of solutions

Gap Tolerance:
  --absoluteGapTolerance double    Stop the search when the gap is below the tolerance
  --relativeGapTolerance double    Stop the search when the gap is below the tolerance

Propagation levels:
  --noOverlapPropagationLevel uint32
                                   How much to propagate noOverlap constraints
  --cumulPropagationLevel uint32   How much to propagate constraints on cumul functions
  --reservoirPropagationLevel uint32
                                   How much to propagate constraints on cumul functions
  --positionPropagationLevel uint32
                                   How much to propagate position expressions on noOverlap constraints
  --integralPropagationLevel uint32
                                   How much to propagate stepFunctionSum expression
  --usePrecedenceEnergy uint32     Whether to use precedence energy propagation algorithm

Failure-Directed Search:
  --fdsInitialRating double        Initial rating for newly created choices
  --fdsReductionWeight double      Weight of the reduction factor in rating computation
  --fdsRatingAverageLength int32   Length of average rating computed for choices
  --fdsFixedAlpha double           When non-zero, alpha factor for rating updates
  --fdsRatingAverageComparison Off|Global|Depth
                                   Whether to compare the local rating with the average
  --fdsReductionFactor Normal|Zero|Random
                                   Reduction factor R for rating computation
  --fdsReuseClosing bool           Whether always reuse closing choice
  --fdsUniformChoiceStep bool      Whether all initial choices have the same step length
  --fdsLengthStepRatio double      Choice step relative to average length
  --fdsMaxInitialChoicesPerVariable uint32
                                   Maximum number of choices generated initially per a variable
  --fdsAdditionalStepRatio double  Domain split ratio when run out of choices
  --fdsPresenceStatusChoices bool  Whether to generate choices on presence status
  --fdsMaxInitialLengthChoices uint32
                                   Maximum number of initial choices on length of an interval variable
  --fdsMinLengthChoiceStep uint32  Maximum step when generating initial choices for length of an interval variable
  --fdsMinIntVarChoiceStep uint32  Minimum step when generating choices for integer variables.
  --fdsEventTimeInfluence double   Influence of event time to initial choice rating
  --fdsBothFailRewardFactor double
                                   How much to improve rating when both branches fail immediately
  --fdsEpsilon double              How often to chose a choice randomly
  --fdsStrongBranchingSize uint32  Number of choices to try in strong branching
  --fdsStrongBranchingDepth uint32
                                   Up-to what search depth apply strong branching
  --fdsStrongBranchingCriterion Both|Left|Right
                                   How to choose the best choice in strong branching
  --fdsInitialRestartLimit uint64  Fail limit for the first restart
  --fdsRestartStrategy Geometric|Nested|Luby
                                   Restart strategy to use
  --fdsRestartGrowthFactor double  Growth factor for fail limit after each restart
  --fdsMaxCounterAfterRestart uint8
                                   Truncate choice use counts after a restart to this value
  --fdsMaxCounterAfterSolution uint8
                                   Truncate choice use counts after a solution is found
  --fdsResetRestartsAfterSolution bool
                                   Reset restart size after a solution is found (ignored in Luby)
  --fdsUseNogoods bool             Whether to use or not nogood constraints
  --fdsBranchOnObjective bool      Whether to generate choices for objective expression/variable
  --fdsBranchOrdering FailureFirst|FailureLast|Random
                                   Controls which side of a choice is is explored first (considering the rating).
  --fdsDualStrategy Minimum|Random|Split
                                   A strategy to choose objective cuts during FDSDual search.
  --fdsDualResetRatings bool       Whether to reset ratings when a new LB is proved

Large Neighborhood Search:
  --lnsUseWarmStartOnly bool       Use only the user-provided warm start as the initial solution in LNS

Simple Lower Bound:
  --simpleLBWorker int32           Which worker computes simple lower bound
  --simpleLBMaxIterations uint32   Maximum number of feasibility checks
  --simpleLBShavingRounds uint32   Number of shaving rounds
"""



class _ParameterParser:
    """Parses command-line arguments into Parameters."""

    def __init__(self, params: Parameters) -> None:
        self._params = params
        self._unrecognized: list[str] = []
        self._allow_unknown = False

    def allow_unknown(self) -> None:
        """Enable collecting unrecognized options instead of raising errors."""
        self._allow_unknown = True

    def get_unrecognized(self) -> list[str]:
        """Return list of unrecognized arguments."""
        return self._unrecognized

    def _add_unrecognized(self, opt: str) -> None:
        if self._allow_unknown:
            self._unrecognized.append(opt)
        else:
            raise ValueError(f"Unrecognized command line option: {opt}")

    def _get_or_create_worker(self, worker_id: int) -> WorkerParameters:
        if 'workers' not in self._params:
            self._params['workers'] = []
        workers = self._params['workers']
        while len(workers) <= worker_id:
            workers.append({})  # type: ignore[arg-type]
        worker = workers[worker_id]
        if worker is None:
            workers[worker_id] = {}  # type: ignore[assignment]
            return workers[worker_id]  # type: ignore[return-value]
        return worker  # type: ignore[return-value]

    def _apply_parameter(self, name: str, value: str) -> bool:
        """Apply a single parameter. Returns False if unknown."""
        # Remove '--' prefix and convert to lowercase
        opt = name[2:].lower()
        worker_range: tuple[int, int] | None = None

        # Check for worker syntax: --worker3.searchType or --worker0-3.searchType
        match = re.match(r'^workers?(\d+)(?:-(\d+))?\.(.+)$', opt)
        if match:
            min_worker = int(match.group(1))
            max_worker = int(match.group(2)) if match.group(2) else min_worker
            if min_worker > max_worker:
                raise ValueError(f"Empty range worker specification: {name}")
            worker_range = (min_worker, max_worker)
            opt = match.group(3)

        config = _PARSER_CONFIG.get(opt)
        if config is None:
            if worker_range is not None:
                raise ValueError(f"Unknown worker parameter '{opt}' in '{name}'.")
            return False

        parsed_value = config.parse(value, config.name)

        if worker_range is None:
            config.set_globally(self._params, parsed_value)
        else:
            if config.set_on_worker is None:
                raise ValueError(
                    f"Parameter '{opt}' is global and cannot be set per-worker. "
                    f"Use '--{opt}' instead."
                )
            for i in range(worker_range[0], worker_range[1] + 1):
                config.set_on_worker(self._get_or_create_worker(i), parsed_value)

        return True

    def parse(self, args: list[str]) -> None:
        """Parse arguments, raising ValueError on errors."""
        i = 0
        while i < len(args):
            opt = args[i]
            if not opt.startswith('--'):
                self._add_unrecognized(opt)
                i += 1
                continue

            # Check for --param=value syntax
            eq_pos = opt.find('=')
            if eq_pos != -1:
                if not self._apply_parameter(opt[:eq_pos], opt[eq_pos + 1:]):
                    self._add_unrecognized(args[i])
                i += 1
                continue

            # Check for --param value syntax
            if i == len(args) - 1:
                if not self._allow_unknown:
                    raise ValueError(f"Missing value for command line option: {opt}")
                self._add_unrecognized(args[i])
                i += 1
                continue

            if self._apply_parameter(opt, args[i + 1]):
                i += 2
            else:
                self._add_unrecognized(args[i])
                i += 1


def _handle_help_flags(
    args: list[str],
    usage: str | None,
    exit_on_error: bool,
) -> None:
    """Handle --help/-h and --optalcpVersion flags."""
    show_help = '--help' in args or '-h' in args
    show_version = any(arg.lower() == '--optalcpversion' for arg in args)

    if not show_help and not show_version:
        return

    if show_help:
        if usage is not None:
            print(usage + '\n')
        else:
            print(f"Usage: python {sys.argv[0]} [options]\n")
        print(_PARAMETERS_HELP)

    if show_version:
        # Late import to avoid circular dependency
        from . import __version__
        from ._solver import Solver
        solver_path = Solver.find_solver({})
        subprocess.run([solver_path, '--version'], check=False)
        print(f"OptalCP Python API {__version__}")
        print(f"Solver path: '{solver_path}'")

    if exit_on_error:
        sys.exit(0)
    else:
        raise ValueError("Help requested" if show_help else "Version requested")


def parse_parameters(
    *,
    args: list[str] | None = None,
    defaults: Parameters | None = None,
    usage: str | None = None,
    exit_on_error: bool = True,
) -> Parameters:
    r"""
    Parses OptalCP solver parameters from the command line.

    :param args: Command-line arguments to parse. Defaults to sys.argv[1:]
    :type args: list[str] | None
    :param defaults: Default parameter values. CLI arguments override these
    :type defaults: Parameters | None
    :param usage: Custom usage text shown before the parameter list when --help is used
    :type usage: str | None
    :param exit_on_error: If True (default), exits on error or --help. If False, raises ValueError instead
    :type exit_on_error: bool
    :rtype: Parameters
    :returns: The parsed parameters dict

    ## Details

    This function parses OptalCP solver parameters from the command line and returns
    a :class:`Parameters` dict ready for use with :func:`Model.solve`.

    Instead of hardcoding solver settings like time limits or worker counts in your code,
    you can let users configure them when running your application. For example, running
    `python solve.py --timeLimit 120 --nbWorkers 8` would override any defaults. This makes
    your application flexible without requiring code changes for different scenarios.

    The `defaults` argument lets you specify sensible default values for your application.
    When users don't provide a parameter on the command line, the default value is used.

    By default (`exit_on_error=True`), parse errors and `--help`/`--optalcpVersion` flags
    cause the process to exit. Set `exit_on_error=False` to raise `ValueError` instead.

    If `--help` or `-h` is given, the function prints help starting with the `usage`
    argument (if provided), followed by the list of recognized parameters:

    :class:`WorkerParameters` can be specified for individual worker(s) using the following prefixes:

    - `--workerN.` or `--workersN.` for worker `N`
    - `--workerN-M.` or `--workersN-M.` for workers in the range `N` to `M`

    For example:

    - `--worker0.searchType FDS` sets the search type for the first worker only.
    - `--workers4-8.noOverlapPropagationLevel 4` sets the propagation level of `no_overlap` constraint for workers 4, 5, 6, 7, and 8.

    This function does not accept unrecognized arguments (they cause an error).

    .. code-block:: python

        import optalcp as cp

        # Parse with defaults that CLI can override
        params = cp.parse_parameters(
            defaults={"timeLimit": 60, "nbWorkers": 4},
            usage="Usage: python solve.py [OPTIONS] <input-file>\n\nSolve scheduling problem."
        )

        # Use parsed parameters
        result = model.solve(params)

    .. seealso::

        - :func:`parse_known_parameters` to handle unrecognized arguments.
    """
    if args is None:
        args = sys.argv[1:]

    params: Parameters = copy_parameters(defaults) if defaults else cast(Parameters, {})

    _handle_help_flags(args, usage, exit_on_error)

    parser = _ParameterParser(params)

    if exit_on_error:
        try:
            parser.parse(args)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.parse(args)

    return params


def parse_known_parameters(
    *,
    args: list[str] | None = None,
    defaults: Parameters | None = None,
    usage: str | None = None,
    exit_on_error: bool = True,
) -> tuple[Parameters, list[str]]:
    r"""
    Parses OptalCP solver parameters from the command line, passing through unrecognized arguments.

    :param args: Command-line arguments to parse. Defaults to sys.argv[1:]
    :type args: list[str] | None
    :param defaults: Default parameter values. CLI arguments override these
    :type defaults: Parameters | None
    :param usage: Custom usage text shown before the parameter list when --help is used
    :type usage: str | None
    :param exit_on_error: If True (default), exits on error or --help. If False, raises ValueError instead
    :type exit_on_error: bool
    :rtype: tuple[Parameters, list[str]]
    :returns: A tuple of the parsed parameters and a list of unrecognized arguments

    ## Details

    This function parses OptalCP solver parameters from the command line and returns
    both a :class:`Parameters` dict and a list of unrecognized arguments.

    Instead of hardcoding solver settings like time limits or worker counts in your code,
    you can let users configure them when running your application. This variant is
    particularly useful when your application accepts its own arguments (like input file
    names) alongside solver parameters. For example, running
    `python solve.py --timeLimit 120 input.txt` would parse `--timeLimit 120` as a solver
    parameter and return `input.txt` as an unrecognized argument for your code to handle.

    The `defaults` argument lets you specify sensible default values for your application.
    When users don't provide a parameter on the command line, the default value is used.

    By default (`exit_on_error=True`), parse errors and `--help`/`--optalcpVersion` flags
    cause the process to exit. Set `exit_on_error=False` to raise `ValueError` instead,
    which is useful for testing or custom error handling.

    If `--help` or `-h` is given, the function prints help starting with the `usage`
    argument (if provided), followed by the list of recognized parameters:

    :class:`WorkerParameters` can be specified for individual workers using `--workerN.` prefix.
    For example, `--worker0.searchType FDS` sets the search type for the first worker only.

    .. code-block:: python

        import optalcp as cp

        # Parse solver parameters, collect input files as unrecognized args
        params, input_files = cp.parse_known_parameters(
            defaults={"timeLimit": 60},
            usage="Usage: python solve.py [OPTIONS] <input-file>..."
        )

        for file in input_files:
            model = load_model(file)
            model.solve(params)

    .. seealso::

        - :func:`parse_parameters` for a stricter version that rejects unrecognized arguments.
    """
    if args is None:
        args = sys.argv[1:]

    params: Parameters = copy_parameters(defaults) if defaults else cast(Parameters, {})

    _handle_help_flags(args, usage, exit_on_error)

    parser = _ParameterParser(params)
    parser.allow_unknown()

    if exit_on_error:
        try:
            parser.parse(args)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.parse(args)

    return params, parser.get_unrecognized()
