import subprocess
import sys
import os

def get_int_input(prompt, default_value):
    while True:
        try:
            user_input = input(f"{prompt} (default: {default_value:_}): ")
            if not user_input:
                return default_value
            return int(user_input)
        except ValueError:
            print("Invalid input. Please enter a number.")

def main():
    scripts = {
        1: {"name": "ComputeNumpy.py", "params": ["trials", "workers"]},
        2: {"name": "ComputeMultiprocess.py", "params": ["trials", "workers"]},
        3: {"name": "ComputeMultithread.py", "params": ["trials", "workers"]},
        4: {"name": "ComputeSimple.py", "params": ["trials"]},
        5: {"name": "ComputeCupy.py", "params": ["trials"]},
        6: {"name": "VisualBesideThePoint.py", "params": []},
        7: {"name": "ParsePerformance.py", "params": []}
    }

    print("Select a script to run:")
    for key, val in scripts.items():
        print(f"{key}. {val['name']}")

    choice = -1
    while choice not in scripts:
        try:
            choice = int(input("Enter your choice (number): "))
            if choice not in scripts:
                print("Invalid choice. Please select a number from the list.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    selected_script_info = scripts[choice]
    target_script = selected_script_info["name"]
    cmd = [sys.executable, target_script]

    default_trials = 10_000_000_000
    default_workers = 12
    
    if "trials" in selected_script_info["params"]:
        trials = get_int_input("Number of trials", default_trials)
        cmd.extend(["--total_trials", str(trials)])

    if "workers" in selected_script_info["params"]:
        try:
            cpu_cores = os.cpu_count()
            suggested_workers = f" (suggested based on CPU cores: {cpu_cores})"
        except NotImplementedError:
            suggested_workers = ""
            cpu_cores = None 
        
        workers_prompt = f"Number of workers{suggested_workers}"
        workers = get_int_input(workers_prompt, default_workers if cpu_cores is None or default_workers <= cpu_cores else cpu_cores if cpu_cores is not None else default_workers)
        cmd.extend(["--num_workers", str(workers)])

    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {target_script}: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Script {target_script} not found. Make sure it's in the same directory as interactive_run.py.", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main() 