import numpy as np
import json
import os
import logging
import threading
import time
from concurrent.futures import ProcessPoolExecutor
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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

def save_progress(count_solutions, count_run, filename='progress.json'):
    """Save current progress to a JSON file."""
    data = {'count_solutions': int(count_solutions), 'count_run': int(count_run)}
    with open(filename, 'w') as f:
        json.dump(data, f)

def load_progress(filename='progress.json'):
    """Load progress from a JSON file."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['count_solutions'], data['count_run']
    return 0, 0

def logger_thread(solutions, trials_run, total_trials, log_interval=10, save_interval=60, filename='progress.json'):
    """Periodically log and save progress."""
    start_time = time.time()
    while trials_run.value < total_trials:
        time.sleep(log_interval)
        current_solutions = solutions.value
        current_trials = trials_run.value
        probability = current_solutions / current_trials if current_trials > 0 else 0
        logging.info(
            f"Trials: {current_trials:,} | Solutions: {current_solutions:,} | "
            f"Probability: {probability:.7f}"
        )
        if (time.time() - start_time) >= save_interval:
            save_progress(current_solutions, current_trials, filename)
            start_time = time.time()
    save_progress(solutions.value, trials_run.value, filename)

def compute(total_trials, num_workers=24, batch_size=1000000, log_interval=10, save_interval=60):
    """Compute trials using NumPy vectorization and multiprocessing."""
    count_solutions, count_run = load_progress()
    trials_remaining = total_trials - count_run

    if trials_remaining <= 0:
        logging.info("All trials completed previously.")
        return count_solutions / total_trials if total_trials > 0 else 0

    # Shared counters
    from multiprocessing import Value
    solutions = Value('q', count_solutions)
    trials_run = Value('q', count_run)

    # Save progress on exit
    atexit.register(save_progress, solutions.value, trials_run.value, 'progress.json')

    # Start logger thread
    logger = threading.Thread(
        target=logger_thread,
        args=(solutions, trials_run, total_trials, log_interval, save_interval),
        daemon=True
    )
    logger.start()

    # Run trials in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        while trials_remaining > 0:
            current_batch = min(batch_size, trials_remaining)
            futures.append(executor.submit(vectorized_trial, current_batch))
            trials_remaining -= current_batch

        # Collect results
        for future in futures:
            batch_solutions, batch_trials = future.result()
            with solutions.get_lock():
                solutions.value += batch_solutions
            with trials_run.get_lock():
                trials_run.value += batch_trials

    logger.join(timeout=5)
    return solutions.value / trials_run.value if trials_run.value > 0 else 0

if __name__ == "__main__":
    total_trials = 15000000000
    result = compute(total_trials)
    logging.info(f"Final probability: {result:.7f}")