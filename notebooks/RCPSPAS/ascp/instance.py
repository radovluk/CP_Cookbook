"""
Instance Module for RCPSP-AS (Resource-Constrained Project Scheduling Problem
with Alternative Subgraphs).

This module defines the core data structures used to represent RCPSP-AS problem
instances. The structure closely follows the benchmark dataset format from
Servranckx & Vanhoucke (2019).

Key concepts:
- Activities: Tasks with durations, resource requirements, and precedence relations
- Subgraphs: Alternative execution paths where exactly one branch must be selected
- Branches: Within a subgraph, each branch represents one possible execution path
- Resources: Renewable resources with limited capacities (e.g., workers, machines)
"""

from dataclasses import dataclass
from typing import Self


@dataclass
class AlternativeStructureParams:
    """
    Parameters describing the alternative structure complexity of an instance.
    These are metadata from the ASlib benchmark format.

    Attributes:
        flex: Flexibility parameter - controls how much choice exists in the project
        nested: Nesting level - how deeply subgraphs can be nested within each other
        linked: Linking parameter - controls dependencies between subgraphs
    """
    flex: float
    nested: float
    linked: float


@dataclass
class Activity:
    """
    Represents a single activity (task) in the RCPSP-AS problem.

    In the mathematical model, an activity i has:
    - Duration d_i: time required to complete the activity
    - Successors: set of activities {j ∈ N | (i,j) ∈ A} that must start after i finishes
    - Branches B_i: set of alternative branches this activity belongs to
    - Resource requirements r_{i,v}: demand for each resource type v

    Attributes:
        id: Unique identifier (0-indexed internally, 1-indexed in benchmark files)
        duration: Time units required to complete this activity (d_i)
        successors: Set of activity IDs that must follow this activity (precedence edges)
        branches: Set of branch IDs this activity belongs to (determines when scheduled)
        requirements: List of resource demands, one per resource type (r_{i,v})
    """
    id: int
    duration: int
    successors: set[int]
    branches: set[int]
    requirements: list[int]


@dataclass
class RawSubgraph:
    """
    A subgraph before principal activity reconstruction.

    Used during parsing when the principal (branching) activity
    hasn't been identified yet from the graph topology.

    Attributes:
        id: Unique identifier for this subgraph
        branches: Set of branch IDs that belong to this subgraph
    """
    id: int
    branches: set[int]


@dataclass
class Subgraph(RawSubgraph):
    """
    Represents an alternative subgraph (decision point) in the project.

    A subgraph models a choice: exactly one of its branches must be selected.
    The principal_activity is the "branching activity" whose successors
    determine which branch path to take.

    For subgraph l with principal activity p_l:
    - The constraint Σ_{k ∈ K_{p_l}} x_{b_k} = x_{p_l} ensures exactly one
      branch is selected if and only if the principal activity is scheduled.

    Attributes:
        id: Unique identifier for this subgraph
        branches: Set of branch IDs that belong to this subgraph (K_l)
        principal_activity: The branching activity ID that triggers this choice (p_l)
    """
    principal_activity: int


@dataclass(kw_only=True)
class __Instance[S: RawSubgraph]:
    """
    Generic base class for RCPSP-AS problem instances.

    Type parameter S: Either RawSubgraph (before reconstruction) or Subgraph (after).

    Attributes:
        resources: List of resource capacities a_v for each resource type v
        activities: List of all activities in the project
        subgraphs: List of alternative subgraphs (decision points)
        name: Instance identifier (usually derived from source filename)
    """
    resources: list[int]
    activities: list[Activity]
    subgraphs: list[S]
    name: str

# Type aliases for convenience
RawInstance = __Instance[RawSubgraph]  # Before principal activity reconstruction
Instance = __Instance[Subgraph]        # After reconstruction, ready for solving


@dataclass
class AslibInstanceFiles:
    """Paths to the source benchmark files for an ASlib instance."""
    file_a: str  # Main file with activities, resources, and precedence
    file_b: str  # Alternative structure file with subgraphs and branches


@dataclass(kw_only=True)
class AslibInstance(Instance):
    """
    An RCPSP-AS instance from the ASlib benchmark set (Servranckx & Vanhoucke, 2019).

    Used for Cmax (makespan minimization) objective.

    Attributes:
        params: Alternative structure parameters (flex, nested, linked)
        files: Optional paths to the source benchmark files
    """
    params: AlternativeStructureParams
    files: AslibInstanceFiles | None = None

    @classmethod
    def from_instance(
        cls,
        instance: Instance,
        params: AlternativeStructureParams,
        files: AslibInstanceFiles | None = None,
    ) -> Self:
        """Create an AslibInstance from a base Instance with added parameters."""
        return cls(
            resources=instance.resources,
            activities=instance.activities,
            subgraphs=instance.subgraphs,
            name=instance.name,
            params=params,
            files=files
        )


@dataclass
class WtInstanceFiles:
    """
    Paths to the source benchmark files for a weighted tardiness instance.
    
    Weighted tardiness instances require an additional file beyond the
    standard ASlib format to specify due dates and weights.
    """
    file_a: str   # Main file with activities, resources, and precedence
    file_b: str   # Alternative structure file with subgraphs and branches
    file_wt: str  # Weighted tardiness file with due dates and weights


@dataclass(kw_only=True)
class WtParams:
    """
    Parameters for weighted tardiness instance generation.
    
    These parameters control how weighted tardiness instances are created
    from base RCPSP-AS instances by adding jobs with due dates.
    
    Attributes:
        activities_in_job: Number of activities per job
        jobs_in_instance: Number of jobs in the instance
        instance_start_lag: Controls spacing between job start times
        resource_overlap: Controls resource sharing between jobs
        weight_range: (min, max) range for activity weights
    """
    activities_in_job: int
    jobs_in_instance: int
    instance_start_lag: float
    resource_overlap: float
    weight_range: tuple[int, int]

    __Tuple = tuple[int, int, float, float, int, int]

    def astuple(self) -> __Tuple:
        return (
            self.activities_in_job,
            self.jobs_in_instance,
            self.instance_start_lag,
            self.resource_overlap,
            *self.weight_range,
        )

    def tuple_labels(self) -> tuple[str, str, str, str, str, str]:
        return (
            "activities_in_job",
            "jobs_in_instance",
            "instance_start_lag",
            "resource_overlap",
            "weight_range_min",
            "weight_range_max",
        )

    @classmethod
    def fromtuple(cls, t: __Tuple) -> Self:
        return cls(
            activities_in_job=t[0],
            jobs_in_instance=t[1],
            instance_start_lag=t[2],
            resource_overlap=t[3],
            weight_range=(t[4], t[5]),
        )

    @classmethod
    def fromstr(cls, s: str) -> Self:
        [a, b, c, d, e, f] = s.split()
        return cls.fromtuple((int(a), int(b), float(c), float(d), int(e), int(f)))


@dataclass(frozen=True)
class WtDueDate:
    """
    Due date specification for a monitored activity in weighted tardiness.
    
    The weighted tardiness for an activity is: w_i * max(0, C_i - d_i)
    where C_i is the completion time, d_i is the due date, and w_i is the weight.
    
    Attributes:
        due_date: Target completion time d_i for the activity
        weight: Importance weight w_i (higher = more important to be on time)
    """
    due_date: int
    weight: int


@dataclass(kw_only=True)
class WtInstance(Instance):
    """
    An RCPSP-AS instance for weighted tardiness (wT) minimization.
    
    Unlike Cmax instances, wT instances:
    - May not have a single sink activity
    - Include due dates and weights for monitored activities
    - Objective is to minimize: Σ w_i * max(0, C_i - d_i)
    
    Attributes:
        due_dates: Mapping from activity ID to its due date and weight
        params: Parameters used to generate this wT instance
        files: Optional paths to the source benchmark files
    """
    due_dates: dict[int, WtDueDate]
    params: WtParams
    files: WtInstanceFiles | None

    @classmethod
    def from_instance(
        cls,
        instance: Instance,
        due_dates: dict[int, WtDueDate],
        params: WtParams,
        files: WtInstanceFiles | None = None,
    ) -> Self:
        """Create a WtInstance from a base Instance with added due dates."""
        return cls(
            resources=instance.resources,
            activities=instance.activities,
            subgraphs=instance.subgraphs,
            name=instance.name,
            due_dates=due_dates,
            params=params,
            files=files
        )

