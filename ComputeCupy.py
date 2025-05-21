import cupy as cp
# import json # No longer directly used here
# import os # No longer directly used here
import logging
# import threading # No longer directly used here
# import time # No longer directly used here

from performance_logger import CentralizedLogger # Import the new logger

# Configure logging for this script (e.g., final result, errors outside logger)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def vectorized_trial(num_trials, seed=None):
    """Run num_trials trials on GPU using CuPy."""
    if seed is not None:
        cp.random.seed(seed)
    
    # Generate random points on GPU
    blue = cp.random.random((num_trials, 2))  # [x, y]
    red = cp.random.random((num_trials, 2))

    # Distances to sides
    dbottom = blue[:, 1]
    dtop = 1 - blue[:, 1]
    dright = 1 - blue[:, 0]
    dleft = blue[:, 0]
    distances = cp.stack([dbottom, dtop, dright, dleft], axis=1)
    closest_side_idx = cp.argmin(distances, axis=1)

    # Midpoint and slope
    mid = (blue + red) / 2
    slope = (blue[:, 1] - red[:, 1]) / (blue[:, 0] - red[:, 0] + 1e-10)
    neg_recip_slope = -1 / slope

    # Initialize solutions
    solutions = cp.zeros(num_trials, dtype=cp.bool_)

    # Process each side
    for idx in range(4):
        mask = (closest_side_idx == idx)
        if not cp.any(mask):
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

    return cp.sum(solutions), num_trials

# Removed old save_progress, load_progress, and logger_thread functions

def compute(total_trials, batch_size=10_000_000, log_interval=10, save_interval=20):
    """Compute trials on GPU using CuPy with CentralizedLogger."""
    
    # Note: Progress filename will be progress-CupyGPU.json
    # Performance log filename will be Performance-CupyGPU.txt
    logger = CentralizedLogger(
        compute_type="CupyGPU",
        total_trials=total_trials,
        log_interval_sec=log_interval,
        save_interval_sec=save_interval
    )

    initial_solutions, initial_run = logger.get_current_progress()

    if initial_run >= total_trials:
        logging.info(f"[{logger.compute_type}] All {total_trials:,} trials already completed based on loaded progress.")
        logger.stop() # Ensure any finalization of the logger happens
        return logger.get_final_probability()

    logger.start()
    seed = 0 # Seed can be managed locally or be part of progress if needed for exact resume of RNG state.
             # For now, restarting seed from 0 if computation resumes.

    try:
        while True:
            _, current_trials_run = logger.get_current_progress()
            if current_trials_run >= total_trials:
                break

            current_batch = min(batch_size, total_trials - current_trials_run)
            if current_batch <= 0: # Should not happen if loop condition is correct
                break
                
            batch_solutions, batch_trials_returned = vectorized_trial(current_batch, seed)
            
            batch_solutions_int = int(batch_solutions.get()) # Ensure it's a Python int
            
            logger.update_progress(batch_solutions_int, batch_trials_returned)
            seed += 1
    finally:
        logger.stop() # Ensure logger stops and finalizes logs/saves
    
    return logger.get_final_probability()

if __name__ == "__main__":
    total_trials = 15_000_000_000_000
    # For testing, smaller numbers might be useful:
    # total_trials = 100_000_000
    # batch_s = 10_000_000
    # log_i = 5
    # save_i = 10
    # result = compute(total_trials, batch_size=batch_s, log_interval=log_i, save_interval=save_i)
    
    result = compute(total_trials)
    logging.info(f"Final probability (CupyGPU): {result:.12f}")