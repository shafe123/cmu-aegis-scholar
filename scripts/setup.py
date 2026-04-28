#!/usr/bin/env python3
"""
Setup script to install dependencies for all Aegis Scholar components.
Run this before running tests for the first time.
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple

# Component paths relative to repository root
PYTHON_COMPONENTS = [
    Path("services/aegis-scholar-api"),
    Path("services/graph-db"),
    Path("services/vector-db"),
    Path("jobs/vector-loader"),
    Path("jobs/graph-loader"),
    Path("libs/example_lib"),
    Path("tests"),
]

FRONTEND_PATH = Path("frontend")


class Colors:
    """ANSI color codes."""

    GREEN = "\033[92m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.ENDC}")


def print_info(msg: str):
    print(f"{Colors.CYAN}→ {msg}{Colors.ENDC}")


def run_command(cmd: list, cwd: Path) -> Tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=True if sys.platform == "win32" else False,
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def setup_frontend() -> bool:
    """Install frontend dependencies."""
    print_info(f"Installing frontend dependencies at {FRONTEND_PATH}")

    if not FRONTEND_PATH.exists():
        print_error(f"Frontend directory not found: {FRONTEND_PATH}")
        return False

    exit_code, output = run_command(["npm", "install"], FRONTEND_PATH)

    if exit_code == 0:
        print_success("Frontend dependencies installed")
        return True
    else:
        print_error("Frontend installation failed")
        print(output)
        return False


def setup_python_component(component_path: Path, python_path: str) -> bool:
    """Install Python component dependencies using poetry."""
    print_info(f"Installing dependencies for {component_path}")

    if not component_path.exists():
        print_error(f"Component directory not found: {component_path}")
        return False

    if not (component_path / "pyproject.toml").exists():
        print_error(f"No pyproject.toml found in {component_path}")
        return False

    # Set Poetry to use the specified Python version
    print_info(f"Setting Poetry environment to use {python_path}")
    exit_code, output = run_command(
        ["poetry", "env", "use", python_path], component_path
    )
    if exit_code != 0:
        print_error(f"Failed to set Python version for {component_path.name}")
        print(output)
        # Don't fail - continue anyway in case it's already set

    exit_code, output = run_command(["poetry", "lock"], component_path)
    if exit_code == 0:
        print_success(f"{component_path.name} dependencies locked")
    else:
        print_error(f"{component_path.name} lock failed")
        print(output)
        return False

    exit_code, output = run_command(["poetry", "install"], component_path)

    if exit_code == 0:
        print_success(f"{component_path.name} dependencies installed")
        return True
    else:
        print_error(f"{component_path.name} installation failed")
        print(output)
        return False


def main():
    """Main setup function."""
    print(f"\n{Colors.BOLD}Aegis Scholar - Dependency Setup{Colors.ENDC}\n")
    print("This will install dependencies for all components.\n")

    # Check for required tools
    print_info("Checking for required tools...")

    # Check for Node.js/npm
    npm_check, _ = run_command(["npm", "--version"], Path("."))
    if npm_check != 0:
        print_error("npm not found. Please install Node.js from https://nodejs.org/")
        return 1
    print_success("npm found")

    # Check for Poetry
    poetry_check, _ = run_command(["poetry", "--version"], Path("."))
    if poetry_check != 0:
        print_error(
            "poetry not found. Install with: curl -sSL https://install.python-poetry.org | python3 -"
        )
        return 1
    print_success("poetry found")

    # Get Python 3.12 executable path
    print_info("Detecting Python 3.12...")
    python_path = sys.executable  # Use the Python running this script
    print_success(f"Using Python: {python_path}")

    print()

    # Install frontend dependencies
    print(f"\n{Colors.BOLD}[1/8] Frontend{Colors.ENDC}")
    if not setup_frontend():
        print_error("Frontend setup failed")
        return 1

    # Install Python component dependencies
    for i, component in enumerate(PYTHON_COMPONENTS, start=2):
        print(f"\n{Colors.BOLD}[{i}/8] {component}{Colors.ENDC}")
        if not setup_python_component(component, python_path):
            print_error(f"Setup failed for {component}")
            return 1

    print(
        f"\n{Colors.GREEN}{Colors.BOLD}✓ All dependencies installed successfully!{Colors.ENDC}\n"
    )
    print("You can now run tests with:")
    print("  npm run test:all")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
