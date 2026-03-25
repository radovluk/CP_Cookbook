"""
Shared utilities for solver communication.

This module contains internal utility functions used by both sync and async
solver implementations. These are not part of the public API.
"""

from __future__ import annotations

import os
import sys
from typing import IO


def _enable_windows_ansi() -> bool:
    """
    Enable ANSI escape sequences on Windows.

    Returns:
        True if ANSI mode was enabled or already supported, False otherwise
    """
    if sys.platform != 'win32':
        return True  # Not Windows, assume ANSI is supported

    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Get handle to stdout
        handle = kernel32.GetStdHandle(-11)
        # Enable VIRTUAL_TERMINAL_PROCESSING (0x0004) | DISABLE_NEWLINE_AUTO_RETURN (0x0008)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            mode.value |= 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            return bool(kernel32.SetConsoleMode(handle, mode))
    except Exception:
        pass

    return False


def _can_use_colors(output_stream: IO[str] | None) -> bool:
    """
    Detect if ANSI color codes can be used in output.

    Checks multiple conditions to determine color support:
    - NO_COLOR environment variable (disables colors if set)
    - FORCE_COLOR environment variable (forces colors if set)
    - Jupyter/IPython environments (VS Code notebooks, JupyterLab, etc.)
    - TTY detection for terminal output
    - Windows ANSI support

    Args:
        output_stream: The output stream to check (e.g., sys.stdout)

    Returns:
        True if ANSI colors can be used, False otherwise

    References:
        - NO_COLOR standard: https://no-color.org/
        - FORCE_COLOR: Common convention for CI/CD and logging
    """
    # Respect NO_COLOR standard: https://no-color.org/
    if os.environ.get('NO_COLOR'):
        return False

    # Force colors if requested (useful for CI/CD, logging)
    if os.environ.get('FORCE_COLOR'):
        return True

    # No stream = no colors
    if output_stream is None:
        return False

    # Detect Jupyter/IPython environments (VS Code notebooks, JupyterLab, Jupyter Classic, etc.)
    # These environments support ANSI colors even though they're not TTYs
    # IPython injects get_ipython() into the global namespace when running in a kernel
    get_ipython_func = globals().get('get_ipython')
    if get_ipython_func is not None and get_ipython_func() is not None:
        # We're running in a Jupyter kernel - colors work!
        return True

    # Check if output stream is a TTY (traditional terminal check)
    if hasattr(output_stream, 'isatty') and output_stream.isatty():
        # On Windows, try to enable ANSI support
        if sys.platform == 'win32':
            return _enable_windows_ansi()
        return True

    # No color support detected
    return False
