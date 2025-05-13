import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from BesideThePoint import trial

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')


def run_trial(_):
    """Execute a single trial and return 1 if solution found, else 0."""
    sol = trial()
    return 1 if sol['solution'] == 'Solution' else 0


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


def compute(trials, num_workers=4, log_interval=1000000, save_interval=1000000):
    """
    Compute trials in parallel, log progress, and save to file.

    Args:
        trials: Total number of trials to run.
        num_workers: Number of threads to use.
        log_interval: Log progress every log_interval trials.
        save_interval: Save progress every save_interval trials.

    Returns:
        Probability of solution (count_solutions / count_run).
    """
    # Load existing progress
    count_solutions, count_run = load_progress()
    trials_remaining = trials - count_run

    if trials_remaining <= 0:
        logging.info("All trials completed previously.")
        return count_solutions / count_run if count_run > 0 else 0

    # Run trials in parallel
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        while count_run < trials:
            # Process trials in chunks to allow periodic logging/saving
            chunk_size = min(log_interval, trials - count_run)
            results = executor.map(run_trial, range(chunk_size))
            chunk_solutions = sum(results)

            count_solutions += chunk_solutions
            count_run += chunk_size

            # Log progress
            probability = count_solutions / count_run if count_run > 0 else 0
            logging.info(
                f"Trials: {count_run:,} | Solutions: {count_solutions:,} | "
                f"Probability: {probability:.4f}"
            )

            # Save progress
            if count_run % save_interval == 0:
                save_progress(count_solutions, count_run)

    # Final save
    save_progress(count_solutions, count_run)

    return count_solutions / count_run if count_run > 0 else 0


if __name__ == "__main__":
    # Example usage
    total_trials = 1000000000
    result = compute(total_trials)
    logging.info(f"Final probability: {result:.4f}")