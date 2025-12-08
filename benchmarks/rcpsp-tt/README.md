# RCPSP-TT Benchmark Suite

Benchmark suite for comparing **OptalCP** vs **IBM CP Optimizer** on the Resource-Constrained Project Scheduling Problem with Transfer Times (RCPSP-TT).

## Problem Description

RCPSP-TT extends the classical RCPSP by modeling resource transfers between activities. When a resource unit finishes one activity and moves to another, a transfer time is incurred. The model includes flow variables for resource allocation and optional interval variables for transfer operations.

## Requirements

- Python 3.8+
- OptalCP (`pip install optalcp`)
- DOcplex (`pip install docplex`)

```bash
pip install optalcp docplex
```

## Files

| File | Description |
|------|-------------|
| `solve_optal.py` | OptalCP solver for RCPSP-TT |
| `solve_cpo.py` | IBM CP Optimizer solver for RCPSP-TT |
| `run.py` | Benchmark runner comparing both solvers |

## Usage

### Solve a Single Instance

```bash
# OptalCP
python solve_optal.py instance.sm --timeLimit 60 --workers 8

# IBM CP Optimizer
python solve_cpo.py instance.sm --timeLimit 60 --workers 8

# Save results to JSON
python solve_optal.py instance.sm --output results.json
```

### Solve Multiple Instances

```bash
python solve_optal.py j301_a.sm j302_a.sm j303_a.sm --output results.json
```

### Run Full Benchmark

1. **Configure** `run.py`:
   ```python
   SOLVER_PYTHON = "/path/to/python"       # Python with optalcp & docplex
   TIME_LIMIT = 20                          # Seconds per instance
   WORKERS = 8                              # Parallel workers
   ```

2. **Place instances** in `data/rcpsp_tt_instances/`:
   ```
   data/rcpsp_tt_instances/
   ├── j301_a.sm
   ├── j302_a.sm
   ├── j601_a.sm
   └── ...
   ```

3. **Run**:
   ```bash
   python run.py
   ```

4. **Results** saved to `results/` directory:
   - `optalcp-results-full.json`
   - `cpo-results-full.json`
   - `comparison-report/main.html` (if compare tool available)

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--timeLimit` | 60 | Time limit in seconds |
| `--workers` | 8 | Number of parallel workers |
| `--output` | stdout | Output JSON file |
| `--logLevel` | 0/Quiet | Verbosity (OptalCP: 0-3, CPO: Quiet/Terse/Normal/Verbose) |

## Instance Format

Uses `.sm` files in PSPLIB format extended with transfer time matrices:

```
****************
PRECEDENCE RELATIONS:
jobnr.  #modes #successors successors
    1      1        3        2  3  4
...
****************
REQUESTS/DURATIONS:
jobnr.  mode duration  R1  R2
    1     1     0       0   0
...
****************
RESOURCEAVAILABILITIES:
  R1  R2
   4   4
****************
TRANSFERTIMES R1
    1  2  3  4
 1  0  1  2  1
 2  1  0  1  2
...
```

## Output Format

JSON output per instance:
```json
{
  "modelName": "j301_a",
  "objective": 156,
  "lowerBound": 156,
  "proof": true,
  "duration": 2.345,
  "nbSolutions": 12,
  "nbBranches": 5000,
  "nbFails": 2500,
  "nbIntVars": 1200,
  "nbIntervalVars": 450,
  "objectiveHistory": [
    {"objective": 200, "solveTime": 0.1},
    {"objective": 156, "solveTime": 1.5}
  ]
}
```

## Model Details

The RCPSP-TT model includes:

- **Activity intervals** `a[i]`: Mandatory intervals for each activity
- **Flow variables** `f[i,j,r]`: Optional integer variables for resource flow from activity i to j for resource r
- **Transfer intervals** `z[i,j,r]`: Optional intervals for transfer operations with duration `Delta[i][j][r]`

Key constraints:
1. Precedence relations (transitive closure)
2. Source flow initialization (all resources start at source)
3. Flow conservation (resources flow in = flow out)
4. Temporal linking (transfer happens between activities)
5. Cumulative resource capacity

## Benchmark Instances

Standard instance sets from PSPLIB with transfer times:
- `j30x`: 30 activities (480 instances)
- `j60x`: 60 activities (480 instances)  
- `j90x`: 90 activities (480 instances)
