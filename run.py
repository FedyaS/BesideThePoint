import argparse
import subprocess
import sys
import os

def main():
    parser = argparse.ArgumentParser(description="Master script to run various BesideThePoint computations and utilities.")
    subparsers = parser.add_subparsers(dest='script_name', title='scripts',
                                       description='Available scripts to run',
                                       help='Select a script to execute')
    parser.add_argument('--trials', type=int, default=10_000_000_000,
                        help='Default number of trials for compute scripts (default: 10,000,000,000)')
    parser.add_argument('--workers', type=int, default=12,
                        help='Default number of workers for parallel compute scripts (default: 12)')

    # --- ComputeNumpy ---
    numpy_parser = subparsers.add_parser('computenumpy', help='Run ComputeNumpy.py')
    numpy_parser.add_argument('--trials', type=int,
                              help=f'Number of trials (default: {parser.get_default("trials"):_})')
    numpy_parser.add_argument('--workers', type=int,
                              help=f'Number of workers (default: {parser.get_default("workers")})')

    # --- ComputeMultiprocess ---
    multiproc_parser = subparsers.add_parser('computemultiproc', help='Run ComputeMultiprocess.py')
    multiproc_parser.add_argument('--trials', type=int,
                                  help=f'Number of trials (default: {parser.get_default("trials"):_})')
    multiproc_parser.add_argument('--workers', type=int,
                                  help=f'Number of workers (default: {parser.get_default("workers")})')

    # --- ComputeMultithread ---
    multithread_parser = subparsers.add_parser('computemultithread', help='Run ComputeMultithread.py')
    multithread_parser.add_argument('--trials', type=int,
                                    help=f'Number of trials (default: {parser.get_default("trials"):_})')
    multithread_parser.add_argument('--workers', type=int,
                                    help=f'Number of workers (default: {parser.get_default("workers")})')

    # --- ComputeSimple ---
    simple_parser = subparsers.add_parser('computesimple', help='Run ComputeSimple.py')
    simple_parser.add_argument('--trials', type=int,
                               help=f'Number of trials (default: {parser.get_default("trials"):_})')

    # --- ComputeCupy ---
    cupy_parser = subparsers.add_parser('computecupy', help='Run ComputeCupy.py')
    cupy_parser.add_argument('--trials', type=int,
                             help=f'Number of trials (default: {parser.get_default("trials"):_})')

    # --- VisualBesideThePoint ---
    subparsers.add_parser('visualize', help='Run VisualBesideThePoint.py')

    # --- ParsePerformance ---
    subparsers.add_parser('parseperformance', help='Run ParsePerformance.py')

    args = parser.parse_args()

    if not args.script_name:
        parser.print_help()
        sys.exit(1)

    script_map = {
        'computenumpy': 'ComputeNumpy.py',
        'computemultiproc': 'ComputeMultiprocess.py',
        'computemultithread': 'ComputeMultithread.py',
        'computesimple': 'ComputeSimple.py',
        'computecupy': 'ComputeCupy.py',
        'visualize': 'VisualBesideThePoint.py',
        'parseperformance': 'ParsePerformance.py'
    }

    target_script = script_map[args.script_name]
    cmd = [sys.executable, target_script]

    # Override global defaults with subcommand specific ones if provided
    trials = args.trials if hasattr(args, 'trials') and args.trials is not None else parser.get_default('trials')
    workers = args.workers if hasattr(args, 'workers') and args.workers is not None else parser.get_default('workers')

    if args.script_name in ['computenumpy', 'computemultiproc', 'computemultithread']:
        cmd.extend(['--total_trials', str(trials)])
        cmd.extend(['--num_workers', str(workers)])
    elif args.script_name in ['computesimple', 'computecupy']:
        cmd.extend(['--total_trials', str(trials)])
    
    print(f"Executing: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {target_script}: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Script {target_script} not found. Make sure it's in the same directory as run.py.", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main() 