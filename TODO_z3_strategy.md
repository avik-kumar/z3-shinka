# Z3 Strategy Evolution TODO

- [ ] 1. Finalize implementation plan for robust evolution in `examples/z3_strategy`.
  - Define exact changes for prompting, mutation structure, and novelty settings.
  - Decide minimal safe defaults for smoke vs full runs.

- [ ] 2. Fix repeated patch-attempt failures (`No changes applied` / missing diffs).
  - Improve diff prompt anchors and patch formatting rules.
  - Add diagnostics to capture why each failed patch was rejected.

- [ ] 3. Add SEARCH-block verification that does not distract solver evolution.
  - Validate SEARCH matches EVOLVE-BLOCK lines before apply.
  - Keep verification lightweight and local so strategy search stays focused on solver quality.

- [ ] 4. Consolidate run configuration into one file.
  - Centralize generations, LLM temperatures, timeout, max instances, patch attempts, and parallel jobs.
  - Make `run_evo.py`, `evaluate.py`, and timeout settings read from the same config source.
