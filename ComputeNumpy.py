import numpy as np
# import json # No longer directly used
# import os # No longer directly used
import logging
# import threading # No longer directly used for logger thread
# import time # No longer directly used for logger timing
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures
from multiprocessing import Value # Still needed for worker communication

from performance_logger import CentralizedLogger # Import the new logger

# Configure logging for this script (e.g., final result, errors outside logger)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def vectorized_trial(num_trials):
    """Run num_trials trials using NumPy vectorization."""
    # Generate all points at once
    blue = np.random.random((num_trials, 2))  # [x, y]
    red = np.random.random((num_trials, 2))

    # Distances to sides
    dbottom = blue[:, 1]
    dtop = 1 - blue[:, 1]
    dright = 1 - blue[:, 0]
    dleft = blue[:, 0]
    distances = np.stack([dbottom, dtop, dright, dleft], axis=1)
    closest_side_idx = np.argmin(distances, axis=1)

    # Midpoint and slope
    mid = (blue + red) / 2
    slope = (blue[:, 1] - red[:, 1]) / (blue[:, 0] - red[:, 0] + 1e-10)
    neg_recip_slope = -1 / slope

    # Initialize intersection results
    solutions = np.zeros(num_trials, dtype=bool)

    # Process each side
    for side, idx in enumerate([0, 1, 2, 3]):
        mask = (closest_side_idx == idx)
        if not np.any(mask):
            continue

        if idx == 0:  # Bottom: y = 0
            y = 0
            x = (y - mid[mask, 1]) / neg_recip_slope[mask] + mid[mask, 0]
            solutions[mask] = (x >= 0) & (x <= 1)
        elif idx == 1:  # Top: y = 1
            y = 1
            x = (y - mid[mask, 1]) / neg_recip_slope[mask] + mid[mask, 0]
            solutions[mask] = (x >= 0) & (x <= 1)
        elif idx == 2:  # Right: x = 1
            x = 1
            y = neg_recip_slope[mask] * (x - mid[mask, 0]) + mid[mask, 1]
            solutions[mask] = (y >= 0) & (y <= 1)
        else:  # Left: x = 0
            x = 0
            y = neg_recip_slope[mask] * (x - mid[mask, 0]) + mid[mask, 1]
            solutions[mask] = (y >= 0) & (y <= 1)

    return np.sum(solutions), num_trials

# Removed old save_progress, load_progress, and logger_thread functions

def compute(total_trials, num_workers=12, batch_size=1000000, log_interval=10, save_interval=20):
    """Compute trials using NumPy vectorization and multiprocessing with CentralizedLogger."""
    
    logger = CentralizedLogger(
        compute_type="NumpyCPU",
        total_trials=total_trials,
        log_interval_sec=log_interval,
        save_interval_sec=save_interval
    )

    initial_solutions, initial_run = logger.get_current_progress()

    if initial_run >= total_trials:
        logging.info(f"[{logger.compute_type}] All {total_trials:,} trials already completed based on loaded progress.")
        logger.stop()
        return logger.get_final_probability()

    # Shared counters, initialized with loaded progress
    # Using 'Q' for unsigned long long, as in the original script for large counts.
    # Ensure these Value types are appropriate if CentralizedLogger uses different internal types for its state.
    # CentralizedLogger uses Python integers, which handle arbitrary size, so this should be fine.
    solutions_counter = Value('Q', initial_solutions)
    trials_run_counter = Value('Q', initial_run)

    logger.start()

    try:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            active_futures = set()
            
            # Tracks the cumulative number of trials submitted or loaded as already run.
            # This should start from initial_run as those are already accounted for.
            submitted_trials_total = initial_run 

            # Initial submissions
            for _ in range(num_workers):
                if submitted_trials_total < total_trials:
                    current_batch_to_submit = min(batch_size, total_trials - submitted_trials_total)
                    if current_batch_to_submit <= 0: 
                        break 
                    future = executor.submit(vectorized_trial, current_batch_to_submit)
                    active_futures.add(future)
                    submitted_trials_total += current_batch_to_submit
                else:
                    break 

            while active_futures:
                done_iterator = concurrent.futures.as_completed(active_futures)
                completed_future = next(done_iterator)

                try:
                    batch_solutions, batch_trials_from_future = completed_future.result()
                    # Convert to Python int if they are numpy types, for Value and logger
                    batch_solutions = int(batch_solutions)
                    batch_trials_from_future = int(batch_trials_from_future)
                except Exception as e:
                    logging.error(f"[{logger.compute_type}] A trial batch encountered an error: {e}. Skipping this batch's results.")
                    active_futures.remove(completed_future)
                    continue

                active_futures.remove(completed_future)

                # Update multiprocessing.Value counters first
                with solutions_counter.get_lock():
                    solutions_counter.value += batch_solutions
                with trials_run_counter.get_lock():
                    trials_run_counter.value += batch_trials_from_future
                
                # Then update the centralized logger with the results of this batch
                logger.update_progress(batch_solutions, batch_trials_from_future)
                
                # If there are still more trials to be submitted overall, dispatch a new task.
                if submitted_trials_total < total_trials:
                    current_batch_to_submit = min(batch_size, total_trials - submitted_trials_total)
                    if current_batch_to_submit > 0:
                        new_future = executor.submit(vectorized_trial, current_batch_to_submit)
                        active_futures.add(new_future)
                        submitted_trials_total += current_batch_to_submit
    finally:
        logger.stop()
    
    return logger.get_final_probability()

if __name__ == "__main__":
    total_trials = 15_000_000_000_000 # Example total trials
    # total_trials = 200_000_000 # Smaller value for testing
    # num_w = 4
    # batch_s = 1_000_000
    # log_i = 2
    # save_i = 5
    # result = compute(total_trials, num_workers=num_w, batch_size=batch_s, log_interval=log_i, save_interval=save_i)
    result = compute(total_trials)
    logging.info(f"Final probability (NumpyCPU): {result:.12f}")