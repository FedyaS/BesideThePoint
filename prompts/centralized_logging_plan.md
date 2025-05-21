# Centralized Logger Plan

## Goal
Extract logging functionality from various compute scripts into a single, reusable module.

## Key Features for the New Logger:
- Log to console.
- Log to a dedicated performance file (`Performance-{Compute-Type}.txt`).
- Track:
    - Solutions
    - Trials run
    - Probability (to 10 decimal places)
    - Time (Timestamp or Elapsed Time - TBD)
- Operate in a separate thread to minimize performance impact.
- Configurable log interval (for console/file performance logs) and save interval (for `progress.json`).
- Handle loading and saving of progress (e.g., `progress-{compute_type}.json`).

## Proposed Module: `performance_logger.py`

### Class: `CentralizedLogger`

**Core Responsibilities:**
- Initialize with compute-specific details (`compute_type`, `total_trials`, intervals).
- Manage `progress_state` (solutions, trials run) internally, ensuring thread safety.
- Load initial progress from a JSON file.
- Start/stop a dedicated logging thread.
- Provide a method for compute scripts to report batch completion (`update_progress(batch_solutions, batch_trials)`).
- The logging thread will:
    - Periodically log metrics to console and the performance file.
    - Periodically save current progress to the JSON file.

## Open Questions / Design Decisions:
1.  **Progress Saving**: Yes, the logger will handle loading and saving progress.
2.  **Time Logging**: Log the current timestamp with each performance log entry.
3.  **Progress Filenames**: The logger will accept a `progress_filename` parameter during initialization.
4.  **Shared State for Multiprocessing**: Option B. The main process will be responsible for reading from shared `multiprocessing.Value` objects (if used by the compute script) and then calling an update method on the logger (e.g., `logger.update_progress(batch_solutions, batch_trials)`). The logger itself will not directly interact with `multiprocessing.Value` for simplicity and to keep its interface clean.

## Next Steps:
- Draft the `CentralizedLogger` class structure.
- Refactor one script at a time to use the new logger. 