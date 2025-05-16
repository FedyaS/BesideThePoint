import cupy as cp
import json
import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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

def save_progress(count_solutions, count_run, filename='progress-gpu.json'):
    """Save progress to JSON file."""
    data = {'count_solutions': int(count_solutions), 'count_run': int(count_run)}
    with open(filename, 'w') as f:
        json.dump(data, f)
    logging.info(f"Saved: {data} to {filename}")

def load_progress(filename='progress-gpu.json'):
    """Load progress from JSON file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['count_solutions'], data['count_run']
    return 0, 0

def logger_thread(progress_state, total_trials, log_interval=10, save_interval=20, filename='progress-gpu.json'):
    """Periodically log and save progress."""
    last_save_time = time.time()
    logging.info("Logger thread started.")

    while progress_state['trials_run'] < total_trials:
        # Calculate how long to sleep. If log_interval is already passed since last theoretical log time, log immediately.
        # This aims for more regular logging intervals.
        # However, a simple sleep is often sufficient and less complex.
        # For now, sticking to simple sleep.
        time.sleep(log_interval)

        current_solutions = progress_state['solutions']
        current_trials = progress_state['trials_run']

        # Check if total_trials reached during sleep or by another quick update
        if not (current_trials < total_trials):
            break

        probability = current_solutions / current_trials if current_trials > 0 else 0
        logging.info(
            f"Progress - Trials: {current_trials:,} | Solutions: {current_solutions:,} | "
            f"Probability: {probability:.12f}"
        )

        if (time.time() - last_save_time) >= save_interval:
            save_progress(current_solutions, current_trials, filename)
            last_save_time = time.time()

    # Final save when loop terminates (either total_trials reached or compute is ending)
    final_solutions = progress_state['solutions']
    final_trials = progress_state['trials_run']
    save_progress(final_solutions, final_trials, filename)
    logging.info(
        f"Logger thread: Final save. Trials: {final_trials:,} | Solutions: {final_solutions:,}"
    )

def compute(total_trials, batch_size=10_000_000, log_interval=10, save_interval=20):
    """Compute trials on GPU using CuPy."""
    initial_solutions, initial_run = load_progress()
    
    progress_state = {'solutions': initial_solutions, 'trials_run': initial_run}

    trials_remaining = total_trials - progress_state['trials_run']

    probability = progress_state['solutions'] / progress_state['trials_run'] if progress_state['trials_run'] > 0 else 0
    logging.info(
        f"Loaded - Trials: {progress_state['trials_run']:,} | Solutions: {progress_state['solutions']:,} | "
        f"Probability: {probability:.12f}"
    )

    if trials_remaining <= 0:
        logging.info("All trials completed previously.")
        # If all trials were completed, the probability is based on total_trials expected.
        # Or, if progress_state['trials_run'] > 0, use that as denominator.
        # Original used total_trials. Let's stick to that if it's the target.
        if total_trials > 0:
            return progress_state['solutions'] / total_trials
        elif progress_state['trials_run'] > 0: # If total_trials is 0, but we ran some
            return progress_state['solutions'] / progress_state['trials_run']
        else: # total_trials is 0 and no runs
            return 0

    # Start logger thread
    logger = threading.Thread(
        target=logger_thread,
        args=(progress_state, total_trials, log_interval, save_interval, 'progress-gpu.json'), # Pass filename explicitly
        daemon=True
    )
    logger.start()

    seed = 0
    while progress_state['trials_run'] < total_trials:
        current_batch = min(batch_size, total_trials - progress_state['trials_run'])
        batch_solutions, batch_trials = vectorized_trial(current_batch, seed)
        
        # Ensure batch_solutions is a Python int before adding
        batch_solutions_int = int(batch_solutions.get())
        
        progress_state['solutions'] += batch_solutions_int
        progress_state['trials_run'] += batch_trials
        seed += 1

    logger.join(timeout=log_interval + save_interval + 5) # Give ample time for final log/save
    return progress_state['solutions'] / progress_state['trials_run'] if progress_state['trials_run'] > 0 else 0

if __name__ == "__main__":
    total_trials = 15_000_000_000_000
    result = compute(total_trials)
    logging.info(f"Final probability: {result:.12f}")