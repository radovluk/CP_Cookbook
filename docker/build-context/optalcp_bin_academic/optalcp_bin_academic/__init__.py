"""OptalCP solver binaries - Academic edition."""
import sys
import platform
from pathlib import Path

def get_solver_path() -> Path:
    """
    Get path to the bundled optalcp binary for this platform.

    Returns:
        Path to the optalcp executable

    Raises:
        RuntimeError: If the current platform is not supported
        FileNotFoundError: If the binary file is not found in the package

    Remarks:
        This function determines the platform and returns the path to the
        appropriate binary bundled with this package. The binaries are stored
        in the bin/{platform}/ subdirectory of the package.
    """
    # Determine platform
    system = sys.platform
    machine = platform.machine()

    if system == "linux" and machine == "x86_64":
        platform_dir = "linux-x64"
        binary_name = "optalcp"
    elif system == "darwin" and machine == "x86_64":
        platform_dir = "darwin-x64"
        binary_name = "optalcp"
    elif system == "darwin" and machine == "arm64":
        platform_dir = "darwin-arm64"
        binary_name = "optalcp"
    elif system == "win32" and machine == "AMD64":
        platform_dir = "win32-x64"
        binary_name = "optalcp.exe"
    else:
        raise RuntimeError(
            f"No optalcp binary available for platform {system}/{machine}. "
            f"Supported platforms: linux/x86_64, darwin/x86_64, darwin/arm64, win32/AMD64"
        )

    # Use importlib.resources.files() (Python 3.9+)
    from importlib.resources import files
    binary_path = files("optalcp_bin_academic").joinpath("bin", platform_dir, binary_name)

    if not binary_path.is_file():
        raise FileNotFoundError(
            f"Binary not found: {binary_path}. "
            f"The optalcp-bin-academic package may be incomplete or corrupted."
        )

    return Path(str(binary_path))

__all__ = ["get_solver_path"]
