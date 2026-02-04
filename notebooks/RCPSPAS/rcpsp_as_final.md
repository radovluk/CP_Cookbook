# A Simplified Formulation for RCPSP-AS

## 1. Notation

### Graph

- $G = (N, A)$ — directed acyclic project graph
- $N = \{1, \ldots, n\}$ — topologically ordered activities
- $A \subset N \times N$ — precedence arcs
- $d_i \geq 0$ — duration of activity $i$

Activity $1$ is the unique source; activity $n$ is the unique sink.

### Resources

- $R$ — set of renewable resources
- $a_v$ — capacity of resource $v \in R$
- $r_{i,v}$ — demand of activity $i$ for resource $v$

### Alternatives

- $L$ — set of alternative subgraphs
- $p_l \in N$ — principal activity of subgraph $l \in L$

The immediate successors of $p_l$ in $A$ represent mutually exclusive branches.

### Derived Set

$$A_{\text{prop}} = A \setminus \{(p_l, j) \in A : l \in L\}$$

### Decision Variables

- $x_i \in \{0, 1\}$ — whether activity $i$ is selected
- $s_i \in \mathbb{N}_0$ — start time of activity $i$

---

## 2. Formulation

**Objective:**

$$\min\; s_n + d_n \tag{1}$$

**Subject to:**

$$x_1 = 1 \tag{2}$$

$$x_i \Rightarrow x_j \quad \forall (i, j) \in A_{\text{prop}} \tag{3}$$

$$\sum_{j:\, (p_l, j) \in A} x_j = x_{p_l} \quad \forall l \in L \tag{4}$$

$$(x_i \land x_j) \Rightarrow (s_i + d_i \leq s_j) \quad \forall (i, j) \in A \tag{5}$$

$$\sum_{i \in S_t} r_{i,v} \leq a_v \quad \forall t \in \mathbb{N}_0,\, \forall v \in R \tag{6}$$

where $S_t = \{i \in N : x_i \land s_i \leq t < s_i + d_i\}$

---

## 3. Semantics

| Constraint | Purpose |
|------------|---------|
| (2) | Project execution begins at the source |
| (3) | Selection propagates along non-branching arcs |
| (4) | Exactly one branch per active subgraph |
| (5) | Precedence timing for selected activities |
| (6) | Resource capacity respected at all times |

---

## 4. Transformation from the Original Formulation

This formulation is a simplification of the RCPSP-AS model presented by Servranckx & Vanhoucke. The original formulation defines numerous auxiliary concepts: branching activities $b_k$, terminal activities $t_l$, branch membership sets $N_{b_k}$, fixed vs. alternative activities $N^f$ and $N^a$, and link parameters $\kappa_{i,j}$.

We show that all original constraints are captured by our simplified formulation.

### 4.1 Original Constraints

| Original | Description |
|----------|-------------|
| (3.3) | $(x_i \land x_j) \Rightarrow (s_i + d_i \leq s_j)$ for $(i,j) \in A$ |
| (3.4) | $\sum_{k \in K_{p_l}} x_{b_k} = x_{p_l}$ for each subgraph $l$ |
| (3.5) | $x_i = 1$ for all fixed activities $i \in N^f$ |
| (3.6) | $x_{p_l} \Rightarrow x_{t_l}$ — principal implies terminal |
| (3.7) | $x_i \Rightarrow x_j$ for $(i,j) \in (N_{b_k} \times N_{b_k}) \cap A$ |
| (3.8) | $(\kappa_{i,j} \land x_i) \Rightarrow x_j$ — cross-branch links |
| (3.9) | Resource capacity constraints |

### 4.2 Transformation Mapping

| Original | New | Justification |
|----------|-----|---------------|
| (3.3) | (5) | Identical |
| (3.4) | (4) | Equivalent; $K_{p_l} = \{j : (p_l, j) \in A\}$ by definition |
| (3.5) | (2) + (3) | See §4.3 |
| (3.6) | (3) | See §4.4 |
| (3.7) | (3) | Within-branch arcs are in $A_{\text{prop}}$ |
| (3.8) | (3) | Links are encoded directly as arcs in $A$ |
| (3.9) | (6) | Identical |

### 4.3 Fixed Activities

**Original approach:** Explicitly enumerate fixed activities $N^f = N \setminus N^a$ and force $x_i = 1$.

**New approach:** Start with $x_1 = 1$ and propagate selection through $A_{\text{prop}}$.

**Why it works:** A fixed activity is one that does not belong to any branch. Therefore, every path from the source to a fixed activity consists entirely of non-branching arcs (which are in $A_{\text{prop}}$) and exactly one selected branching arc per encountered subgraph (guaranteed by constraint 4).

By induction on topological order:
- Base: $x_1 = 1$ by constraint (2)
- Step: For fixed activity $i$ with predecessor $j$:
  - If $(j, i) \in A_{\text{prop}}$: propagation (3) ensures $x_j \Rightarrow x_i$
  - If $(j, i) \notin A_{\text{prop}}$: then $j = p_l$ for some $l$, but this contradicts $i$ being fixed (it would be a branching activity)

Therefore all fixed activities are selected.

### 4.4 Terminal Activities

**Original approach:** Explicit constraint $x_{p_l} \Rightarrow x_{t_l}$.

**New approach:** Covered by propagation (3).

**Why it works:** By definition, terminal activity $t_l$ is not part of any branch within subgraph $l$. Therefore, all arcs leading into $t_l$ from within the subgraph are in $A_{\text{prop}}$.

When $x_{p_l} = 1$:
1. Constraint (4) selects exactly one branching activity $b_k$
2. Propagation (3) selects all activities along the path from $b_k$ to $t_l$
3. Since this path lies entirely in $A_{\text{prop}}$, $t_l$ is selected

### 4.5 Cross-Branch Links

**Original approach:** Explicit parameter $\kappa_{i,j}$ and constraint (3.8).

**New approach:** Links are simply arcs in $A$. Since links connect activities within branches (not from principal activities), they belong to $A_{\text{prop}}$ and are handled by propagation (3).

**Why it works:** A link $(i, j)$ where $i \in N_{b_k}$ and $j \in N_{b_{k'}}$ with $k \neq k'$ is an arc between branch activities. Neither $i$ nor $j$ is a principal activity, so $(i, j) \in A_{\text{prop}}$.

### 4.6 Nested Subgraphs

**Original approach:** Implicit through branch membership sets.

**New approach:** Handled automatically.

**Why it works:** If subgraph $l'$ is nested within a branch of subgraph $l$, then $p_{l'}$ is a non-branching activity within that branch. 

- If the containing branch is not selected: $x_{p_{l'}} = 0$, so constraint (4) for $l'$ yields $\sum_j x_j = 0$ — no branch of $l'$ is selected
- If the containing branch is selected: $x_{p_{l'}} = 1$ via propagation, so constraint (4) selects exactly one branch of $l'$

---

## 5. Correctness Summary

The simplified formulation is equivalent to the original under the following structural assumption:

> **Assumption:** Cross-branch links do not target branching activities directly. That is, if $(i, j) \in A$ is a link with $i$ in one branch and $j$ in another, then $j$ is not an immediate successor of any principal activity.

This assumption is satisfied by well-formed RCPSP-AS instances as defined in the literature, where links connect "internal" branch activities rather than entry points.

Under this assumption:
- **Soundness:** Every solution feasible in the new formulation is feasible in the original
- **Completeness:** Every solution feasible in the original formulation is feasible in the new formulation

The formulations are therefore equivalent.

---

## 6. Benefits of Simplification

| Aspect | Original | Simplified |
|--------|----------|------------|
| Auxiliary sets | $N^f$, $N^a$, $N_{b_k}$, $K_{p_l}$ | — |
| Auxiliary parameters | $b_k$, $t_l$, $\kappa_{i,j}$ | — |
| Selection constraints | 4 (eqs. 3.5–3.8) | 2 (eqs. 2–3) |
| Total constraints | 7 | 5 |

The alternative structure is fully characterized by $L$ and $p_l$ alone. All other concepts emerge from graph topology and the single propagation rule.
