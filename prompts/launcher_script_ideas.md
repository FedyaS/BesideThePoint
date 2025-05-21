# Launcher Script Brainstorming

## Goal
Create an easy way for users to run various computation and utility scripts with configurable parameters, minimizing modifications to the original scripts and ensuring no performance degradation. This will be achieved via two distinct launcher scripts.

## Scripts to Include
- `ComputeNumpy.py`
- `ComputeMultiprocess.py`
- `ComputeMultithread.py`
- `ComputeSimple.py`
- `ComputeCupy.py`
- `VisualBesideThePoint.py`
- `ParsePerformance.py`

## Approach 1: CLI-driven Master Script (`run.py`)

### Functionality
-   Uses `argparse` to handle command-line arguments.
-   Defines subcommands for each target script (e.g., `computenumpy`, `computemultiproc`, `visualize`).
-   For compute scripts, accepts `--trials` (default: 1,000,000,000) and `--workers` (default: 12, where applicable).
    -   Example: `python run.py computenumpy --workers 8 --trials 100000000`
    -   Example: `python run.py computesimple --trials 50000000`
-   For utility scripts (`VisualBesideThePoint.py`, `ParsePerformance.py`), parameters TBD (may not need any from launcher).
-   `run.py` will construct and execute the appropriate command for the target script using `subprocess`.

### `Compute*.py` Script Modifications
-   Each `Compute*.py` script's `if __name__ == "__main__":` block will be modified:
    -   Import `argparse`.
    -   Define arguments:
        -   `--total_trials` (type `int`): Default to current hardcoded value in the script.
        -   `--num_workers` (type `int`): Default to current hardcoded value. (Only for `ComputeNumpy.py`, `ComputeMultiprocess.py`, `ComputeMultithread.py`).
    -   Parse arguments.
    -   Pass parsed arguments to their respective `compute()` function.
    -   Example for `ComputeNumpy.py`: `compute(args.total_trials, num_workers=args.num_workers, ...)`
    -   Example for `ComputeSimple.py`: `compute(args.total_trials, ...)`
-   The `compute()` function signatures in `ComputeNumpy.py`, `ComputeMultiprocess.py`, and `ComputeMultithread.py` already accept `num_workers`.
-   `ComputeSimple.py` and `ComputeCupy.py` `compute()` functions do not take `num_workers`, and `run.py` will not pass it to them.
-   **No other modifications to `Compute*.py` files.**

## Approach 2: Interactive Master Script (`interactive_run.py`)

### Functionality
-   Presents a numbered list of available scripts for the user to choose from.
-   Once a script is selected:
    -   **If `ComputeNumpy.py`, `ComputeMultiprocess.py`, or `ComputeMultithread.py`:**
        -   Prompts for "Number of trials" (proposing default: 1,000,000,000).
        -   Prompts for "Number of workers" (proposing default: 12, and suggesting `os.cpu_count()` as a value).
    -   **If `ComputeSimple.py` or `ComputeCupy.py`:**
        -   Prompts for "Number of trials" (proposing default: 1,000,000,000). (No worker prompt).
    -   **If `VisualBesideThePoint.py` or `ParsePerformance.py`:**
        -   Parameter needs TBD by their own CLI or interactive prompts if any. `interactive_run.py` might just launch them.
-   Uses the collected inputs to construct and execute the command for the target script using `subprocess`, similar to `run.py`.

### `Compute*.py` Script Modifications
-   Same as for `run.py`. The `Compute*.py` scripts will be agnostic to whether they are called by `run.py`, `interactive_run.py`, or directly, as they will handle their own argument parsing.

## General Constraints
-   The primary goal is to provide convenient launchers without altering the core logic or performance of the existing scripts.
-   Modifications to `Compute*.py` files are strictly limited to their `if __name__ == "__main__":` block for argument parsing.
-   No other files in the project should be touched. 