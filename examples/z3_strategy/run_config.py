"""Single source of truth for Z3 strategy evolution runtime settings."""

import os
from typing import Optional

# Dataset/evaluation settings
BENCHMARK_DIR = "tests/smt-tests"
MAX_SMT_INSTANCES = 40
INSTANCE_TIMEOUT_MS = 3000

# Evolution loop settings
NUM_GENERATIONS = 10
MAX_PARALLEL_JOBS = 4
MAX_PATCH_ATTEMPTS = 8

# LLM settings
LLM_MODELS = ["openrouter/free"]
LLM_TEMPERATURES = [0.15, 0.25]
LLM_MAX_TOKENS = 4096

# Optional hard wall timeout per evaluate.py child process (e.g. "00:30:00").
# Keep None to disable scheduler-level kill.
EVAL_WALL_TIMEOUT: Optional[str] = None


def apply_runtime_environment() -> None:
    """Apply shared runtime environment variables for evaluator discovery."""
    os.environ["MAX_SMT_INSTANCES"] = str(MAX_SMT_INSTANCES)
