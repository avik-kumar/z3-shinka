"""Z3 SMT/SAT Solver Strategy Synthesis - Baseline Implementation

This module provides a baseline Z3 strategy for solving SMT-LIB instances.
The EVOLVE-BLOCK contains the strategy selection logic that will be improved by mutation.
"""

import z3
import time
from timeout_config import INSTANCE_TIMEOUT_MS


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
    # EVOLVE-BLOCK-END

    return {
        "mode": mode,
        "strategy_name": strategy_name,
        "primary_tactics": primary_tactics,
        "fallback_tactics": fallback_tactics,
        "use_tryfor": use_tryfor,
        "tryfor_share": tryfor_share,
    }


def _build_pipeline_tactic(ctx, tactic_names, timeout_ms, use_tryfor, tryfor_share):
    """Build a sequential tactic pipeline with optional per-tactic TryFor wrapping."""
    if not tactic_names:
        return z3.Tactic("smt", ctx=ctx)

    names = [name for name in tactic_names if isinstance(name, str) and name.strip()]
    if not names:
        return z3.Tactic("smt", ctx=ctx)

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
    fallback = cfg.get("fallback_tactics", [["smt"]])
    use_tryfor = bool(cfg.get("use_tryfor", False))
    tryfor_share = float(cfg.get("tryfor_share", 0.6))

    all_pipelines = [primary] + list(fallback)
    tactic = None
    for pipeline in all_pipelines:
        try:
            current = _build_pipeline_tactic(ctx, pipeline, timeout_ms, use_tryfor, tryfor_share)
            tactic = current if tactic is None else z3.OrElse(tactic, current)
        except Exception:
            continue

    if tactic is None:
        tactic = z3.Tactic("smt", ctx=ctx)
    return tactic


def solve_instance(instance_path, timeout_ms=INSTANCE_TIMEOUT_MS):
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
    
    try:
        # Read the SMT-LIB file
        with open(instance_path, 'r') as f:
            content = f.read()
        
        # Create a context for parsing
        ctx = z3.Context()
        
        # Parse the SMT-LIB file - returns AstVector of assertions
        assertions = z3.parse_smt2_string(content, ctx=ctx)
        
        strategy_cfg = get_strategy()
        mode = strategy_cfg.get("mode", "solver")

        if mode == "tactic":
            tactic = _build_strategy_tactic(ctx, timeout_ms)
            goal = z3.Goal(ctx=ctx)
            for assertion in assertions:
                goal.add(assertion)
            bounded_tactic = z3.TryFor(tactic, timeout_ms)

            try:
                applied = bounded_tactic(goal)
                s = z3.Solver(ctx=ctx)
                s.set(timeout=timeout_ms)
                for subgoal in applied:
                    s.add(subgoal.as_expr())
            except Exception:
                s = z3.Solver(ctx=ctx)
                s.set(timeout=timeout_ms)
                for assertion in assertions:
                    s.add(assertion)
        else:
            s = z3.Solver(ctx=ctx)
            s.set(timeout=timeout_ms)
            for assertion in assertions:
                s.add(assertion)
        
        # Measure solve time
        start = time.time()
        result = s.check()
        end = time.time()
        stats['solve_time'] = end - start
        
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
