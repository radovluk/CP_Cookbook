"""
Load Instance Module for RCPSP-AS.

This module provides functions for loading RCPSP-AS problem instances from
benchmark files in the ASlib format (Servranckx & Vanhoucke, 2019).

The benchmark format uses two files per instance:
- *a.RCP: Main file with activity count, resources, durations, and precedences
- *b.RCP: Alternative structure with subgraph definitions and branch memberships

For weighted tardiness instances, an additional *wt.RCP file specifies due dates.

Key functions:
- load_instance(): Main entry point, auto-detects instance type
- reconstruct_instance(): Identifies principal (branching) activities from topology
"""

import os
from collections import deque
from typing import Callable, Optional

from ascp.__shared import other_instance_file_path, file_a_to_name

from .instance import (
    Activity,
    AlternativeStructureParams,
    AslibInstance,
    AslibInstanceFiles,
    Instance,
    RawInstance,
    RawSubgraph,
    Subgraph,
    WtDueDate,
    WtInstance,
    WtInstanceFiles,
    WtParams,
)


# =============================================================================
# File Parsing Utilities
# =============================================================================

def __read_file(file_path: str):
    """
    Create a line reader for a benchmark file.
    
    Returns a function that yields non-empty stripped lines one at a time.
    This allows for sequential parsing of the file format.
    """
    def lines():
        with open(file_path, 'r') as f:
            for line in map(str.strip, f):
                if line: yield line.strip()

    ls = lines()
    def next_line(): return next(ls)
    return next_line


def __nums[T](line: str, to_num: Callable[[str], T] = int) -> list[T]:
    """Parse a line of whitespace-separated numbers into a list."""
    return list(map(to_num, line.split()))


def __parse_subgraph(id: int, line: str) -> RawSubgraph:
    """
    Parse a subgraph definition from a benchmark file line.
    
    Format: <branch_count> <branch_id_1> <branch_id_2> ...
    Note: Branch IDs are 1-indexed in files, converted to 0-indexed here.
    """
    [count, *branches] = __nums(line)
    assert count == len(branches), f"Expected {count} branches, got {len(branches)}"
    return RawSubgraph(id, set(b - 1 for b in branches))


def __parse_activity(id: int, resource_count: int, line_a: str, line_b: str) -> Activity:
    """
    Parse an activity from corresponding lines in file_a and file_b.
    
    file_a format: <duration> <r1> <r2> ... <rk> <succ_count> <succ1> <succ2> ...
    file_b format: <branch_count> <branch1> <branch2> ...
    
    Note: All IDs are 1-indexed in files, converted to 0-indexed here.
    """
    ints_a = __nums(line_a)
    ints_b = __nums(line_b)

    # Parse file_a: duration, resource requirements, successors
    [duration, *ints_a] = ints_a
    resources = ints_a[:resource_count]

    [successors_count, *successors] = ints_a[resource_count:]
    assert_err = lambda: f"Expected {successors_count} successors, got {len(successors)}"
    assert successors_count == len(successors), assert_err()

    # Parse file_b: branch memberships
    [branches_count, *branches] = ints_b
    assert_err = lambda: f"Expected {branches_count} branches, got {len(branches)}"
    assert branches_count == len(branches), assert_err()

    return Activity(
        id=id,
        duration=duration,
        successors=set(s - 1 for s in successors),  # Convert to 0-indexed
        branches=set(b - 1 for b in branches),       # Convert to 0-indexed
        requirements=resources
    )


def __verify_branch_ids(subgraphs: list[RawSubgraph]):
    """
    Verify that branch IDs form a consecutive sequence starting from 1.
    
    This is an integrity check to ensure the benchmark file is well-formed.
    """
    total_branch_count = sum(len(sg.branches) for sg in subgraphs)
    all_branches_set = __union(*[sg.branches for sg in subgraphs])

    err_message = lambda: f"Subgraph branch IDs must be consecutive integers starting from 1, got {all_branches_set}"
    assert set(range(1, total_branch_count + 1)) == all_branches_set, err_message()


def __verify_topsort_and_sink_activity(activities: list[Activity], check_sink: bool = True):
    """
    Verify that activities are topologically ordered and have a valid sink.
    
    For Cmax instances, all activities must be reachable from a single sink
    (the last activity). For wT instances, check_sink=False skips this check
    since multiple sink activities are allowed.
    """
    # Build reverse adjacency list while checking topological order
    reverse_neighbours = [[] for _ in activities]
    for activity in activities:
        for successor in activity.successors:
            # In topological order, all successors must have higher IDs
            assert successor > activity.id, \
                f"Activities must be in topological order, got {activity.id} -> {successor}"
            reverse_neighbours[successor].append(activity.id)

    if not check_sink:
        return

    hopeful_sink = activities[-1].id
    queue = deque([hopeful_sink])
    seen = set([hopeful_sink])

    while queue:
        activity = queue.popleft()
        for neighbour in reverse_neighbours[activity]:
            if neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)

    all_activities = set(a.id for a in activities)
    err_message = lambda: f"Activities {all_activities.difference(seen)} not reachable from sink {hopeful_sink + 1}"
    assert seen == all_activities, err_message()

    err_message = lambda: f"Sink activity {hopeful_sink + 1} must only belong to branch 0"
    assert activities[hopeful_sink].branches == { 0 }, err_message()


# =============================================================================
# Instance Loading Functions
# =============================================================================

__ReadLine = Callable[[], str]


def __load_instance(read_line_a: __ReadLine, read_line_b: __ReadLine, name: str, check_sink: bool = True) -> RawInstance:
    """
    Parse a raw RCPSP-AS instance from benchmark file readers.
    
    This is the core parsing function that reads both files in lockstep,
    creating activities and subgraphs. Returns a RawInstance which still
    needs principal activity reconstruction.
    
    Args:
        read_line_a: Reader for the main benchmark file (*a.RCP)
        read_line_b: Reader for the alternative structure file (*b.RCP)
        name: Instance identifier
        check_sink: Whether to verify single sink activity (False for wT instances)
    """
    # Parse header: activity count and resource types from file_a
    [activity_count, resource_count] = __nums(read_line_a())
    resources = __nums(read_line_a())  # Resource capacities
    assert_err = lambda: f"Expected {resource_count} resources, got {len(resources)}"
    assert resource_count == len(resources), assert_err()

    # Parse subgraph definitions from file_b header
    [num_subgraphs] = __nums(read_line_b())
    subgraphs = [ __parse_subgraph(i, read_line_b()) for i in range(num_subgraphs) ]
    __verify_branch_ids(subgraphs)

    # Parse activities from both files in parallel
    activities = [
        __parse_activity(i, resource_count, read_line_a(), read_line_b())
        for i in range(activity_count)
    ]
    __verify_topsort_and_sink_activity(activities, check_sink)

    return RawInstance(
        activities=activities,
        resources=resources,
        subgraphs=subgraphs,
        name=name,
    )


def __load_aslib_instance(
    read_line_a: __ReadLine, read_line_b: __ReadLine,
    name: str, file_a: str, file_b: str
) -> AslibInstance:
    """Load an ASlib instance for Cmax minimization."""
    # First line of file_b contains alternative structure parameters
    [flex, nest, link] = __nums(read_line_b(), float)
    params = AlternativeStructureParams(flex, nest, link)

    instance = __load_instance(read_line_a, read_line_b, name)
    instance = reconstruct_instance(instance)  # Identify principal activities

    return AslibInstance.from_instance(instance, params, AslibInstanceFiles(file_a, file_b))


def __load_wt_instance(
    read_line_a: __ReadLine, read_line_b: __ReadLine, read_line_wt: __ReadLine,
    name: str, file_a: str, file_b: str, file_wt: str
) -> WtInstance:
    """Load a weighted tardiness instance."""
    # Parse wT-specific parameters and due dates from file_wt
    params = WtParams.fromstr(read_line_wt())
    [num_wt] = __nums(read_line_wt())  # Number of monitored activities

    # Parse due dates: <activity_id> <weight> <due_date>
    due_dates = dict[int, WtDueDate]()
    for i in range(num_wt):
        [activity_id, weight, due_date] = __nums(read_line_wt())
        due_dates[activity_id - 1] = WtDueDate(due_date, weight)  # Convert to 0-indexed

    # wT instances may have multiple sinks, so check_sink=False
    instance = __load_instance(read_line_a, read_line_b, name, check_sink=False)
    instance = reconstruct_instance(instance)

    return WtInstance.from_instance(
        instance,
        due_dates,
        params,
        WtInstanceFiles(file_a, file_b, file_wt)
    )


def load_instance(file_a: str) -> WtInstance | AslibInstance:
    """
    Load an RCPSP-AS instance from benchmark files.
    
    Main entry point for loading instances. Auto-detects whether the instance
    is for Cmax or weighted tardiness based on the presence of a *wt.RCP file.
    
    Args:
        file_a: Path to the main benchmark file (*a.RCP)
        
    Returns:
        AslibInstance for Cmax minimization, or WtInstance for weighted tardiness.
    """
    # Derive paths to companion files from file_a
    file_b = other_instance_file_path(file_a, "b")
    file_wt = other_instance_file_path(file_a, "wt")

    read_line_a = __read_file(file_a)
    read_line_b = __read_file(file_b)

    name = file_a_to_name(file_a)
    # If wT file exists, load as weighted tardiness; otherwise as Cmax
    if not os.path.exists(file_wt):
        return __load_aslib_instance(read_line_a, read_line_b, name, file_a, file_b)
    else:
        read_line_wt = __read_file(file_wt)
        return __load_wt_instance(read_line_a, read_line_b, read_line_wt, name, file_a, file_b, file_wt)


# =============================================================================
# Principal Activity Reconstruction
# =============================================================================
# The benchmark format doesn't explicitly store which activity is the "principal"
# (branching) activity for each subgraph. We must infer it from the graph topology.
# The principal activity is the one whose immediate successors all belong to
# different branches of the same subgraph.

def __all_disjoint[T](*sets: set[T]) -> bool:
    """Check if all given sets are pairwise disjoint (no common elements)."""
    seen: set[T] = set()

    for s in sets:
        if s.intersection(seen):
            return False

        seen.update(s)

    return True


def __union[T](*sets: set[T]) -> set[T]:
    """Compute the union of all given sets."""
    return set().union(*sets)


def __index_where[T](lst: list[T], predicate: Callable[[T], bool]) -> Optional[int]:
    """Find the index of the first element matching the predicate."""
    for i, item in enumerate(lst):
        if predicate(item):
            return i

    return None


def __check_branching_activity_precedes_whole_subgraph(
    instance: RawInstance,
    branching_activity: int,
    subgraph: RawSubgraph
):
    """
    Verify that the branching activity is a valid principal for the subgraph.
    
    The branching activity must:
    1. Not be part of the subgraph itself
    2. Have paths leading to ALL activities in the subgraph
    """
    # Find all activities that belong to this subgraph's branches
    required_activities = {
        a.id for a in instance.activities
        if a.branches.intersection(subgraph.branches)
    }

    err_message = lambda: f"Branching activity {branching_activity} must not be in subgraph {subgraph.id}"
    assert branching_activity not in required_activities, err_message()

    # BFS from branching activity to verify it reaches all subgraph activities

    seen = set([branching_activity])
    q = deque([branching_activity])

    while q and required_activities:
        activity = q.popleft()
        for successor in instance.activities[activity].successors:
            if successor in seen: continue

            required_activities.discard(successor)
            seen.add(successor)
            q.append(successor)

    err_message = lambda: f"Branching activity {branching_activity} does not cause all activities in subgraph {subgraph.id}"
    assert not required_activities, err_message()


def reconstruct_instance(instance: RawInstance):
    """
    Reconstruct principal (branching) activities for each subgraph.
    
    The benchmark format doesn't explicitly specify which activity is the
    "principal" or "branching" activity for each subgraph. We identify it
    by looking for activities whose immediate successors:
      1. Each belong to exactly one branch
      2. All belong to different branches (disjoint)
      3. Together form exactly the branches of some subgraph
    
    This is the key transformation that enables the CP model to work.
    
    Algorithm:
    1. For each activity, examine its successors' branch memberships
    2. If successors form a perfect partition matching a subgraph's branches,
       this activity is that subgraph's branching activity
    3. Verify each identified branching activity can reach all subgraph activities
    
    Args:
        instance: A RawInstance without principal activities
        
    Returns:
        An Instance with principal activities identified for each subgraph
    """
    # Initialize: we need to find one branching activity per subgraph
    branching_activities: list[int | None] = [None for _ in instance.subgraphs]

    for activity in instance.activities:
        # Get the branch sets of all immediate successors
        successor_branchsets = [instance.activities[s].branches for s in activity.successors]
        
        # Each successor must belong to exactly one branch
        if not all(len(s) == 1 for s in successor_branchsets): continue
        
        # Successor branches must be disjoint (no overlap)
        if not __all_disjoint(*successor_branchsets): continue

        # Check if the union of successor branches matches any subgraph
        successor_branchset = __union(*successor_branchsets)
        subgraph = __index_where(instance.subgraphs, lambda s: s.branches == successor_branchset)
        if subgraph is None: continue

        # Found a match! Verify it's the only one
        err_message = lambda old_ba: (
            f"Subgraph {subgraph} has multiple possible branching activities: "
            f"{old_ba + 1}, {activity.id + 1}"
        )
        assert branching_activities[subgraph] is None, err_message(branching_activities[subgraph])
        branching_activities[subgraph] = activity.id

    # Verify we found a branching activity for every subgraph
    def unwrap_activity(subgraph: int, a: int | None) -> int:
        assert a is not None, f"Subgraph {subgraph} has no branching activity"
        return a

    unwrapped_branching_activities = [unwrap_activity(i, a) for i, a in enumerate(branching_activities)]
    
    # Verify each branching activity actually precedes its entire subgraph
    for ba, sg in zip(unwrapped_branching_activities, instance.subgraphs):
        __check_branching_activity_precedes_whole_subgraph(instance, ba, sg)

    # Build the final Instance with Subgraph objects containing principal activities
    return Instance(
        resources=instance.resources,
        activities=instance.activities,
        name=instance.name,
        subgraphs=[
            Subgraph(
                id=s.id,
                branches=s.branches,
                principal_activity=unwrapped_branching_activities[s.id]
            )
            for s in instance.subgraphs
        ]
    )

