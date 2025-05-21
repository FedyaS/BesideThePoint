import threading
import time
import json
import os
import logging
from datetime import datetime

# Configure basic logging for the logger module itself (e.g., for errors within the logger)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class CentralizedLogger:
    def __init__(self, compute_type, total_trials, log_interval_sec, save_interval_sec, progress_filename_prefix="progress", performance_log_filename_prefix="performance"):
        self.compute_type = compute_type
        self.total_trials = total_trials
        self.log_interval_sec = log_interval_sec
        self.save_interval_sec = save_interval_sec
        self.progress_filename = f"{progress_filename_prefix}-{self.compute_type}.json"
        self.performance_log_filename = f"{performance_log_filename_prefix}-{self.compute_type}.csv"

        self.progress_state = {'solutions': 0, 'trials_run': 0}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.logger_thread = None

        self._load_progress()

    def _load_progress(self):
        if os.path.exists(self.progress_filename):
            try:
                with open(self.progress_filename, 'r') as f:
                    data = json.load(f)
                with self._lock:
                    self.progress_state['solutions'] = data.get('count_solutions', 0)
                    self.progress_state['trials_run'] = data.get('count_run', 0)
                # logging.info(f"[{self.compute_type}] Progress loaded from {self.progress_filename}: {self.progress_state}")
            except json.JSONDecodeError:
                logging.error(f"[{self.compute_type}] Error decoding JSON from {self.progress_filename}. Starting fresh.")
            except Exception as e:
                logging.error(f"[{self.compute_type}] Error loading progress from {self.progress_filename}: {e}. Starting fresh.")
        else:
            logging.info(f"[{self.compute_type}] No progress file found at {self.progress_filename}. Starting fresh.")
        
        # Initial performance log entry
        self._log_performance_metrics(initial_log=True)


    def _save_progress(self):
        with self._lock:
            data_to_save = {'count_solutions': self.progress_state['solutions'], 'count_run': self.progress_state['trials_run']}
        try:
            with open(self.progress_filename, 'w') as f:
                json.dump(data_to_save, f)
            # logging.info(f"[{self.compute_type}] Progress saved to {self.progress_filename}: {data_to_save}") # Usually too verbose for interval saving
        except Exception as e:
            logging.error(f"[{self.compute_type}] Error saving progress to {self.progress_filename}: {e}")

    def _log_performance_metrics(self, initial_log=False):
        with self._lock:
            solutions = self.progress_state['solutions']
            trials = self.progress_state['trials_run']
        
        probability = solutions / trials if trials > 0 else 0
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] # Milliseconds

        log_message_console = (
            f"[{self.compute_type}] Progress - Time: {timestamp} | Trials: {trials:,} | "
            f"Solutions: {solutions:,} | Probability: {probability:.10f}"
        )
        if initial_log:
            log_message_console = (
            f"[{self.compute_type}] Loaded - Time: {timestamp} | Trials: {trials:,} | "
            f"Solutions: {solutions:,} | Probability: {probability:.10f}"
        )


        print(log_message_console) # Console output

        log_message_file = f"{timestamp}, {trials}, {solutions}, {probability:.10f}\n"
        
        try:
            # Create header if file doesn't exist or is empty
            file_exists = os.path.exists(self.performance_log_filename)
            is_empty = file_exists and os.path.getsize(self.performance_log_filename) == 0

            with open(self.performance_log_filename, 'a') as f:
                if not file_exists or is_empty:
                    f.write("Timestamp, TrialsRun, SolutionsFound, Probability\n")
                f.write(log_message_file)
        except Exception as e:
            logging.error(f"[{self.compute_type}] Error writing to performance log {self.performance_log_filename}: {e}")

    def update_progress(self, batch_solutions, batch_trials):
        if batch_trials == 0: # Avoid division by zero or no-op updates
            return
        with self._lock:
            self.progress_state['solutions'] += batch_solutions
            self.progress_state['trials_run'] += batch_trials
            # It's generally better for the logging thread to handle logging
            # to avoid blocking the main computation thread with I/O.

    def _logging_loop(self):
        logging.info(f"[{self.compute_type}] Logger thread started. Logging every {self.log_interval_sec}s, Saving progress every {self.save_interval_sec}s.")
        last_log_time = time.time()
        last_save_time = time.time()

        while not self._stop_event.is_set():
            current_trials_run_for_check = 0
            with self._lock:
                current_trials_run_for_check = self.progress_state['trials_run']

            # Check if we should stop before sleeping
            if current_trials_run_for_check >= self.total_trials:
                logging.info(f"[{self.compute_type}] Target trials ({self.total_trials:,}) reached or exceeded. Logger thread will perform final actions and stop.")
                break 
            
            # Determine the shortest time to sleep to meet the next log or save interval
            now = time.time()
            time_to_next_log = self.log_interval_sec - (now - last_log_time)
            time_to_next_save = self.save_interval_sec - (now - last_save_time)
            
            sleep_duration = min(time_to_next_log, time_to_next_save, 1) # Sleep at most 1s to remain responsive
            sleep_duration = max(0, sleep_duration) # Ensure sleep duration is not negative

            self._stop_event.wait(sleep_duration) # Use event's wait for stoppable sleep
            if self._stop_event.is_set(): # Check if stopped during sleep
                 break

            now = time.time() # Re-evaluate current time after sleeping

            # Log if interval passed
            if (now - last_log_time) >= self.log_interval_sec:
                # Use the locked value obtained at the start of this loop iteration for the check
                if current_trials_run_for_check < self.total_trials :
                    self._log_performance_metrics()
                last_log_time = now
            
            # Save progress if interval passed
            if (now - last_save_time) >= self.save_interval_sec:
                # Use the locked value obtained at the start of this loop iteration for the check
                if current_trials_run_for_check < self.total_trials:
                     self._save_progress()
                last_save_time = now

        # Final actions before thread termination
        logging.info(f"[{self.compute_type}] Logger thread performing final log and save.")
        self._log_performance_metrics() # Final log
        self._save_progress()           # Final save
        logging.info(f"[{self.compute_type}] Logger thread stopped.")

    def start(self):
        if self.logger_thread is not None and self.logger_thread.is_alive():
            logging.warning(f"[{self.compute_type}] Logger thread already running.")
            return

        # Ensure progress state reflects totals if already met
        if self.progress_state['trials_run'] >= self.total_trials:
            logging.info(f"[{self.compute_type}] All {self.total_trials:,} trials completed previously. Logger will not start a new thread, but will ensure final state is logged.")
            # self._log_performance_metrics() # Already called at end of _load_progress
            # self._save_progress() # Ensure saved state is current
            return

        self._stop_event.clear()
        self.logger_thread = threading.Thread(target=self._logging_loop, daemon=True)
        self.logger_thread.start()

    def stop(self):
        logging.info(f"[{self.compute_type}] Stop signal received for logger thread.")
        self._stop_event.set()
        if self.logger_thread and self.logger_thread.is_alive():
            # Wait for the thread to finish its current cycle and final save/log
            # Increased timeout to ensure final I/O operations can complete.
            self.logger_thread.join(timeout=max(self.log_interval_sec, self.save_interval_sec) + 5) 
            if self.logger_thread.is_alive():
                 logging.warning(f"[{self.compute_type}] Logger thread did not stop in time.")
        else:
            logging.info(f"[{self.compute_type}] Logger thread was not running or already stopped.")
        
        # Perform a final log and save just in case the thread didn't get to it or if it wasn't started because trials were complete.
        # This ensures the final state based on all updates is captured.
        # self._log_performance_metrics() # _logging_loop handles final log
        # self._save_progress()           # _logging_loop handles final save


    def get_current_progress(self):
        """Returns the current number of solutions and trials run."""
        with self._lock:
            return self.progress_state['solutions'], self.progress_state['trials_run']

    def get_final_probability(self):
        """Calculates and returns the final probability. Should be called after all trials are done."""
        with self._lock:
            solutions = self.progress_state['solutions']
            # Use total_trials for the denominator if it's the target and has been met or exceeded.
            # Otherwise, use actual trials_run. This matches original behavior in some scripts.
            trials_for_calc = self.total_trials if self.progress_state['trials_run'] >= self.total_trials and self.total_trials > 0 else self.progress_state['trials_run']
            
        if trials_for_calc > 0:
            return solutions / trials_for_calc
        return 0 