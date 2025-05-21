import unittest
import os
import json
import time
import shutil
from datetime import datetime
from unittest.mock import patch, mock_open

# Adjust the import path if your test file is not in the same directory as performance_logger.py
from performance_logger import CentralizedLogger

class TestCentralizedLogger(unittest.TestCase):
    TEST_COMPUTE_TYPE = "TestCompute"
    TEST_TOTAL_TRIALS = 100
    LOG_INTERVAL = 0.1  # seconds
    SAVE_INTERVAL = 0.2  # seconds
    PROGRESS_PREFIX = "test_progress"
    PERFORMANCE_PREFIX = "test_performance"
    
    def setUp(self):
        # Ensure a clean state for filenames
        self.progress_file = f"{self.PROGRESS_PREFIX}-{self.TEST_COMPUTE_TYPE}.json"
        self.performance_file = f"{self.PERFORMANCE_PREFIX}-{self.TEST_COMPUTE_TYPE}.txt"
        self._cleanup_files() # Clean up before each test

    def tearDown(self):
        self._cleanup_files() # Clean up after each test

    def _cleanup_files(self):
        if os.path.exists(self.progress_file):
            os.remove(self.progress_file)
        if os.path.exists(self.performance_file):
            os.remove(self.performance_file)
        # Clean up any other potential test files if necessary
        for f in os.listdir("."):
            if f.startswith(self.PROGRESS_PREFIX + "-") or f.startswith(self.PERFORMANCE_PREFIX + "-"):
                try:
                    os.remove(f)
                except OSError:
                    pass # e.g. if it's a directory somehow, though unlikely for these prefixes

    def _create_dummy_progress_file(self, solutions, trials, filename=None):
        filename = filename or self.progress_file
        data = {'count_solutions': solutions, 'count_run': trials}
        with open(filename, 'w') as f:
            json.dump(data, f)
        return filename

    def test_01_initialization_and_filenames(self):
        logger = CentralizedLogger(
            compute_type=self.TEST_COMPUTE_TYPE,
            total_trials=self.TEST_TOTAL_TRIALS,
            log_interval_sec=self.LOG_INTERVAL,
            save_interval_sec=self.SAVE_INTERVAL,
            progress_filename_prefix=self.PROGRESS_PREFIX,
            performance_log_filename_prefix=self.PERFORMANCE_PREFIX
        )
        self.assertEqual(logger.compute_type, self.TEST_COMPUTE_TYPE)
        self.assertEqual(logger.total_trials, self.TEST_TOTAL_TRIALS)
        self.assertEqual(logger.progress_filename, self.progress_file)
        self.assertEqual(logger.performance_log_filename, self.performance_file)
        logger.stop() # Ensure thread is cleaned up if started implicitly

    def test_02_load_progress_no_file(self):
        logger = CentralizedLogger(self.TEST_COMPUTE_TYPE, self.TEST_TOTAL_TRIALS, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        self.assertEqual(logger.progress_state['solutions'], 0)
        self.assertEqual(logger.progress_state['trials_run'], 0)
        self.assertTrue(os.path.exists(self.performance_file)) # Initial log should create it
        with open(self.performance_file, 'r') as f:
            lines = f.readlines()
            self.assertGreaterEqual(len(lines), 2) # Header + initial loaded log
            self.assertTrue("Timestamp,TrialsRun,SolutionsFound,Probability" in lines[0].replace(" ", "")) # Normalize header check
            # Check the data of the initial log entry in the file
            self.assertTrue(lines[1].count(',') == 3, "Initial log line should have 3 commas")
            self.assertTrue(",0,0,0.0000000000" in lines[1].replace(" ", ""), f"Initial log data incorrect, got: {lines[1]}")
        logger.stop()

    def test_03_save_and_load_progress(self):
        initial_solutions, initial_trials = 50, 500
        self._create_dummy_progress_file(initial_solutions, initial_trials)

        logger = CentralizedLogger(self.TEST_COMPUTE_TYPE, self.TEST_TOTAL_TRIALS * 10, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        self.assertEqual(logger.progress_state['solutions'], initial_solutions)
        self.assertEqual(logger.progress_state['trials_run'], initial_trials)

        # Trigger a save
        logger.update_progress(10, 20)
        logger._save_progress() # Force save for testability

        self.assertTrue(os.path.exists(self.progress_file))
        with open(self.progress_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['count_solutions'], initial_solutions + 10)
            self.assertEqual(data['count_run'], initial_trials + 20)
        logger.stop()

    def test_04_update_progress(self):
        logger = CentralizedLogger(self.TEST_COMPUTE_TYPE, self.TEST_TOTAL_TRIALS, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        logger.update_progress(5, 10)
        s, t = logger.get_current_progress()
        self.assertEqual(s, 5)
        self.assertEqual(t, 10)

        logger.update_progress(2, 3)
        s, t = logger.get_current_progress()
        self.assertEqual(s, 7)
        self.assertEqual(t, 13)
        logger.stop()

    @patch('builtins.print') # Mock print to avoid console clutter during test
    def test_05_logging_thread_operation(self, mock_print):
        logger = CentralizedLogger(
            compute_type=self.TEST_COMPUTE_TYPE,
            total_trials=self.TEST_TOTAL_TRIALS,
            log_interval_sec=0.05, # Faster for testing
            save_interval_sec=0.1,  # Faster for testing
            progress_filename_prefix=self.PROGRESS_PREFIX,
            performance_log_filename_prefix=self.PERFORMANCE_PREFIX
        )
        logger.start()
        
        time.sleep(0.01) # brief sleep to ensure thread starts
        logger.update_progress(10, 20) # solutions, trials
        time.sleep(0.06) # Should trigger at least one log (of 20 trials, 10 solutions)
        
        current_s_after_first_log, current_t_after_first_log = logger.get_current_progress()

        logger.update_progress(5, 5) # solutions, trials (total 25 trials, 15 solutions)
        time.sleep(0.12) # Should trigger at least one save and another log
        
        current_s_after_second_log, current_t_after_second_log = logger.get_current_progress()

        logger.stop()

        # Check performance log file
        self.assertTrue(os.path.exists(self.performance_file))
        with open(self.performance_file, 'r') as f:
            lines = [line.strip().replace(" ", "") for line in f.readlines() if line.strip()] # Read and normalize lines
            
            self.assertGreaterEqual(len(lines), 4, f"Not enough lines in performance log. Got {len(lines)} lines: {lines}") 
            self.assertTrue("Timestamp,TrialsRun,SolutionsFound,Probability" in lines[0])
            
            # lines[1] is the initial log (0,0)
            self.assertTrue(",0,0,0.0000000000" in lines[1], f"Initial log data incorrect in file. Got: {lines[1]}")

            # Check for subsequent progress logs. Due to timing, we check for expected values.
            # First actual progress log should reflect (20 trials, 10 solutions)
            # Second actual progress log should reflect (25 trials, 15 solutions)
            # Final log will also be (25 trials, 15 solutions)
            
            # Look for a line with 20 trials, 10 solutions
            found_first_progress_log = any(",20,10,0.5000000000" in line for line in lines[2:])
            # Look for a line with 25 trials, 15 solutions
            found_second_progress_log = any(",25,15,0.6000000000" in line for line in lines[2:])
            
            self.assertTrue(found_first_progress_log, "Did not find log entry for 20 trials, 10 solutions in performance file.")
            self.assertTrue(found_second_progress_log, "Did not find log entry for 25 trials, 15 solutions in performance file.")
            
            # The last data line should be the final state
            self.assertTrue(f",{current_t_after_second_log},{current_s_after_second_log}," in lines[-1], f"Final log line incorrect. Expected containing: ',{current_t_after_second_log},{current_s_after_second_log},'. Got: {lines[-1]}")


        # Check progress.json file
        self.assertTrue(os.path.exists(self.progress_file))
        with open(self.progress_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data['count_solutions'], 15) # 10 + 5
            self.assertEqual(data['count_run'], 25)     # 20 + 5
        
        # mock_print.assert_called() # Verify print was called (console logging)

    def test_06_get_final_probability(self):
        logger = CentralizedLogger(self.TEST_COMPUTE_TYPE, self.TEST_TOTAL_TRIALS, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        
        # Case 1: No trials
        self.assertEqual(logger.get_final_probability(), 0)

        # Case 2: Some trials, less than total_trials
        logger.update_progress(10, 50) # solutions, trials
        self.assertAlmostEqual(logger.get_final_probability(), 10/50)

        # Case 3: Trials equal total_trials
        logger.progress_state = {'solutions': 0, 'trials_run': 0} # Reset
        logger.update_progress(25, self.TEST_TOTAL_TRIALS)
        self.assertAlmostEqual(logger.get_final_probability(), 25/self.TEST_TOTAL_TRIALS)

        # Case 4: Trials exceed total_trials (should use total_trials for calculation if total_trials > 0)
        logger.progress_state = {'solutions': 0, 'trials_run': 0} # Reset
        logger.update_progress(30, self.TEST_TOTAL_TRIALS + 20)
        self.assertAlmostEqual(logger.get_final_probability(), 30/self.TEST_TOTAL_TRIALS)

        # Case 5: total_trials = 0
        logger_zero_total = CentralizedLogger(self.TEST_COMPUTE_TYPE, 0, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        logger_zero_total.update_progress(5,10)
        self.assertAlmostEqual(logger_zero_total.get_final_probability(), 5/10)
        logger_zero_total.stop()
        logger.stop()

    def test_07_start_stop_thread_management(self):
        logger = CentralizedLogger(self.TEST_COMPUTE_TYPE, self.TEST_TOTAL_TRIALS, self.LOG_INTERVAL, self.SAVE_INTERVAL, self.PROGRESS_PREFIX, self.PERFORMANCE_PREFIX)
        self.assertIsNone(logger.logger_thread)
        logger.start()
        self.assertIsNotNone(logger.logger_thread)
        self.assertTrue(logger.logger_thread.is_alive())
        
        thread_id_1 = logger.logger_thread.ident

        # Calling start again should not create a new thread (or should warn)
        logger.start() 
        self.assertTrue(logger.logger_thread.is_alive())
        self.assertEqual(logger.logger_thread.ident, thread_id_1)

        logger.stop()
        # The join in stop() might take a moment
        time.sleep(max(self.LOG_INTERVAL, self.SAVE_INTERVAL) + 0.1) 
        if logger.logger_thread: # Thread object might still exist
             self.assertFalse(logger.logger_thread.is_alive())
        
        # Calling stop again should be safe
        logger.stop()


    def test_08_trials_completed_before_start(self):
        initial_solutions = self.TEST_TOTAL_TRIALS // 2
        initial_trials = self.TEST_TOTAL_TRIALS
        self._create_dummy_progress_file(solutions=initial_solutions, trials=initial_trials)
        
        with patch.object(CentralizedLogger, '_logging_loop') as mock_logging_loop:
            logger = CentralizedLogger(
                compute_type=self.TEST_COMPUTE_TYPE,
                total_trials=self.TEST_TOTAL_TRIALS,
                log_interval_sec=self.LOG_INTERVAL,
                save_interval_sec=self.SAVE_INTERVAL,
                progress_filename_prefix=self.PROGRESS_PREFIX,
                performance_log_filename_prefix=self.PERFORMANCE_PREFIX
            )
            logger.start() # Attempt to start
            
            mock_logging_loop.assert_not_called() 
            # If trials are complete, the thread might not be created or might exit immediately.
            # Checking is_alive() for a non-existent or quickly exited thread can be tricky.
            # The main check is that _logging_loop was not called.
            if logger.logger_thread is not None:
                self.assertFalse(logger.logger_thread.is_alive(), "Logger thread should not be alive if trials were complete at start.")

        self.assertTrue(os.path.exists(self.performance_file))
        with open(self.performance_file, 'r') as f:
            lines = [line.strip().replace(" ", "") for line in f.readlines() if line.strip()]
            self.assertGreaterEqual(len(lines), 2, f"Not enough lines in performance log. Got {len(lines)} lines: {lines}")
            self.assertTrue("Timestamp,TrialsRun,SolutionsFound,Probability" in lines[0])
            # Check the data of the initial "loaded" log entry in the file
            # File format: Timestamp,TrialsRun,SolutionsFound,Probability
            expected_data_substring = f",{initial_trials},{initial_solutions}," # e.g., ",100,50,"
            self.assertTrue(expected_data_substring in lines[1], f"Initial 'loaded' data incorrect in file. Expected containing '{expected_data_substring}'. Got: {lines[1]}")

        with open(self.progress_file, 'r') as f:
             data = json.load(f)
             self.assertEqual(data['count_solutions'], initial_solutions)
             self.assertEqual(data['count_run'], initial_trials)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False) 