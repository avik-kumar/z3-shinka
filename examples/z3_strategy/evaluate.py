"""Z3 Strategy Synthesis Evaluator

Evaluates evolved Z3 strategies on a dataset of SMT-LIB instances.
Computes metrics: solve-rate (primary), timing (secondary tiebreaker).
"""

import os
import json
import argparse
from pathlib import Path
from shinka.core import run_shinka_eval
from run_config import BENCHMARK_DIR, INSTANCE_TIMEOUT_MS, MAX_SMT_INSTANCES


TIMEOUT_MS = INSTANCE_TIMEOUT_MS


def get_smt_instances(benchmark_dir=BENCHMARK_DIR):
    """
    Get all .smt2 files from the benchmark directory.
    
    Args:
        benchmark_dir (str): Path to directory containing SMT-LIB instances
    
    Returns:
        list: List of absolute paths to .smt2 files
    """
    instances = []
    path = Path(benchmark_dir)
    
    if not path.exists():
        raise FileNotFoundError(f"Benchmark directory not found: {benchmark_dir}")
    
    # Recursively find all .smt2 files
    for smt_file in path.rglob("*.smt2"):
        instances.append(str(smt_file.resolve()))
    
    instances = sorted(instances)
    
    # Check if we should limit instances (useful for quick testing)
    max_instances = os.environ.get('MAX_SMT_INSTANCES')
    if max_instances:
        instances = instances[:int(max_instances)]
    
    if not instances:
        raise ValueError(f"No .smt2 files found in {benchmark_dir}")
    
    return instances


def get_kwargs(run_idx: int) -> dict:
    """
    Get kwargs for the run_experiment function.
    
    Args:
        run_idx (int): Index of the run (which instance to test)
    
    Returns:
        dict: Keyword arguments including instance_path and timeout_ms
    """
    instances = get_smt_instances()
    instance_path = instances[run_idx % len(instances)]
    
    return {
        'instance_path': instance_path,
        'timeout_ms': TIMEOUT_MS,
    }


def aggregate_metrics(results: list) -> dict:
    """
    Aggregate results from multiple runs into summary metrics.
    
    Args:
        results (list): List of stats dicts from solve_instance calls
    
    Returns:
        dict: Aggregated metrics with combined_score, public, private, extra_data
    """
    solved_count = 0
    total_count = len(results)
    solve_times = []
    sat_count = 0
    unsat_count = 0
    unknown_count = 0
    error_count = 0
    timeouts = 0
    
    per_instance_results = []
    
    for stats in results:
        per_instance_results.append({
            'instance': stats.get('instance'),
            'result': stats.get('result'),
            'solve_time': stats.get('solve_time', 0.0),
            'error': stats.get('error'),
        })
        
        if stats.get('solved', False):
            solved_count += 1
            solve_times.append(stats.get('solve_time', 0.0))
            
            if stats['result'] == 'sat':
                sat_count += 1
            elif stats['result'] == 'unsat':
                unsat_count += 1
        else:
            if stats['result'] == 'unknown':
                unknown_count += 1
                timeouts += 1
            elif stats['result'] == 'error':
                error_count += 1
    
    # Compute solve rate
    solve_rate = solved_count / total_count if total_count > 0 else 0.0
    
    # Compute average solve time (only for solved instances)
    avg_solve_time = sum(solve_times) / len(solve_times) if solve_times else 0.0
    
    return {
        'combined_score': solve_rate,  # Primary metric: solve-rate
        'public': {
            'solve_rate': solve_rate,
            'solved_count': solved_count,
            'total_count': total_count,
            'sat_count': sat_count,
            'unsat_count': unsat_count,
            'unknown_count': unknown_count,
            'error_count': error_count,
            'timeouts': timeouts,
            'avg_solve_time': avg_solve_time,
        },
        'private': {
            'per_instance_results': per_instance_results,
        },
        'extra_data': {
            'benchmark_dir': BENCHMARK_DIR,
            'timeout_ms': TIMEOUT_MS,
        },
    }


def validate_fn(stats: dict) -> tuple:
    """
    Validate that a single result is properly formatted.
    
    Args:
        stats (dict): Stats dictionary from solve_instance
    
    Returns:
        tuple: (is_valid: bool, error_message: Optional[str])
    """
    required_keys = ['instance', 'result', 'solve_time', 'solved']
    if not all(key in stats for key in required_keys):
        return False, f"Missing required keys. Has: {set(stats.keys())}"
    
    if not isinstance(stats['solved'], bool):
        return False, f"'solved' must be bool, got {type(stats['solved'])}"
    
    if not isinstance(stats['solve_time'], (int, float)):
        return False, f"'solve_time' must be numeric, got {type(stats['solve_time'])}"
    
    if stats['result'] not in ['sat', 'unsat', 'unknown', 'error']:
        return False, f"Invalid result: {stats['result']}"
    
    return True, None


def main(program_path: str, results_dir: str, max_instances: int = None):
    """
    Main evaluator entry point.
    
    Args:
        program_path (str): Path to the evolved program (initial.py)
        results_dir (str): Directory to save evaluation results
        max_instances (int): Max number of instances to test (None = all)
    
    Returns:
        tuple: (metrics, correct, error)
    """
    # Get benchmark instances
    instances = get_smt_instances()
    if max_instances:
        instances = instances[:max_instances]
    num_runs = len(instances)
    
    # Run evaluation using Shinka's standard harness
    metrics, correct, err = run_shinka_eval(
        program_path=program_path,
        results_dir=results_dir,
        experiment_fn_name="run_experiment",
        num_runs=num_runs,
        get_experiment_kwargs=get_kwargs,
        aggregate_metrics_fn=aggregate_metrics,
        validate_fn=validate_fn,
    )
    
    return metrics, correct, err


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Z3 strategy evaluator"
    )
    parser.add_argument(
        "--program_path",
        type=str,
        default="examples/z3_strategy/initial.py",
        help="Path to program to evaluate (must contain 'run_experiment')",
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        default="results",
        help="Dir to save results (metrics.json, correct.json)",
    )
    parser.add_argument(
        "--max_instances",
        type=int,
        default=MAX_SMT_INSTANCES,
        help=f"Max number of instances to test (default: {MAX_SMT_INSTANCES})",
    )
    parsed_args = parser.parse_args()
    metrics, correct, err = main(parsed_args.program_path, parsed_args.results_dir, max_instances=parsed_args.max_instances)
    
    if correct:
        print("Evaluation completed successfully.")
    else:
        print(f"Evaluation failed: {err}")
    
    print("Metrics:")
    for key, value in metrics.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"  {key}: <string_too_long_to_display>")
        elif isinstance(value, dict):
            print(f"  {key}: <dict>")
        else:
            print(f"  {key}: {value}")
