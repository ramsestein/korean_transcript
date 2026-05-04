from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from app.config import Settings
from app.llm.client import TaskName, get_provider

logger = logging.getLogger(__name__)

_CANDIDATE_PATHS = [
    # Docker layout: /app/app/llm/ -> /app/prompts/
    Path(__file__).parent.parent.parent / "prompts" / "judge_prompt_quality.md",
    # Local dev layout
    Path(__file__).parent.parent.parent.parent / "prompts" / "judge_prompt_quality.md",
]


def _load_prompt() -> str:
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    logger.error("Judge prompt not found in: %s", _CANDIDATE_PATHS)
    return ""


async def judge_output(
    task_type: Literal["reconstruct", "translate", "summary"],
    input_data: dict,
    output_data: dict | str,
    expected_constraints: str,
    target_language: str | None,
    judge: Literal["judge_a", "judge_b"],
    settings: Settings,
) -> dict:
    """
    Call a judge LLM to score an output.
    Returns the judge's structured JSON response.
    """
    provider, model = get_provider(judge, settings)
    system_prompt = _load_prompt()

    user_payload = {
        "task_type": task_type,
        "input": input_data,
        "output": output_data,
        "expected_constraints": expected_constraints,
        "target_language": target_language,
    }

    result = await provider.complete_json(
        model=model,
        system=system_prompt,
        user=json.dumps(user_payload, ensure_ascii=False),
        max_tokens=1024,
    )

    return _validate_judge_result(result)


def _validate_judge_result(result: dict) -> dict:
    scores = result.get("scores", {})
    return {
        "scores": {
            "accuracy": int(scores.get("accuracy", 1)),
            "no_hallucination": int(scores.get("no_hallucination", 1)),
            "terminology_preservation": int(scores.get("terminology_preservation", 1)),
            "uncertainty_handling": int(scores.get("uncertainty_handling", 1)),
            "target_language_fluency": int(scores.get("target_language_fluency", 1)),
        },
        "critical_failures": list(result.get("critical_failures", [])),
        "pass": bool(result.get("pass", False)),
        "reason": str(result.get("reason", "")),
        "suggested_prompt_changes": list(result.get("suggested_prompt_changes", [])),
    }
