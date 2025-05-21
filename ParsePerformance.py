import datetime
import glob
import csv
import math # Added for math.isinf
import os # Added for os.path.join
import platform
try:
    import GPUtil
except ImportError:
    GPUtil = None
try:
    import cpuinfo
except ImportError:
    cpuinfo = None

# Import functions from StandardError.py
try:
    from StandardError import standard_error, trials_and_time_for_precision
except ImportError:
    print("Warning: StandardError.py not found or functions cannot be imported. SE and Time to 10dp columns will not be available.")
    standard_error = None
    trials_and_time_for_precision = None

# Define the data directory
DATA_DIR = "data"
P_HAT_ASSUMED = 0.4914 # For SE calculations where actual proportion isn't from data


def parse_time(timestr):
    try:
        return datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            return datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S,%f")
        except ValueError as e:
            # Raise an error to be caught by the caller, indicating parsing failure
            raise ValueError(f"Timestamp '{timestr}' does not match known formats.")


def calculate_metrics(filename):
    timestamps = []
    trials_run_list = []
    solutions_list = [] # New: To store solutions count from CSV
    # p_hat_assumed is now global P_HAT_ASSUMED

    with open(filename, 'r', encoding='utf-8') as file: # Added encoding
        reader = csv.DictReader(file)
        for i, row in enumerate(reader):
            line_num = i + 2 # 1 for header, 1 for 0-indexed enumerate
            try:
                # Strip whitespace from keys and values
                current_row_data = {k.strip(): v.strip() for k, v in row.items()}

                # Extended check for required columns
                required_cols = ["Timestamp", "TrialsRun", "SolutionsFound"]
                missing_cols = [col for col in required_cols if col not in current_row_data]
                if missing_cols:
                    print(f"Warning: Missing {', '.join(missing_cols)} in {filename} at line {line_num}. Skipping row: {row}")
                    continue

                timestamp_str = current_row_data["Timestamp"]
                trials_run_str = current_row_data["TrialsRun"]
                solutions_str = current_row_data["SolutionsFound"] # New

                # Check for empty values
                if not timestamp_str:
                    print(f"Warning: Empty timestamp in {filename} at line {line_num}. Skipping row: {row}")
                    continue
                if not trials_run_str:
                    print(f"Warning: Empty TrialsRun in {filename} at line {line_num}. Skipping row: {row}")
                    continue
                if not solutions_str: # New
                    print(f"Warning: Empty Solutions in {filename} at line {line_num}. Skipping row: {row}")
                    continue
                
                if ' ' in trials_run_str:
                     print(f"Warning: Space found in 'TrialsRun' field in {filename} at line {line_num}. Value: '{trials_run_str}'. Skipping row: {row}")
                     continue
                if ' ' in solutions_str: # New: Check for spaces in solutions
                     print(f"Warning: Space found in 'Solutions' field in {filename} at line {line_num}. Value: '{solutions_str}'. Skipping row: {row}")
                     continue

                parsed_timestamp = parse_time(timestamp_str)
                parsed_trials_run = int(trials_run_str.replace(',', '')) # Allow commas in numbers
                parsed_solutions = int(solutions_str.replace(',', '')) # New: Parse solutions

                timestamps.append(parsed_timestamp)
                trials_run_list.append(parsed_trials_run)
                solutions_list.append(parsed_solutions) # New: Store solutions

            except ValueError as e: # Handles errors from parse_time and int()
                print(f"Warning: Could not parse data in {filename} at line {line_num}. Error: {e}. Skipping row: {row}")
                continue
            except Exception as e:
                print(f"Warning: An unexpected error occurred in {filename} at line {line_num}. Error: {e}. Skipping row: {row}")
                continue
    
    # Extended check for enough data points
    if len(timestamps) < 2 or len(trials_run_list) < 2 or len(solutions_list) < 2:
        print(f"Warning: Not enough valid data points in {filename} to calculate performance. Collected {len(timestamps)} timestamps, {len(trials_run_list)} trial entries, {len(solutions_list)} solution entries.")
        return None

    # Combine and sort data by timestamp (now includes solutions)
    combined_data = sorted(zip(timestamps, trials_run_list, solutions_list))
    
    # Filter out initial zero trial entries
    # Find the first index where trials are greater than 0
    first_meaningful_index = -1
    for i in range(len(combined_data)):
        if combined_data[i][1] > 0: # Check trials (index 1)
            first_meaningful_index = i
            break
    
    # If all trials are zero or only one meaningful entry, cannot calculate
    if first_meaningful_index == -1 or first_meaningful_index >= len(combined_data) - 1:
        print(f"Warning: Not enough non-zero trial data points or only one such point in {filename} to calculate performance.")
        return None

    initial_timestamp = combined_data[first_meaningful_index][0]
    initial_trials = combined_data[first_meaningful_index][1]
    # initial_solutions = combined_data[first_meaningful_index][2] # Available if needed
    
    # Use the very last entry for final timestamp, trials, and solutions
    final_timestamp = combined_data[-1][0]
    final_trials_raw_last_entry = combined_data[-1][1]
    final_solutions_raw_last_entry = combined_data[-1][2]

    if initial_timestamp == final_timestamp and initial_trials == final_trials_raw_last_entry:
        print(f"Warning: Initial and final data points are identical in {filename} after filtering. Cannot calculate rate.")
        return None

    total_time_seconds = (final_timestamp - initial_timestamp).total_seconds()
    # total_trials_processed is based on the difference from first meaningful to last
    total_trials_processed = final_trials_raw_last_entry - initial_trials


    if total_time_seconds <= 0:
        print(f"Warning: Calculated total time is zero or negative ({total_time_seconds}s) in {filename}. Check timestamps and data consistency.")
        return None
    if total_trials_processed <= 0:
        # This condition might be too strict if final_trials_raw_last_entry can be less than initial_trials due to data issues.
        # However, given the sorting and selection of first_meaningful_index, this should typically mean no progress.
        print(f"Warning: Calculated total trials processed (final_trials_raw_last_entry - initial_trials) is zero or negative ({total_trials_processed}) in {filename}.")
        return None

    iterations_per_second = total_trials_processed / total_time_seconds
    time_for_1_billion_iterations_seconds = (1_000_000_000 / iterations_per_second) if iterations_per_second > 0 else float('inf')

    current_se = 0.0
    se_after_60s = 0.0
    time_to_10dp = "N/A"

    if standard_error:
        # Calculate current SE based on final_trials_raw_last_entry and P_HAT_ASSUMED
        current_solutions_for_se = P_HAT_ASSUMED * final_trials_raw_last_entry
        current_se = standard_error(current_solutions_for_se, final_trials_raw_last_entry)

        # Calculate SE after 60 seconds
        trials_in_60s = iterations_per_second * 60
        solutions_in_60s_for_se = P_HAT_ASSUMED * trials_in_60s
        se_after_60s = standard_error(solutions_in_60s_for_se, trials_in_60s)

    if trials_and_time_for_precision and iterations_per_second > 0:
        precision_info = trials_and_time_for_precision(10, iterations_per_second)
        time_to_10dp = precision_info["time_formatted"]
    elif iterations_per_second <= 0:
        time_to_10dp = "N/A (0 IPS)"
    
    basename = os.path.basename(filename) # Robust compute_type derivation
    compute_type_val = basename.replace("performance-", "").replace(".csv", "")

    return {
        "compute_type": compute_type_val,
        "iterations_per_second": iterations_per_second,
        "time_for_1_billion_iterations_seconds": time_for_1_billion_iterations_seconds,
        "current_se": current_se,
        "se_after_60s": se_after_60s,
        "time_to_10dp": time_to_10dp,
        "last_entry_solutions": final_solutions_raw_last_entry, # New for probability and overall
        "last_entry_trials": final_trials_raw_last_entry     # New for probability and overall
    }

def format_time_to_1b(seconds):
    if seconds == float('inf') or math.isinf(seconds) or math.isnan(seconds):
        return "N/A (or 0 IPS)"
    
    total_seconds_numeric = float(seconds)
    
    mm = int(total_seconds_numeric // 60)
    ss = total_seconds_numeric % 60
    
    return f"{mm:02d} min, {ss:05.2f} sec"


def get_machine_specs():
    specs = {
        "os": "N/A",
        "cpu": "N/A",
        "gpus": "N/A"
    }
    try:
        specs["os"] = f"{platform.system()} {platform.release()}"
    except Exception as e:
        print(f"Warning: Could not retrieve OS information: {e}")

    # Try to get CPU brand string using cpuinfo
    if cpuinfo:
        try:
            info = cpuinfo.get_cpu_info()
            if 'brand_raw' in info:
                specs["cpu"] = info['brand_raw']
            else:
                # Fallback if brand_raw is not in cpuinfo's output
                print("Warning: 'brand_raw' not found in cpuinfo output. Falling back to platform.processor().")
                specs["cpu"] = platform.processor() if platform.processor() else "N/A (platform.processor() empty)"
        except Exception as e:
            print(f"Warning: Could not retrieve CPU information using cpuinfo: {e}. Falling back to platform.processor().")
            specs["cpu"] = platform.processor() if platform.processor() else "N/A (platform.processor() empty / cpuinfo error)"
    else: # Final fallback if cpuinfo is not available
        specs["cpu"] = platform.processor() if platform.processor() else "N/A (cpuinfo not available, platform.processor() empty)"
        if not platform.processor():
             print("Warning: cpuinfo not available, and platform.processor() returned an empty string for CPU info.")

    if GPUtil:
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                specs["gpus"] = ", ".join([gpu.name for gpu in gpus])
            else:
                specs["gpus"] = "No NVIDIA GPUs found"
        except Exception as e:
            print(f"Warning: Could not retrieve GPU information: {e}")
            specs["gpus"] = "Error retrieving GPU info"
        
    return specs


def main():
    machine_specs = get_machine_specs()
    all_metrics_data = []
    overall_total_solutions = 0 # New: For overall statistics
    overall_total_trials = 0    # New: For overall statistics

    # Look for CSV files in the data directory
    csv_files_path = os.path.join(DATA_DIR, "performance-*.csv")
    csv_files = sorted(glob.glob(csv_files_path))

    if not csv_files:
        print(f"No 'performance-*.csv' files found in the '{DATA_DIR}' directory.")
        return

    print("Processing performance files...")
    for csv_file in csv_files:
        print(f"  - Processing {csv_file}")
        metrics = calculate_metrics(csv_file)
        if metrics:
            all_metrics_data.append(metrics)
            # Accumulate for overall stats from last entry of each file
            overall_total_solutions += metrics.get("last_entry_solutions", 0)
            overall_total_trials += metrics.get("last_entry_trials", 0)
        else:
            print(f"  - Could not calculate metrics for {csv_file}")

    if not all_metrics_data:
        print("\nNo valid metrics could be calculated from any file.")
        return

    # Sort by iterations_per_second (descending) for ranking
    all_metrics_data.sort(key=lambda x: x["iterations_per_second"], reverse=True)

    trials_to_10dp_val_str = "N/A" 
    if trials_and_time_for_precision:
        try:
            # Using 1_000_000 IPS as a generic reference for the header label
            trials_needed_info = trials_and_time_for_precision(10, 1_000_000) 
            if trials_needed_info and "trials_needed" in trials_needed_info:
                trials_to_10dp_val_str = f"{trials_needed_info['trials_needed']:.2e}"
            else:
                print("Warning: Could not retrieve 'trials_needed' for 10dp header. Defaulting label to N/A.")
        except Exception as e:
            print(f"Warning: Error getting 'trials_needed' for 10dp header: {e}. Defaulting label to N/A.")
    else:
        print("Warning: 'trials_and_time_for_precision' function not available. 'Time to 10dp' header will use N/A for trials count.")
    
    # Prepare data for tabulation - New "Probability" column added
    headers = ["Compute Type", "Iterations per Second", "Time to 1B Iterations", "Probability", "Current SE", "SE after 60s", f"Time to 10dp ({trials_to_10dp_val_str} trials)"]
    table_rows = [headers]

    for data in all_metrics_data:
        ips_formatted = f"{data['iterations_per_second']:,.0f}"
        time_1b_formatted = format_time_to_1b(data['time_for_1_billion_iterations_seconds'])
        
        # New: Calculate and format probability from last entry
        last_sols = data.get("last_entry_solutions", 0)
        last_trials = data.get("last_entry_trials", 0)
        probability_val = (last_sols / last_trials) if last_trials > 0 else 0.0
        probability_formatted = f"{probability_val:.12f}" if last_trials > 0 else "N/A (0 trials)"

        current_se_formatted = f"{data['current_se']:.2e}" if data.get('current_se', 0) != 0 else "N/A"
        se_after_60s_formatted = f"{data['se_after_60s']:.2e}" if data.get('se_after_60s', 0) != 0 else "N/A"
        time_to_10dp_val = data.get("time_to_10dp", "N/A")

        table_rows.append([
            data["compute_type"],
            ips_formatted,
            time_1b_formatted,
            probability_formatted, # New column inserted here
            current_se_formatted,
            se_after_60s_formatted,
            time_to_10dp_val
        ])

    # Calculate column widths
    col_widths = [0] * len(headers)
    for row in table_rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Add some padding to column widths
    padding = 2
    col_widths = [w + padding for w in col_widths]

    # Generate formatted table string
    report_output_lines = []
    header_line = " | ".join(word.ljust(col_widths[i]) for i, word in enumerate(table_rows[0]))
    report_output_lines.append(header_line)
    report_output_lines.append("-+-".join("-" * col_widths[i] for i in range(len(col_widths)))) # Separator

    for row_data in table_rows[1:]: # Renamed 'row' to 'row_data'
        formatted_cells = []
        for i, cell in enumerate(row_data):
            header_name = table_rows[0][i] 
            # Added "Probability" to right-justified columns
            if header_name in ["Iterations per Second", "Time to 1B Iterations", "Probability", "Current SE", "SE after 60s"] or "Time to 10dp" in header_name:
                formatted_cells.append(str(cell).rjust(col_widths[i]))
            else:
                formatted_cells.append(str(cell).ljust(col_widths[i]))
        report_output_lines.append(" | ".join(formatted_cells))
    
    final_report_table = "\n".join(report_output_lines)

    # New: Overall statistics calculation and formatting
    overall_stats_lines = ["\n--- Overall Statistics ---"]
    if overall_total_trials > 0:
        overall_probability_val = overall_total_solutions / overall_total_trials
        overall_probability_str = f"{overall_probability_val:.12f}"
        
        overall_se_val_str = "N/A (SE function unavailable or error)"
        if standard_error:
            try:
                overall_se_calc = standard_error(overall_total_solutions, overall_total_trials)
                overall_se_val_str = f"{overall_se_calc:.6e}" # Format SE to scientific notation
            except Exception as e:
                print(f"Warning: Could not calculate overall standard error: {e}")
                overall_se_val_str = f"N/A (Error: {e})"
        
        overall_stats_lines.append(f"Total Solutions: {overall_total_solutions:,}")
        overall_stats_lines.append(f"Total Trials:    {overall_total_trials:,}")
        overall_stats_lines.append(f"Overall Probability: {overall_probability_str}")
        overall_stats_lines.append(f"Overall Standard Error: {overall_se_val_str}")
    else:
        overall_stats_lines.append("No overall trials recorded from file last entries to calculate overall statistics.")
    
    final_overall_stats_report = "\n".join(overall_stats_lines)

    print("\n--- Performance Report ---")
    print(f"OS: {machine_specs['os']}")
    print(f"CPU: {machine_specs['cpu']}")
    print(f"GPU(s): {machine_specs['gpus']}")
    print()
    print(final_report_table) # Print the table
    print()
    print(final_overall_stats_report) # Print the overall stats

    # Save the report to the data directory
    report_file_path = os.path.join(DATA_DIR, "performance-report.txt")
    with open(report_file_path, "w", encoding='utf-8') as report_file: # Added encoding
        report_file.write("--- Performance Report ---\n")
        report_file.write(f"OS: {machine_specs['os']}\n")
        report_file.write(f"CPU: {machine_specs['cpu']}\n")
        report_file.write(f"GPU(s): {machine_specs['gpus']}\n\n")
        report_file.write(final_report_table)
        report_file.write("\n")
        report_file.write(final_overall_stats_report) # Add overall stats to file
        report_file.write(f"\n\nNote: 'Current SE' is based on the trial count from the last entry of each file, using an assumed proportion of approx. {P_HAT_ASSUMED}. 'SE after 60s' is an estimate based on current IPS and the same assumed proportion.")
        report_file.write("\nNote: 'Probability' is solutions/trials from the last recorded entry of each respective file.") # New note
        report_file.write("\nNote: 'Time to 10dp' is an estimate for achieving 10 decimal places of precision for a binomial proportion around 0.4914 (or as indicated in header).") # Slightly updated note
        report_file.write("\nNote: 'Overall Statistics' are aggregated from the last recorded entries of all processed files.") # New note
    
    print(f"\nReport saved to {report_file_path}")

if __name__ == "__main__":
    main()