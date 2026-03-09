"""Z3 SMT/SAT Solver Strategy Synthesis - Baseline Implementation

This module provides a baseline Z3 strategy for solving SMT-LIB instances.
The EVOLVE-BLOCK contains the strategy selection logic that will be improved by mutation.
"""

import z3
import time
import json
import sys
import argparse
import subprocess
import os
from run_config import INSTANCE_TIMEOUT_MS


def _remaining_ms(start_time: float, budget_ms: int) -> int:
    """Return remaining wall-clock budget in milliseconds."""
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    return max(0, budget_ms - elapsed_ms)


def get_strategy():
    """
    Get the Z3 solving strategy configuration.
    
    This returns a configuration that can stay in fast baseline solver mode
    or opt into tactic-pipeline mode for more complex evolved behaviors.
    
    Returns:
        dict: Strategy configuration.
    """
    # EVOLVE-BLOCK-START
    mode = "solver"
    strategy_name = "baseline_solver"

    primary_tactics = [
        "simplify",
        "smt",
    ]

    fallback_tactics = [
        ["smt"],
    ]

    use_tryfor = False
    tryfor_share = 0.5
    fallback_policy = "or_else"
    max_fallbacks = 3
    force_terminal_smt = True
    dedup_pipelines = True
    # EVOLVE-BLOCK-END

    return {
        "mode": mode,
        "strategy_name": strategy_name,
        "primary_tactics": primary_tactics,
        "fallback_tactics": fallback_tactics,
        "use_tryfor": use_tryfor,
        "tryfor_share": tryfor_share,
        "fallback_policy": fallback_policy,
        "max_fallbacks": max_fallbacks,
        "force_terminal_smt": force_terminal_smt,
        "dedup_pipelines": dedup_pipelines,
    }


def _build_pipeline_tactic(
    ctx,
    tactic_names,
    timeout_ms,
    use_tryfor,
    tryfor_share,
    force_terminal_smt=True,
):
    """Build a sequential tactic pipeline with optional per-tactic TryFor wrapping."""
    if not tactic_names:
        return z3.Tactic("smt", ctx=ctx)

    names = [name for name in tactic_names if isinstance(name, str) and name.strip()]
    if not names:
        return z3.Tactic("smt", ctx=ctx)

    # Keep final solve stage present when using tactic mode.
    if force_terminal_smt and names[-1] != "smt":
        names = names + ["smt"]

    per_tactic_ms = max(1, int((timeout_ms * max(0.0, min(1.0, tryfor_share))) / len(names)))

    tactics = []
    for name in names:
        tactic = z3.Tactic(name, ctx=ctx)
        if use_tryfor and per_tactic_ms > 0 and name != "smt":
            tactic = z3.TryFor(tactic, per_tactic_ms)
        tactics.append(tactic)

    combined = tactics[0]
    for tactic in tactics[1:]:
        combined = z3.Then(combined, tactic)
    return combined


def _build_strategy_tactic(ctx, timeout_ms):
    """Create a robust tactic from the mutable strategy config with fallback behavior."""
    cfg = get_strategy()

    primary = cfg.get("primary_tactics", ["smt"])
    fallback = list(cfg.get("fallback_tactics", [["smt"]]))
    use_tryfor = bool(cfg.get("use_tryfor", False))
    tryfor_share = float(cfg.get("tryfor_share", 0.6))
    fallback_policy = str(cfg.get("fallback_policy", "or_else"))
    max_fallbacks = max(0, int(cfg.get("max_fallbacks", 3)))
    force_terminal_smt = bool(cfg.get("force_terminal_smt", True))
    dedup_pipelines = bool(cfg.get("dedup_pipelines", True))

    fallback = fallback[:max_fallbacks]
    all_pipelines = [primary] + fallback

    if dedup_pipelines:
        seen = set()
        deduped = []
        for pipeline in all_pipelines:
            key = tuple(pipeline) if isinstance(pipeline, list) else tuple()
            if key not in seen:
                seen.add(key)
                deduped.append(pipeline)
        all_pipelines = deduped

    if fallback_policy == "primary_only":
        all_pipelines = [primary]

    tactic = None
    for pipeline in all_pipelines:
        try:
            current = _build_pipeline_tactic(
                ctx,
                pipeline,
                timeout_ms,
                use_tryfor,
                tryfor_share,
                force_terminal_smt,
            )
            if tactic is None:
                tactic = current
            elif fallback_policy == "chain":
                tactic = z3.Then(tactic, current)
            else:
                tactic = z3.OrElse(tactic, current)
        except Exception:
            continue

    if tactic is None:
        tactic = z3.Tactic("smt", ctx=ctx)
    return tactic


def _solve_instance_internal(instance_path, timeout_ms=INSTANCE_TIMEOUT_MS):
    """
    Solve a single SMT-LIB instance using the evolved strategy.
    
    Args:
        instance_path (str): Path to the SMT-LIB2 file
        timeout_ms (int): Timeout in milliseconds (default 1500)
    
    Returns:
        dict: Statistics with solve result and timing information
    """
    stats = {
        'instance': instance_path,
        'timeout_ms': timeout_ms,
        'solve_time': 0.0,
        'result': 'unknown',
        'solved': False,
        'error': None,
    }
    
    start_total = time.perf_counter()

    try:
        # Read the SMT-LIB file
        with open(instance_path, 'r') as f:
            content = f.read()

        if _remaining_ms(start_total, timeout_ms) <= 0:
            stats['result'] = 'unknown'
            stats['solved'] = False
            stats['solve_time'] = time.perf_counter() - start_total
            return stats
        
        # Create a context for parsing
        ctx = z3.Context()
        
        # Parse the SMT-LIB file - returns AstVector of assertions
        assertions = z3.parse_smt2_string(content, ctx=ctx)

        if _remaining_ms(start_total, timeout_ms) <= 0:
            stats['result'] = 'unknown'
            stats['solved'] = False
            stats['solve_time'] = time.perf_counter() - start_total
            return stats
        
        strategy_cfg = get_strategy()
        mode = strategy_cfg.get("mode", "solver")

        if mode == "tactic":
            remaining_ms = _remaining_ms(start_total, timeout_ms)
            if remaining_ms <= 0:
                stats['result'] = 'unknown'
                stats['solved'] = False
                stats['solve_time'] = time.perf_counter() - start_total
                return stats

            tactic = _build_strategy_tactic(ctx, remaining_ms)
            goal = z3.Goal(ctx=ctx)
            for assertion in assertions:
                goal.add(assertion)

            remaining_ms = _remaining_ms(start_total, timeout_ms)
            if remaining_ms <= 0:
                stats['result'] = 'unknown'
                stats['solved'] = False
                stats['solve_time'] = time.perf_counter() - start_total
                return stats

            bounded_tactic = z3.TryFor(tactic, remaining_ms)

            try:
                applied = bounded_tactic(goal)
                s = z3.Solver(ctx=ctx)
                remaining_ms = _remaining_ms(start_total, timeout_ms)
                if remaining_ms <= 0:
                    stats['result'] = 'unknown'
                    stats['solved'] = False
                    stats['solve_time'] = time.perf_counter() - start_total
                    return stats
                s.set(timeout=remaining_ms)
                for subgoal in applied:
                    s.add(subgoal.as_expr())
            except Exception:
                s = z3.Solver(ctx=ctx)
                remaining_ms = _remaining_ms(start_total, timeout_ms)
                if remaining_ms <= 0:
                    stats['result'] = 'unknown'
                    stats['solved'] = False
                    stats['solve_time'] = time.perf_counter() - start_total
                    return stats
                s.set(timeout=remaining_ms)
                for assertion in assertions:
                    s.add(assertion)
        else:
            s = z3.Solver(ctx=ctx)
            remaining_ms = _remaining_ms(start_total, timeout_ms)
            if remaining_ms <= 0:
                stats['result'] = 'unknown'
                stats['solved'] = False
                stats['solve_time'] = time.perf_counter() - start_total
                return stats
            s.set(timeout=remaining_ms)
            for assertion in assertions:
                s.add(assertion)
        
        remaining_ms = _remaining_ms(start_total, timeout_ms)
        if remaining_ms <= 0:
            stats['result'] = 'unknown'
            stats['solved'] = False
            stats['solve_time'] = time.perf_counter() - start_total
            return stats
        s.set(timeout=remaining_ms)

        result = s.check()
        stats['solve_time'] = time.perf_counter() - start_total
        
        # Interpret the solver result
        if result == z3.sat:
            stats['result'] = 'sat'
            stats['solved'] = True
        elif result == z3.unsat:
            stats['result'] = 'unsat'
            stats['solved'] = True
        else:  # z3.unknown
            stats['result'] = 'unknown'
            stats['solved'] = False
            
    except Exception as e:
        # Catch any errors (parsing, timeout, etc.)
        stats['error'] = str(e)
        stats['result'] = 'error'
        stats['solved'] = False

    if stats['solve_time'] == 0.0:
        stats['solve_time'] = time.perf_counter() - start_total
    
    return stats


def solve_instance(instance_path, timeout_ms=INSTANCE_TIMEOUT_MS):
    """Solve one instance with a strict wall-clock timeout budget."""
    start = time.perf_counter()
    cmd = [
        sys.executable,
        __file__,
        "--_solve_instance",
        "--instance_path",
        instance_path,
        "--timeout_ms",
        str(timeout_ms),
    ]

    # Generated programs run from results/...; ensure shared config imports resolve.
    env = os.environ.copy()
    strategy_dir = os.path.abspath(os.path.join(os.getcwd(), "examples", "z3_strategy"))
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        strategy_dir
        if not existing_pythonpath
        else strategy_dir + os.pathsep + existing_pythonpath
    )

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_ms / 1000.0,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {
            'instance': instance_path,
            'timeout_ms': timeout_ms,
            'solve_time': time.perf_counter() - start,
            'result': 'unknown',
            'solved': False,
            'error': None,
        }

    if proc.returncode != 0:
        stderr_text = (proc.stderr or "").strip()
        return {
            'instance': instance_path,
            'timeout_ms': timeout_ms,
            'solve_time': time.perf_counter() - start,
            'result': 'error',
            'solved': False,
            'error': stderr_text or f"Solver subprocess failed with code {proc.returncode}",
        }

    stdout_text = (proc.stdout or "").strip()
    try:
        stats = json.loads(stdout_text)
    except json.JSONDecodeError:
        return {
            'instance': instance_path,
            'timeout_ms': timeout_ms,
            'solve_time': time.perf_counter() - start,
            'result': 'error',
            'solved': False,
            'error': "Solver subprocess returned non-JSON output",
        }

    if stats.get('solve_time', 0.0) == 0.0:
        stats['solve_time'] = time.perf_counter() - start
    return stats


def run_experiment(**kwargs):
    """
    Main entry point called by the evaluator.
    
    This function is invoked by the evaluation harness with:
    - instance_path: Path to an SMT-LIB instance to solve
    - timeout_ms: Timeout in milliseconds
    
    Returns:
        dict: Statistics dictionary from solve_instance
    """
    instance_path = kwargs.get('instance_path')
    timeout_ms = kwargs.get('timeout_ms', INSTANCE_TIMEOUT_MS)
    
    if not instance_path:
        raise ValueError("instance_path must be provided")
    
    return solve_instance(instance_path, timeout_ms)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--_solve_instance", action="store_true")
    parser.add_argument("--instance_path", type=str)
    parser.add_argument("--timeout_ms", type=int, default=INSTANCE_TIMEOUT_MS)
    args, _ = parser.parse_known_args()

    if args._solve_instance and args.instance_path:
        result = _solve_instance_internal(args.instance_path, args.timeout_ms)
        print(json.dumps(result), flush=True)
