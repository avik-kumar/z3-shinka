# Z3 Strategy Synthesis Task: Implementation Plan

## Goal
Add a new Shinka task that evolves Z3 SMT/SAT solving strategies. The task will:
- Use SMT-LIB2 files as input instances.
- Evaluate a user-defined strategy function in evolved code.
- Score primarily by solve-rate, with speed used as a tiebreaker.
- Enforce a per-instance timeout.

No code changes are included in this document; it is a detailed implementation plan only.

## High-Level Structure to Mirror
Use the circle packing task as the reference pattern:
- Task config: configs/task/circle_packing.yaml
- Example folder: examples/circle_packing/
- Evaluator: examples/circle_packing/evaluate.py
- Seed program: examples/circle_packing/initial.py
- Optional runner: examples/circle_packing/run_evo.py
- Variant config: configs/variant/circle_packing_example.yaml

## New Files to Add
Create the following new files:
1) Task config
   - configs/task/z3_strategy.yaml

2) Example folder
   - examples/z3_strategy/
     - initial.py
     - evaluate.py
     - run_evo.py (optional but recommended for quick local testing)

3) Variant config (optional for convenience)
   - configs/variant/z3_strategy_example.yaml

## Dependency Addition
Add to pyproject.toml:
- z3-solver

## Task Config: configs/task/z3_strategy.yaml
Base this on configs/task/circle_packing.yaml. Update:
- evaluate_function._target_: examples.z3_strategy.evaluate.main
- evo_config.init_program_path: examples/z3_strategy/initial.py
- evo_config.task_sys_msg: describe strategy synthesis goals and constraints
- exp_name: shinka_z3_strategy

Keep job/evolution defaults consistent with local runs unless you want separate budgets.

## Seed Program: examples/z3_strategy/initial.py
Purpose: Provide a stable entrypoint and an editable strategy section.

Recommended structure:
- A fixed wrapper function:
  - run_strategy(instance_path) -> (solved: bool, stats: dict)
- A fixed loader:
  - load SMT-LIB2 file into Z3
- An EVOLVE block that only changes the strategy selection logic, such as:
  - choice of tactics
  - solver parameters
  - ordering or combination of tactics

Keep file I/O, parsing, and validation outside the EVOLVE block to avoid breakage.

## Evaluation Harness: examples/z3_strategy/evaluate.py
Base this on examples/circle_packing/evaluate.py and use run_shinka_eval.

Required behavior:
- Accept (program_path, results_dir)
- Load dataset directory and enumerate SMT-LIB2 instances
- For each instance, call run_strategy(instance_path)
- Enforce timeout per instance
- Compute metrics with at least:
  - combined_score: solve-rate (primary)
  - public: solve_rate, avg_time
  - private: per_instance_times, timeouts

Scoring approach (current decision):
- combined_score = solve_rate
- Use average runtime only as a tiebreaker in reporting (not in combined_score)

Timeout handling:
- If an instance exceeds timeout, mark unsolved and record timeout
- Ensure the evaluator returns correct=False for any invalid output or crash

## Optional Runner: examples/z3_strategy/run_evo.py
Base this on examples/circle_packing/run_evo.py.
- Provide a quick local run without the full CLI
- Set low generations for debug

## Variant Config: configs/variant/z3_strategy_example.yaml
Base this on configs/variant/circle_packing_example.yaml.
- Override task to z3_strategy
- Set cluster to local
- Select desired LLM/embedding models (local or hosted)

## Dataset Layout Assumptions
Assume a dataset directory, for example:
- datasets/z3_benchmarks/
  - instance_001.smt2
  - instance_002.smt2

Evaluator should accept the dataset path from config or environment.

## Validation and Correctness
Define how correctness is determined:
- A solution is correct if Z3 returns sat or unsat without error and within timeout
- Unknown results should be treated as incorrect unless you decide otherwise

Record in metrics:
- counts for sat/unsat/unknown/timeouts
- solve_rate = solved / total

## Implementation Notes
- Avoid any randomness unless controlled by seed
- Do not allow the EVOLVE block to modify the function signature
- Ensure evaluator handles crashes and exceptions cleanly

## Verification Checklist
- Run a 1-2 generation test with a small dataset
- Confirm metrics.json and correct.json are produced
- Confirm combined_score is present and numeric
- Confirm timeouts are enforced

## Next Inputs Needed
To finalize the implementation, provide:
- Dataset folder path
- Timeout value (seconds)
- Final scoring preference if different from solve-rate only
