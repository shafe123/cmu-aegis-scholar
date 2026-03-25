#!/usr/bin/env python3
"""
Unified test runner for Aegis Scholar monorepo.

This script runs tests for all or specific components.
"""
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Component paths relative to repository root
COMPONENTS = {
    "frontend": Path("frontend"),
    "aegis-api": Path("services/aegis-scholar-api"),
    "graph-db": Path("services/graph-db"),
    "vector-db": Path("services/vector-db"),
    "vector-loader": Path("jobs/vector-loader"),
    "graph-loader": Path("jobs/graph-loader"),
    "example-lib": Path("libs/example_lib"),
    "integration": Path("tests"),
}

PYTHON_COMPONENTS = [
    "aegis-api",
    "graph-db",
    "vector-db",
    "vector-loader",
    "graph-loader",
    "example-lib",
    "integration",
]

FRONTEND_COMPONENTS = ["frontend"]


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str):
    """Print colored header message."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.ENDC}")


def print_error(message: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.ENDC}")


def print_info(message: str):
    """Print info message."""
    print(f"{Colors.CYAN}ℹ {message}{Colors.ENDC}")


def run_command(cmd: List[str], cwd: Path, shell: bool = False) -> Tuple[int, str]:
    """
    Run a command and return exit code and output.
    
    Args:
        cmd: Command and arguments as list
        cwd: Working directory
        shell: Whether to use shell
        
    Returns:
        Tuple of (exit_code, output)
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            shell=shell
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def run_python_tests(component: str, coverage: bool = True) -> bool:
    """
    Run pytest for a Python component.
    
    Args:
        component: Component name
        coverage: Whether to generate coverage report
        
    Returns:
        True if tests passed, False otherwise
    """
    component_path = COMPONENTS[component]
    print_info(f"Running tests for {component} at {component_path}")
    
    # Check if poetry.lock exists, if not warn about dependencies
    if not (component_path / "poetry.lock").exists():
        print_error(f"{component}: poetry.lock not found. Run 'poetry install' first.")
        return False
    
    cmd = ["poetry", "run", "pytest", "-v"]
    if coverage:
        # Add coverage arguments
        cov_target = "example_lib" if component == "example-lib" else "app"
        cmd.extend([
            f"--cov={cov_target}",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=80"
        ])
    
    exit_code, output = run_command(cmd, component_path)
    
    if exit_code == 0:
        print_success(f"{component} tests passed")
        return True
    else:
        print_error(f"{component} tests failed")
        # Check for common error patterns
        if "pytest-cov" in output or "unrecognized arguments: --cov" in output:
            print_error(f"  → pytest-cov not installed. Run 'cd {component_path} && poetry install'")
        elif "not allowed by the project" in output:
            print_error(f"  → Python version mismatch. Check pyproject.toml requirements.")
        else:
            print(output)
        return False


def run_frontend_tests(coverage: bool = True) -> bool:
    """
    Run frontend tests using npm.
    
    Args:
        coverage: Whether to generate coverage report
        
    Returns:
        True if tests passed, False otherwise
    """
    component_path = COMPONENTS["frontend"]
    print_info(f"Running frontend tests at {component_path}")
    
    # Check if node_modules exists
    if not (component_path / "node_modules").exists():
        print_error("frontend: node_modules not found. Run 'cd frontend && npm install' first.")
        return False
    
    # Use shell=True for Windows compatibility with npm
    cmd = ["npm", "run", "test:coverage" if coverage else "test"]
    
    exit_code, output = run_command(cmd, component_path, shell=True)
    
    if exit_code == 0:
        print_success("Frontend tests passed")
        return True
    else:
        print_error("Frontend tests failed")
        if "vitest" in output and "not recognized" in output:
            print_error("  → vitest not installed. Run 'cd frontend && npm install'")
        else:
            print(output)
        return False


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(
        description="Run tests for Aegis Scholar components",
        epilog="Note: Run 'npm install' in frontend/ and 'poetry install' in each Python component before testing."
    )
    parser.add_argument(
        "components",
        nargs="*",
        choices=list(COMPONENTS.keys()) + ["all", "python", "services", "jobs", "libs"],
        help="Components to test (default: all)"
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage reporting"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure"
    )
    
    args = parser.parse_args()
    
    # Determine which components to test
    components_to_test = []
    if not args.components or "all" in args.components:
        components_to_test = list(COMPONENTS.keys())
    else:
        if "python" in args.components:
            components_to_test.extend(PYTHON_COMPONENTS)
        if "services" in args.components:
            components_to_test.extend(["aegis-api", "graph-db", "vector-db"])
        if "jobs" in args.components:
            components_to_test.extend(["vector-loader", "graph-loader"])
        if "libs" in args.components:
            components_to_test.append("example-lib")
        
        # Add explicitly named components
        for comp in args.components:
            if comp in COMPONENTS and comp not in components_to_test:
                components_to_test.append(comp)
    
    # Remove duplicates while preserving order
    components_to_test = list(dict.fromkeys(components_to_test))
    
    print_header(f"Running tests for: {', '.join(components_to_test)}")
    
    coverage = not args.no_coverage
    results = {}
    
    # Run tests for each component
    for component in components_to_test:
        if component in FRONTEND_COMPONENTS:
            success = run_frontend_tests(coverage)
        else:
            success = run_python_tests(component, coverage)
        
        results[component] = success
        
        if not success and args.fail_fast:
            print_error("Stopping due to test failure (--fail-fast)")
            break
    
    # Print summary
    print_header("Test Results Summary")
    passed = sum(1 for success in results.values() if success)
    failed = sum(1 for success in results.values() if not success)
    
    for component, success in results.items():
        if success:
            print_success(f"{component:20} PASSED")
        else:
            print_error(f"{component:20} FAILED")
    
    print(f"\n{Colors.BOLD}Total: {passed} passed, {failed} failed{Colors.ENDC}\n")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
