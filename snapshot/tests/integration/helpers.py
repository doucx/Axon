import subprocess
from pathlib import Path


def run_git_command(cwd: Path, args: list[str], check: bool = True) -> str:
    """Helper to run a git command and return stdout."""
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=check)
    return result.stdout.strip()
