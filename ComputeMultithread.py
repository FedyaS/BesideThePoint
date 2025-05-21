import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from BesideThePoint import trial
from performance_logger import CentralizedLogger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def run_trials_worker(logger_instance: CentralizedLogger, total_trials_target: int, local_update_interval=10000):
    """Run trials continuously and update the shared logger instance periodically."""
    local_solutions = 0
    local_trials_count = 0
    
    # Worker loop: continue as long as the logger indicates total trials haven't been met.
    # This check is done periodically within the loop using logger.get_current_progress().
    while True:
        # Check global progress before starting a new trial calculation
        # This is to ensure workers stop reasonably promptly once total_trials is reached.
        _, current_total_trials_run = logger_instance.get_current_progress()
        if current_total_trials_run >= total_trials_target:
            break # Exit if overall target is met

        res = trial()
        if res['solution'] == 'Solution':
            local_solutions += 1
        local_trials_count += 1

        if local_trials_count >= local_update_interval:
            if local_trials_count > 0: # Only update if there's something to report
                logger_instance.update_progress(local_solutions, local_trials_count)
            local_solutions = 0
            local_trials_count = 0
    
    # After the loop (e.g., if total_trials was met), report any remaining local results
    if local_trials_count > 0:
        logger_instance.update_progress(local_solutions, local_trials_count)


def compute(total_trials, num_workers=24, log_interval=10, save_interval=60):
    """
    Compute trials in parallel with periodic logging and saving, using CentralizedLogger.
    """
    
    logger = CentralizedLogger(
        compute_type=f"Multithread2{num_workers}Threads",
        total_trials=total_trials,
        log_interval_sec=log_interval,
        save_interval_sec=save_interval
    )

    initial_solutions, initial_run = logger.get_current_progress()

    if initial_run >= total_trials:
        logging.info(f"[{logger.compute_type}] All {total_trials:,} trials already completed.")
        logger.stop()
        return logger.get_final_probability()

    # No longer need multiprocessing.Value for solutions and trials_run here,
    # as CentralizedLogger will manage the overall progress state.

    logger.start()

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit worker tasks
            futures = []
            for _ in range(num_workers):
                # Pass the logger instance and total_trials to each worker
                futures.append(executor.submit(run_trials_worker, logger, total_trials))
            
            # Main thread monitors overall progress and waits for completion.
            # The logger thread itself handles periodic logging and saving.
            while True:
                _, current_trials_run = logger.get_current_progress()
                if current_trials_run >= total_trials:
                    break
                time.sleep(1) # Check progress periodically
            
            # Wait for all worker threads to complete their current tasks and exit their loops.
            # This happens once they see that total_trials has been reached via logger.get_current_progress().
            for future in futures:
                try:
                    future.result(timeout=log_interval + save_interval + 5) # Wait for worker to finish
                except concurrent.futures.TimeoutError:
                    logging.warning(f"[{logger.compute_type}] Worker thread did not complete in expected time after total trials reached.")
                except Exception as e:
                    logging.error(f"[{logger.compute_type}] Worker thread raised an exception during shutdown: {e}")

    finally:
        logger.stop() # Ensure logger stops and finalizes logs/saves

    return logger.get_final_probability()


if __name__ == "__main__":
    total_trials = 500_000_000
    result = compute(total_trials)
    logging.info(f"Final probability (Multithread2): {result:.10f}")