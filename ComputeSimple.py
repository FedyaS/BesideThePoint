import logging
from performance_logger import CentralizedLogger
from BesideThePoint import trial # Assuming this is the correct import for the trial function
import argparse # Added for command-line argument parsing

# Configure logging for this script (e.g., final result, errors outside logger)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_batch(batch_size_for_worker):
    """Runs a batch of trials and returns solutions and trials run."""
    solutions = 0
    for _ in range(batch_size_for_worker):
        res = trial()
        if res['solution'] == 'Solution':
            solutions += 1
    return solutions, batch_size_for_worker

def compute(total_trials, batch_size=10000, log_interval=10, save_interval=20):
    """Compute trials in a simple loop with CentralizedLogger."""
    
    logger = CentralizedLogger(
        compute_type="SimpleCPU",
        total_trials=total_trials,
        log_interval_sec=log_interval,
        save_interval_sec=save_interval
    )

    initial_solutions, initial_run = logger.get_current_progress()

    if initial_run >= total_trials:
        # Using script's logger for this message, as CentralizedLogger already logged loaded state.
        logging.info(f"[{logger.compute_type}] All {total_trials:,} trials already completed based on loaded progress.")
        logger.stop() # Ensure logger finalizes if it was doing anything
        return logger.get_final_probability()

    logger.start()

    try:
        while True:
            # Get current progress from the logger
            _, current_trials_run = logger.get_current_progress()
            
            if current_trials_run >= total_trials:
                break # All trials are done

            # Determine how many trials to run in this batch
            current_batch_to_run = min(batch_size, total_trials - current_trials_run)
            
            if current_batch_to_run <= 0: # Should ideally not be hit if loop condition is right
                break
            
            # Run the batch of trials
            batch_solutions, num_trials_in_batch = run_batch(current_batch_to_run)
            
            # Update the logger with the results of this batch
            logger.update_progress(batch_solutions, num_trials_in_batch)
            
    finally:
        logger.stop() # Ensure logger stops and finalizes logs/saves
    
    return logger.get_final_probability()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run simple loop-based computation for the BesideThePoint problem.")
    parser.add_argument('--total_trials', type=int, default=15_000_000_000_000,
                        help='Total number of trials to perform.')
    # batch_size, log_interval, save_interval will use defaults from the compute function.
    args = parser.parse_args()

    result = compute(args.total_trials)
    logging.info(f"Final probability (SimpleCPU): {result:.10f}")