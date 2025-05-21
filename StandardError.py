import math

def standard_error(solutions, trials):
    """Calculate standard error for a binomial proportion."""
    if trials <= 0:
        return 0.0
    p_hat = solutions / trials
    return math.sqrt(p_hat * (1 - p_hat) / trials)

def trials_and_time_for_precision(decimal_places, trials_per_second):
    """Estimate trials needed for decimal precision and time required."""
    p_hat = 0.4914  # Approximated probability from prior data
    target_se = 0.5 * 10 ** (-decimal_places)  # Standard error for precision
    
    # Calculate trials needed: SE = sqrt(p_hat * (1 - p_hat) / n)
    variance = p_hat * (1 - p_hat)
    trials_needed = math.ceil(variance / (target_se ** 2))
    
    # Calculate time in seconds
    time_seconds = math.ceil(trials_needed / trials_per_second)
    
    # Convert to years and months
    seconds_per_year = 365.25 * 24 * 3600  # Account for leap years
    seconds_per_month = seconds_per_year / 12
    
    total_months = round(time_seconds / seconds_per_month)
    years = total_months // 12
    months = total_months % 12
    
    # Format time string
    time_str = ""
    if years > 0:
        time_str += f"{years} year{'s' if years != 1 else ''}"
    if months > 0:
        if years > 0:
            time_str += " and "
        time_str += f"{months} month{'s' if months != 1 else ''}"
    if not time_str:
        time_str = "less than 1 month"
    
    return {
        "trials_needed": trials_needed,
        "time_seconds": time_seconds,
        "time_formatted": time_str
    }