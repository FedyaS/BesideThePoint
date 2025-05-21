import datetime
import glob
import csv
import math # Added for math.isinf


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


def main():
    all_metrics_data = []
    csv_files = sorted(glob.glob("performance-*.csv")) # Sort for consistent processing order initially

    if not csv_files:
        print("No 'performance-*.csv' files found in the directory.")
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

    for row in table_rows[1:]:
        report_output_lines.append(" | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    
    final_report = "\n".join(report_output_lines)

    print("\n--- Performance Report ---")
    print(final_report)

    report_file_path = "performance-report.txt"
    with open(report_file_path, "w", encoding='utf-8') as report_file: # Added encoding
        report_file.write("--- Performance Report ---\n")
        report_file.write(final_report)
        report_file.write("\n\nNote: 'N/A (or 0 IPS)' for Time to 1B Iterations indicates effectively zero or non-positive iterations per second.")
    
    print(f"\nReport saved to {report_file_path}")

if __name__ == "__main__":
    main()