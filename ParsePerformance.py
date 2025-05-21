import datetime
import glob
import csv
import math # Added for math.isinf
import os # Added for os.path.join
import platform
try:
    import psutil
except ImportError:
    psutil = None
try:
    import GPUtil
except ImportError:
    GPUtil = None
try:
    import cpuinfo
except ImportError:
    cpuinfo = None

# Define the data directory
DATA_DIR = "data"


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

    with open(filename, 'r', encoding='utf-8') as file: # Added encoding
        reader = csv.DictReader(file)
        for i, row in enumerate(reader):
            line_num = i + 2 # 1 for header, 1 for 0-indexed enumerate
            try:
                # Strip whitespace from keys and values
                current_row_data = {k.strip(): v.strip() for k, v in row.items()}

                if "Timestamp" not in current_row_data or "TrialsRun" not in current_row_data:
                    print(f"Warning: Missing 'Timestamp' or 'TrialsRun' in {filename} at line {line_num}. Skipping row: {row}")
                    continue

                timestamp_str = current_row_data["Timestamp"]
                trials_run_str = current_row_data["TrialsRun"]

                if not timestamp_str:
                    print(f"Warning: Empty timestamp in {filename} at line {line_num}. Skipping row: {row}")
                    continue
                if not trials_run_str:
                    print(f"Warning: Empty TrialsRun in {filename} at line {line_num}. Skipping row: {row}")
                    continue
                
                if ' ' in trials_run_str:
                     print(f"Warning: Space found in 'TrialsRun' field in {filename} at line {line_num}. Value: '{trials_run_str}'. Skipping row: {row}")
                     continue

                parsed_timestamp = parse_time(timestamp_str)
                parsed_trials_run = int(trials_run_str.replace(',', '')) # Allow commas in numbers

                timestamps.append(parsed_timestamp)
                trials_run_list.append(parsed_trials_run)

            except ValueError as e: # Handles errors from parse_time and int()
                print(f"Warning: Could not parse data in {filename} at line {line_num}. Error: {e}. Skipping row: {row}")
                continue
            except Exception as e:
                print(f"Warning: An unexpected error occurred in {filename} at line {line_num}. Error: {e}. Skipping row: {row}")
                continue
    
    if len(timestamps) < 2 or len(trials_run_list) < 2:
        print(f"Warning: Not enough valid data points in {filename} to calculate performance. Collected {len(timestamps)} timestamps and {len(trials_run_list)} trial entries.")
        return None

    # Combine and sort data by timestamp
    combined_data = sorted(zip(timestamps, trials_run_list))
    
    # Filter out initial zero trial entries
    # Find the first index where trials are greater than 0
    first_meaningful_index = -1
    for i in range(len(combined_data)):
        if combined_data[i][1] > 0:
            first_meaningful_index = i
            break
    
    # If all trials are zero or only one meaningful entry, cannot calculate
    if first_meaningful_index == -1 or first_meaningful_index >= len(combined_data) - 1:
        print(f"Warning: Not enough non-zero trial data points or only one such point in {filename} to calculate performance.")
        return None

    initial_timestamp = combined_data[first_meaningful_index][0]
    initial_trials = combined_data[first_meaningful_index][1]
    
    # Use the very last entry for final timestamp and trials
    final_timestamp = combined_data[-1][0]
    final_trials = combined_data[-1][1]

    if initial_timestamp == final_timestamp and initial_trials == final_trials:
        print(f"Warning: Initial and final data points are identical in {filename} after filtering. Cannot calculate rate.")
        return None

    total_time_seconds = (final_timestamp - initial_timestamp).total_seconds()
    total_trials_processed = final_trials - initial_trials

    if total_time_seconds <= 0:
        print(f"Warning: Calculated total time is zero or negative ({total_time_seconds}s) in {filename}. Check timestamps and data consistency.")
        return None
    if total_trials_processed <= 0:
        print(f"Warning: Calculated total trials processed is zero or negative ({total_trials_processed}) in {filename}.")
        return None

    iterations_per_second = total_trials_processed / total_time_seconds
    time_for_1_billion_iterations_seconds = (1_000_000_000 / iterations_per_second) if iterations_per_second > 0 else float('inf')

    return {
        "compute_type": filename.replace("performance-", "").replace(".csv", ""),
        "iterations_per_second": iterations_per_second,
        "time_for_1_billion_iterations_seconds": time_for_1_billion_iterations_seconds,
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
    elif psutil: # Fallback to psutil if cpuinfo is not available (though we know it's not ideal for brand string)
        try:
            # This was the problematic line, psutil.cpu_info() doesn't exist.
            # We are keeping psutil for other potential uses but relying on platform or cpuinfo for CPU name.
            # For now, if cpuinfo is not present, we directly use platform.processor()
            # as psutil doesn't have a direct equivalent for the brand string.
            cpu_name = platform.processor()
            if cpu_name:
                specs["cpu"] = cpu_name
            else:
                specs["cpu"] = "N/A (platform.processor() returned empty)"
                print("Warning: platform.processor() returned an empty string for CPU info.")
        except Exception as e:
            print(f"Warning: Could not retrieve CPU information using platform.processor(): {e}")
            specs["cpu"] = "N/A (Error with platform.processor())"
    else: # Final fallback if neither cpuinfo nor psutil (for platform.processor) is available
        specs["cpu"] = platform.processor() if platform.processor() else "N/A (cpuinfo/psutil not available, platform.processor() empty)"
        if not platform.processor():
             print("Warning: cpuinfo and psutil not available, and platform.processor() returned an empty string for CPU info.")

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
        else:
            print(f"  - Could not calculate metrics for {csv_file}")

    if not all_metrics_data:
        print("\nNo valid metrics could be calculated from any file.")
        return

    # Sort by iterations_per_second (descending) for ranking
    all_metrics_data.sort(key=lambda x: x["iterations_per_second"], reverse=True)

    # Prepare data for tabulation
    headers = ["Compute Type", "Iterations per Second", "Time to 1B Iterations"]
    table_rows = [headers]

    for data in all_metrics_data:
        ips_formatted = f"{data['iterations_per_second']:,.0f}"
        time_1b_formatted = format_time_to_1b(data['time_for_1_billion_iterations_seconds'])
        table_rows.append([
            data["compute_type"],
            ips_formatted,
            time_1b_formatted
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

    for row_idx, row in enumerate(table_rows[1:]):
        formatted_cells = []
        for i, cell in enumerate(row):
            # Headers are at index 0 of table_rows, data starts from index 1
            header_name = table_rows[0][i] 
            if header_name == "Iterations per Second" or header_name == "Time to 1B Iterations":
                formatted_cells.append(str(cell).rjust(col_widths[i]))
            else:
                formatted_cells.append(str(cell).ljust(col_widths[i]))
        report_output_lines.append(" | ".join(formatted_cells))
    
    final_report = "\n".join(report_output_lines)

    print("\n--- Performance Report ---")
    print(f"OS: {machine_specs['os']}")
    print(f"CPU: {machine_specs['cpu']}")
    print(f"GPU(s): {machine_specs['gpus']}")
    print(final_report)

    # Save the report to the data directory
    report_file_path = os.path.join(DATA_DIR, "performance-report.txt")
    with open(report_file_path, "w", encoding='utf-8') as report_file: # Added encoding
        report_file.write("--- Performance Report ---\n")
        report_file.write(f"OS: {machine_specs['os']}\n")
        report_file.write(f"CPU: {machine_specs['cpu']}\n")
        report_file.write(f"GPU(s): {machine_specs['gpus']}\n")
        report_file.write(final_report)
        report_file.write("\n\nNote: 'N/A (or 0 IPS)' for Time to 1B Iterations indicates effectively zero or non-positive iterations per second.")
    
    print(f"\nReport saved to {report_file_path}")

if __name__ == "__main__":
    main()