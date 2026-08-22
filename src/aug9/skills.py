from pathlib import Path


def load_skills(
    skills_directory: str = "skills",
) -> str:

    skill_paths = sorted(
        Path(skills_directory).glob(
            "**/SKILL.md"
        )
    )

    return "\n\n".join(
        path.read_text()
        for path in skill_paths
    )
