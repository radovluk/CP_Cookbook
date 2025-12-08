# Benchmarks

Benchmark suite for comparing **OptalCP** vs **IBM CP Optimizer** on constraint programming scheduling problems.

## Structure

```
benchmarks/
├── compare/          # Comparison report generator
├── rcpsp-tt/         # RCPSP with Transfer Times
└── rcpsp-as/         # RCPSP with Alternative Subgraphs
```

## Quick Start

### 1. Install dependencies

```bash
# Compare tool (Node.js)
cd compare && npm install

# Python solvers
pip install optalcp docplex
```

### 2. Run benchmarks

```bash
# RCPSP-TT: Test with 1 instance
cd rcpsp-tt
python run_benchmark_python.py --max 1

# RCPSP-AS: Test with 1 instance  
cd rcpsp-as
python run_benchmark_rcpspas.py --max 1

# Full benchmark (all instances)
python run_benchmark_python.py
```

### 3. View results

Open `results/comparison-report/main.html` in a browser.

## Problems

| Problem | Description | Instances |
|---------|-------------|-----------|
| **RCPSP-TT** | Resource-Constrained Project Scheduling with Transfer Times | j30, j60, j90 (.sm) |
| **RCPSP-AS** | Resource-Constrained Project Scheduling with Alternative Subgraphs | ASLIB (.rcp) |

## Configuration

Edit the `run_benchmark_*.py` files to configure:

```python
SOLVER_PYTHON = "/path/to/python"  # Python with optalcp & docplex
TIME_LIMIT = 60                     # Seconds per instance
WORKERS = 8                         # Parallel workers
```

## Output

Each benchmark produces:
- `results/optalcp-results-*.json` - OptalCP results
- `results/cpo-results-*.json` - IBM CP Optimizer results  
- `results/comparison-report/main.html` - Interactive comparison report
