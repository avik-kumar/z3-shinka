# Z3 Strategy Evolution TODO

- [ ] 1. Enforce generation-level synchronization for parent/archive selection.
  - Ensure parent selection for generation `g+1` starts only after all jobs in generation `g` finish.
  - Verify island-level scheduling cannot sample incomplete generation state.
  - Add clear logs proving generation barrier behavior.

- [ ] 2. Explore WebUI/visualization and define how to leverage it.
  - Validate current visualization flow against latest run artifacts.
  - Identify views to track patch quality, island progression, and novelty/diversity.
  - Document practical monitoring workflow for debugging stalled or low-quality runs.

- [ ] 3. Improve LLM mutation reliability pipeline.
  - Reduce out-of-editable-region patch attempts.
  - Reduce `No changes applied` responses by strengthening patch anchors/format rules.
  - Add handling/retry path for `LLM response content was None` with useful diagnostics.

- [ ] 4. Evaluate stronger LLM models than `openrouter/free` for mutation quality.
  - Shortlist candidate models for diff-style code editing reliability.
  - Run small A/B smoke tests on patch validity + score movement.
  - Choose a default model set and temperatures for stable evolution runs.
