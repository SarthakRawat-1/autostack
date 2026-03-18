from typing import Dict, Any, List

def assess_complexity_level(
    features: List[Any],
    goals: List[Any],
    challenges: List[Any],
    plan_estimated_complexity: str = "medium"
) -> str:
    feature_count = len(features)
    goal_count = len(goals)
    challenge_count = len(challenges)

    if feature_count <= 2 and goal_count <= 2 and challenge_count <= 1:
        return "simple"
    elif feature_count <= 5 and goal_count <= 4 and challenge_count <= 3:
        return "medium"
    else:
        return "complex"


def get_task_limits_for_complexity(complexity_level: str) -> Dict[str, int]:
    limits = {
        "simple": {"min_tasks": 2, "max_tasks": 4},
        "medium": {"min_tasks": 3, "max_tasks": 6},
        "complex": {"min_tasks": 5, "max_tasks": 10},
    }
    return limits.get(complexity_level, limits["medium"])
