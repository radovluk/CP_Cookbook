"""
Solver Configuration

Shared settings for OptalCP and IBM CP Optimizer solvers.
Import this in solve_optal.py and solve_cpo.py.
"""

# =============================================================================
# DEFAULT PARAMETERS
# =============================================================================

DEFAULTS = {
    "timeLimit": 60,
    "workers": 8,
    "logLevel": 0,
}

# OptalCP parameters (name: default_value)
OPTAL_PARAMS = {
    "searchType": "FDSDual",
    "noOverlapPropagationLevel": 4,
    "cumulPropagationLevel": 3,
    "reservoirPropagationLevel": 2,
    "usePrecedenceEnergy": 1,
    "logPeriod": 5.0,
}

# CPO parameters (name: default_value)
CPO_PARAMS = {
    "SearchType": "Restart",
    "FailureDirectedSearch": "On",
    "NoOverlapInferenceLevel": "Extended",
    "CumulFunctionInferenceLevel": "Extended",
    "PrecedenceInferenceLevel": "Extended",
    "LogPeriod": 5000,
}

# CPO log level mapping (numeric -> string)
CPO_LOG_LEVELS = {0: 'Quiet', 1: 'Terse', 2: 'Normal', 3: 'Verbose'}


# =============================================================================
# ARGUMENT PARSING HELPERS
# =============================================================================

def add_common_args(parser):
    """Add common arguments to parser."""
    parser.add_argument('instances', nargs='+', help='Instance file(s)')
    parser.add_argument('--timeLimit', type=int, default=DEFAULTS["timeLimit"])
    parser.add_argument('--workers', type=int, default=DEFAULTS["workers"])
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--logLevel', default=DEFAULTS["logLevel"])
    return parser


def add_solver_args(parser, param_dict):
    """Add solver-specific arguments from param dict."""
    for name, default in param_dict.items():
        arg_type = type(default) if default is not None else str
        if isinstance(default, bool):
            parser.add_argument(f'--{name}', type=str, default=None,
                              help=f'(default: {default})')
        else:
            parser.add_argument(f'--{name}', type=arg_type, default=None,
                              help=f'(default: {default})')
    return parser


def get_solver_params(args, param_dict):
    """Extract solver params from args, using defaults for unset values."""
    params = {}
    for name, default in param_dict.items():
        val = getattr(args, name, None)
        if val is not None:
            # Handle bool conversion from string
            if isinstance(default, bool):
                val = val.lower() in ('true', '1', 'yes', 'on')
            params[name] = val
        else:
            params[name] = default
    return params
