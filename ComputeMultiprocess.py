import logging
import time # Keep time for potential delays if needed, but not for main loop logic
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Value # For shared counters
import argparse # Added for command-line argument parsing
from BesideThePoint import trial
from performance_logger import CentralizedLogger
import concurrent.futures # For as_completed

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_trials_worker(num_trials_for_batch):
    """Run a specific number of trials and return the results."""
    local_solutions = 0
    for _ in range(num_trials_for_batch):
        res = trial()
        if res['solution'] == 'Solution':
            local_solutions += 1
    return local_solutions, num_trials_for_batch

def compute(total_trials, num_workers=24, batch_size=10000, log_interval=10, save_interval=20):
    """Compute trials in parallel using processes, with CentralizedLogger, similar to ComputeNumpy."""
    
    logger = CentralizedLogger(
        compute_type=f"Multiprocess{num_workers}Processes",
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
    solutions_counter = Value('Q', initial_solutions)
    trials_run_counter = Value('Q', initial_run)

    logger.start()

    try:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            active_futures = set()
            
            submitted_trials_total = initial_run 

            # Initial submissions
            for _ in range(num_workers):
                if submitted_trials_total < total_trials:
                    current_batch_to_submit = min(batch_size, total_trials - submitted_trials_total)
                    if current_batch_to_submit <= 0: 
                        break 
                    future = executor.submit(run_trials_worker, current_batch_to_submit)
                    active_futures.add(future)
                    submitted_trials_total += current_batch_to_submit
                else:
                    break 

            while active_futures:
                # Use concurrent.futures.as_completed
                done_iterator = as_completed(active_futures)
                completed_future = next(done_iterator)

                try:
                    batch_solutions, batch_trials_from_future = completed_future.result()
                    # Ensure Python int for Value and logger
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
                        new_future = executor.submit(run_trials_worker, current_batch_to_submit)
                        active_futures.add(new_future)
                        submitted_trials_total += current_batch_to_submit
    finally:
        logger.stop()
    
    # Log final counts from shared values for verification, if desired
    logging.info(f"[{logger.compute_type}] Final raw counts - Solutions: {solutions_counter.value}, Trials: {trials_run_counter.value}")
    return logger.get_final_probability()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multiprocess-based computation for the BesideThePoint problem.")
    parser.add_argument('--total_trials', type=int, default=15_000_000_000_000,
                        help='Total number of trials to perform.')
    parser.add_argument('--num_workers', type=int, default=12,
                        help='Number of worker processes. Defaults to (12).')
    # Other parameters like batch_size, log_interval, save_interval will use defaults from the compute function.
    args = parser.parse_args()

    result = compute(args.total_trials, num_workers=args.num_workers)

    logging.info(f"Final probability (Multiprocess): {result:.10f}")