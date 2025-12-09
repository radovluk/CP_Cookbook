# CP Solver Benchmarks

Benchmark suite comparing **OptalCP** vs **IBM CP Optimizer** on constraint programming problems.

## Structure

```
.
├── run.py              # Universal benchmark runner
├── config.py           # Shared solver configuration
├── compare/            # HTML report generator (Node.js)
├── rcpsp-tt/           # RCPSP with Transfer Times
│   ├── solve_optal.py
│   └── solve_cpo.py
├── rcpsp-as/           # RCPSP with Alternative Subgraphs
│   ├── solve_optal.py
│   └── solve_cpo.py
├── rcpsp-timeoffs/     # RCPSP with Time-Offs (6 variants)
│   ├── solve_optal.py
│   └── solve_cpo.py
└── data/               # Instance files (not tracked)
```

## Requirements

```bash
pip install optalcp docplex
```

## Quick Start

```bash
# Run all instances for a problem
python run.py rcpsp-tt

# Test with limited instances
python run.py rcpsp-tt --max 5

# Custom time limit and workers
python run.py rcpsp-as --timeLimit 120 --workers 4

# Run single solver
python run.py rcpsp-tt --solver optal
python run.py rcpsp-tt --solver cpo

# RCPSP-TimeOffs with specific variant
python run.py rcpsp-timeoffs --variant 1 --max 10
python run.py rcpsp-timeoffs --variant all --max 5
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--max N` | all | Limit to N instances |
| `--timeLimit T` | 60 | Seconds per instance |
| `--workers W` | 8 | Parallel workers |
| `--solver S` | both | `optal`, `cpo`, or `both` |
| `--data PATH` | auto | Custom data directory |
| `--output PATH` | auto | Custom results directory |
| `--logLevel L` | 0 | Verbosity (0=quiet, 3=verbose) |
| `--python PATH` | auto | Python interpreter |
| `--no-compare` | false | Skip comparison report |
| `--variant V` | 1 | Problem variant (for rcpsp-timeoffs) |

## RCPSP with Time-Offs

This problem addresses RCPSP variants where resources have individual availability calendars. 
Each resource unit has its own availability calendar (available/unavailable periods).

### 6 Problem Variants

| Variant | Name | Description |
|---------|------|-------------|
| 1 | `no_mig_no_delay` | **No Migration \| No Delays** - Tasks execute continuously, resources fixed |
| 2 | `mig_no_delay` | **Migration \| No Delays** - Tasks continuous, can switch resources |
| 3 | `no_mig_delay_block` | **No Migration \| Delays \| Blocked** - Tasks pause when unavailable, resources blocked |
| 4 | `mig_delay` | **Migration \| Delays** - Tasks can pause and switch resources |
| 5 | `heterogeneous` | **Multi-Resource Heterogeneous** - Mixed policy per resource type |
| 6 | `no_mig_delay_rel` | **No Migration \| Delays \| Released** - Tasks pause, resources released |

### Running Variants

```bash
# Run specific variant
python run.py rcpsp-timeoffs --variant 1 --max 10
python run.py rcpsp-timeoffs --variant mig_no_delay --max 10

# Run all 6 variants
python run.py rcpsp-timeoffs --variant all --max 5

# Solve single instance directly
cd rcpsp-timeoffs
python solve_optal.py instance.data --variant 3 --timeLimit 60
python solve_cpo.py instance.data --variant no_mig_delay_block --timeLimit 60
```

## Solving Single Instances

```bash
# Direct solver usage
cd rcpsp-tt
python solve_optal.py instance.sm --timeLimit 60 --output result.json
python solve_cpo.py instance.sm --timeLimit 60 --output result.json

# Override any solver parameter
python solve_optal.py instance.sm --searchType LNS --noOverlapPropagationLevel 3
python solve_cpo.py instance.sm --SearchType DepthFirst --NoOverlapInferenceLevel Medium
```

## Solver Parameters

Edit `config.py` to change defaults, or pass via command line:

**OptalCP** (`solve_optal.py`):
- `--searchType` (FDSLB, LNS, FDS, SetTimes)
- `--noOverlapPropagationLevel` (0-4)
- `--cumulPropagationLevel` (0-4)
- `--usePrecedenceEnergy` (0/1)

**CPO** (`solve_cpo.py`):
- `--SearchType` (Restart, DepthFirst, MultiPoint)
- `--NoOverlapInferenceLevel` (Low, Medium, Extended)
- `--CumulFunctionInferenceLevel` (Low, Medium, Extended)
- `--FailureDirectedSearch` (On, Off)

## Output

Results saved to `<problem>/results/`:
- `optalcp-results.json` / `optalcp-results_v1.json` - OptalCP results
- `cpo-results.json` / `cpo-results_v1.json` - CPO results  
- `comparison/main.html` - Interactive comparison report

## Adding New Problems

1. Create directory: `mkdir my-problem`
2. Copy solver templates: `cp rcpsp-timeoffs/solve_*.py my-problem/`
3. Customize `parse_instance()` and `build_model()` functions
4. Update `PROBLEM_CONFIG` in `run.py` with data paths and patterns
5. Run: `python run.py my-problem`

Solver scripts must accept:
```
python solve_X.py <instances...> --timeLimit T --workers W --output FILE --logLevel L [--variant V]
```

## Environment Variables

- `SOLVER_PYTHON` - Default Python interpreter path
