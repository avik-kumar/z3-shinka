"""Quick local runner for Z3 strategy synthesis evolution.

Usage:
    python examples/z3_strategy/run_evo.py
"""

import os
from shinka.core import EvolutionRunner, EvolutionConfig
from shinka.database import DatabaseConfig
from shinka.launch import LocalJobConfig
from timeout_config import INSTANCE_TIMEOUT_MS


def main():
    """Run a quick local evolution test on Z3 strategy synthesis."""
    
    # Run on a larger benchmark subset
    os.environ['MAX_SMT_INSTANCES'] = '40'
    
    # Minimal job config for local execution
    # Point to evaluate.py in the same directory
    job_config = LocalJobConfig(eval_program_path="examples/z3_strategy/evaluate.py")
    
    # Small database for quick testing
    db_config = DatabaseConfig(
        num_islands=2,
        archive_size=10,
    )
    
    # Evolution config for Z3 strategy synthesis
    evo_config = EvolutionConfig(
        task_sys_msg="""You are an expert in SMT/SAT solving and Z3 solver strategy synthesis.
    Evolve get_strategy() to maximize solve-rate on SMT-LIB benchmarks under strict runtime constraints.

    MUTATION TARGET:
    - Edit ONLY lines inside the EVOLVE-BLOCK in get_strategy().
    - Do not edit solve_instance() or any code outside EVOLVE-BLOCK.

    OUTPUT RULES (STRICT):
    - Include <NAME>, <DESCRIPTION>, and exactly one <DIFF> section.
    - In <DIFF>, include 2-4 SEARCH/REPLACE blocks.
    - No prose outside those required tags.
    - Preserve exact indentation/whitespace in SEARCH text.
    - Every SEARCH block must match current code verbatim.
    - Every REPLACE block must change executable behavior.
    - Each SEARCH block must be 1-3 consecutive lines copied verbatim from # Current program.
    - If unsure about exact formatting, use smaller SEARCH anchors.
    - Do not minify or reformat SEARCH text (no multiline-to-single-line list rewrites).
    - REPLACE blocks must only rewrite EVOLVE-BLOCK body lines.
    - Do not include or reference code outside EVOLVE-BLOCK in SEARCH.

    STRATEGY QUALITY RULES:
        - Keep baseline behavior stable, but allow switching mode from "solver" to "tactic"
            when it gives measurable gains.
        - Generate nuanced tactic pipelines and fallback behavior when in tactic mode.
        - Allowed Z3 building blocks: simplify, propagate-values, ctx-solver-simplify,
            solve-eqs, smt, bit-blast, aig, qe, qfbv, qfnra-nlsat, sat, Then, OrElse, Repeat, TryFor.
        - Keep edits focused on strategy config values in EVOLVE-BLOCK.
    - Prefer robust generalization across arithmetic, bit-vector, and quantified cases.
    - Every edit must change executable semantics.
    - Forbidden edits: comments-only, whitespace-only, variable renaming-only,
      reordering-only, or tactic synonyms that do not change behavior.
        - Every mutation must change at least 3 independent strategy dimensions when feasible:
            mode, primary_tactics, fallback_tactics, use_tryfor, tryfor_share,
            fallback_policy, max_fallbacks, force_terminal_smt, dedup_pipelines.
        - Prefer strategy candidates that are structurally different from parent; avoid near-duplicates.

        EXPLORATION POLICY:
        - Be brave: prefer substantial semantic edits over tiny tweaks.
        - Aim to change multiple strategy dimensions per mutation when possible
            (mode, primary_tactics, fallback_tactics, use_tryfor, tryfor_share).
        - Explore different tactic families (bit-blast/aig, qfbv, qe, qfnra-nlsat, sat)
            instead of repeating near-identical variants.
        - Rotate fallback design styles across mutations: primary_only, or_else, and chain.

    Optimization guidance:
    1. Explore diverse tactic combinations with clear rationale for ordering
    2. Balance aggressive preprocessing with solver robustness
    3. Prefer stable strategies over brittle one-off wins
    4. Avoid redundant edits that do not measurably improve solve-rate
    5. Prefer larger, multi-parameter strategy jumps over single-value nudges

    Keep the function signature unchanged. Avoid crashes/timeouts.
    Per-instance timeout budget is {} ms.""".format(INSTANCE_TIMEOUT_MS),
        language="python",
        init_program_path="examples/z3_strategy/initial.py",
        job_type="local",
        num_generations=10,
        max_parallel_jobs=4,
        llm_models=["openrouter/free"],
        llm_kwargs={"temperatures": [0.15, 0.25], "max_tokens": 4096},
        max_patch_attempts=8,
        embedding_model=None,
    )
    
    # Create and run the evolution
    runner = EvolutionRunner(
        evo_config=evo_config,
        job_config=job_config,
        db_config=db_config,
        verbose=True,
    )
    
    runner.run()


if __name__ == "__main__":
    main()
