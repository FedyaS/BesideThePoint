import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import argparse
from BesideThePoint import trial
from performance_logger import CentralizedLogger

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def run_trials_worker(logger_instance: CentralizedLogger, stop_event: threading.Event, local_update_interval=10000):
    """Run trials continuously and update the shared logger instance periodically, checking a stop_event."""
    local_solutions = 0
    local_trials_count = 0
    
    while not stop_event.is_set():
        res = trial()
        if res['solution'] == 'Solution':
            local_solutions += 1
        local_trials_count += 1

        if local_trials_count >= local_update_interval:
            if local_trials_count > 0:
                logger_instance.update_progress(local_solutions, local_trials_count)
            local_solutions = 0
            local_trials_count = 0
    
    if local_trials_count > 0:
        logger_instance.update_progress(local_solutions, local_trials_count)


def compute(total_trials, num_workers=24, log_interval=10, save_interval=20):
    """
    Compute trials in parallel with periodic logging and saving, using CentralizedLogger.
    Workers are signaled to stop via a threading.Event.
    """
    
    stop_event = threading.Event()

    logger = CentralizedLogger(
        compute_type=f"Multithread{num_workers}Threads",
        total_trials=total_trials,
        log_interval_sec=log_interval,
        save_interval_sec=save_interval
    )

    initial_solutions, initial_run = logger.get_current_progress()

    if initial_run >= total_trials:
        logging.info(f"[{logger.compute_type}] All {total_trials:,} trials already completed.")
        logger.stop()
        return logger.get_final_probability()

    logger.start()

    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for _ in range(num_workers):
                futures.append(executor.submit(run_trials_worker, logger, stop_event, local_update_interval=10000))
            
            while not stop_event.is_set():
                _, current_trials_run = logger.get_current_progress()
                if current_trials_run >= total_trials:
                    stop_event.set()
                    break
                time.sleep(0.1)
            
            if not stop_event.is_set():
                stop_event.set()

            for future in futures:
                try:
                    future.result(timeout=log_interval + save_interval + 5)
                except TimeoutError:
                    logging.warning(f"[{logger.compute_type}] Worker thread did not complete in expected time after total trials reached.")
                except Exception as e:
                    logging.error(f"[{logger.compute_type}] Worker thread raised an exception during shutdown: {e}")

    finally:
        logger.stop()

    return logger.get_final_probability()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multithread-based computation for the BesideThePoint problem.")
    parser.add_argument('--total_trials', type=int, default=15_000_000_000_000,
                        help='Total number of trials to perform.')
    parser.add_argument('--num_workers', type=int,
                        help='Number of worker threads. Defaults to (12).')
    args = parser.parse_args()

    result = compute(args.total_trials, num_workers=args.num_workers)

    logging.info(f"Final probability (Multithread): {result:.10f}")