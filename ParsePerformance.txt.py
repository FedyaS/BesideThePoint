import datetime


def parse_time(timestr):
    return datetime.datetime.strptime(timestr, "%Y-%m-%d %H:%M:%S,%f")


def calculate_avg_time_per_million(filename):
    times = []
    trials = []

    with open(filename, 'r') as file:
        for line in file:
            parts = line.split(" - ")
            timestamp = parts[0]
            trial_data = parts[1].split(" | ")[0]
            trial_count = int(trial_data.split(": ")[1].replace(",", ""))
            times.append(parse_time(timestamp))
            trials.append(trial_count)

    total_time = (times[-1] - times[0]).total_seconds()
    total_trials = trials[-1] - trials[0]
    avg_time_per_trial = total_time / total_trials
    return avg_time_per_trial * 1_000_000

avg_time = calculate_avg_time_per_million("Performance.txt")
print(f"Average time for 1,000,000 trials: {avg_time:.4f} seconds - Script1")
avg_time = calculate_avg_time_per_million("Performance2.txt")
print(f"Average time for 1,000,000 trials: {avg_time:.4f} seconds - Script2, 4 workers")
avg_time = calculate_avg_time_per_million("Performance3.txt")
print(f"Average time for 1,000,000 trials: {avg_time:.4f} seconds - Script2, 24 workers")
avg_time = calculate_avg_time_per_million("PerformanceNP1.txt")
print(f"Average time for 1,000,000 trials: {avg_time:.4f} seconds - ScriptNP, 24 workers")