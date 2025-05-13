import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Value
from BesideThePoint import trial

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def run_trials(batch_size, solutions, trials_run, update_interval=10000):
    """Run trials continuously and update shared counters periodically."""
    local_solutions = 0
    local_trials = 0
    while True:
        res = trial()
        if res['solution'] == 'Solution':
            local_solutions += 1
        local_trials += 1
        if local_trials >= update_interval:
            with solutions.get_lock():
                solutions.value += local_solutions
            with trials_run.get_lock():
                trials_run.value += local_trials
            local_solutions = 0
            local_trials = 0


def logger_thread(solutions, trials_run, total_trials, log_interval=10, save_interval=60, filename='progress.json'):
    """Periodically log and save progress from shared counters."""
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
    # Final save when done
    save_progress(solutions.value, trials_run.value, filename)


def save_progress(count_solutions, count_run, filename='progress.json'):
    """Save current progress to a JSON file."""
    data = {'count_solutions': count_solutions, 'count_run': count_run}
    with open(filename, 'w') as f:
        json.dump(data, f)


def load_progress(filename='progress.json'):
    """Load progress from a JSON file, return (count_solutions, count_run)."""
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            data = json.load(f)
            return data['count_solutions'], data['count_run']
    return 0, 0


def compute(total_trials, num_workers=24, log_interval=10, save_interval=60):
    """
    Compute trials in parallel with periodic logging and saving.

    Args:
        total_trials: Total number of trials to run.
        num_workers: Number of computation threads.
        log_interval: Seconds between log outputs.
        save_interval: Seconds between file saves.

    Returns:
        Probability of solution (count_solutions / total_trials).
    """
    # Load existing progress
    count_solutions, count_run = load_progress()
    trials_remaining = total_trials - count_run

    if trials_remaining <= 0:
        logging.info("All trials completed previously.")
        return count_solutions / total_trials if total_trials > 0 else 0

    # Initial log
    probability = count_solutions / count_run if count_run > 0 else 0
    logging.info(
        f"Trials: {count_run:,} | Solutions: {count_solutions:,} | "
        f"Probability: {probability:.7f}"
    )

    # Shared counters with built-in locks
    solutions = Value('i', count_solutions)
    trials_run = Value('i', count_run)

    # Start logger thread
    logger = threading.Thread(
        target=logger_thread,
        args=(solutions, trials_run, total_trials, log_interval, save_interval),
        daemon=True
    )
    logger.start()

    # Start computation threads
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        for _ in range(num_workers):
            executor.submit(run_trials, 10000, solutions, trials_run)

        # Wait until total trials are reached
        while trials_run.value < total_trials:
            time.sleep(1)

    # Wait for logger to finish final save
    logger.join(timeout=5)

    final_solutions = solutions.value
    final_trials = trials_run.value
    return final_solutions / final_trials if final_trials > 0 else 0


if __name__ == "__main__":
    total_trials = 1000000000
    result = compute(total_trials)
    logging.info(f"Final probability: {result:.7f}")