from __future__ import annotations

import re
from pathlib import Path

from vigil_common.topics import Topics


def test_topics_match_create_topics_sh() -> None:
    root = Path(__file__).resolve().parents[2]
    script_path = root / "infra" / "redpanda" / "create_topics.sh"
    assert script_path.exists(), f"create_topics.sh not found at {script_path}"

    content = script_path.read_text(encoding="utf-8")
    # Extract topics from TOPICS="..." block
    sh_topics: set[str] = set()
    in_topics_block = False
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('TOPICS="'):
            in_topics_block = True
            continue
        if in_topics_block:
            if line.startswith('"'):
                break
            if line and not line.startswith("#"):
                topic_name = line.split(":")[0].strip()
                if topic_name:
                    sh_topics.add(topic_name)

    topics_class = set(Topics.all_topics())
    assert sh_topics == topics_class, (
        f"Mismatch between create_topics.sh and Topics class:\n"
        f"In script only: {sh_topics - topics_class}\n"
        f"In Topics only: {topics_class - sh_topics}"
    )


def test_service_and_lib_topic_strings_consistency() -> None:
    root = Path(__file__).resolve().parents[2]
    all_known_topics = set(Topics.all_topics())

    # Pattern for topic names in VIGIL
    topic_pattern = re.compile(
        r'["\'](market\.[a-z0-9_.]+|social\.[a-z0-9_.]+|hype\.[a-z0-9_.]+|anomaly\.[a-z0-9_.]+|graph\.[a-z0-9_.]+|case\.[a-z0-9_.]+|health\.[a-z0-9_.]+|dlq\.[a-z0-9_.]+)["\']'
    )

    found_topics: dict[str, list[str]] = {}
    for base_dir in [root / "services", root / "libs"]:
        for py_path in base_dir.rglob("*.py"):
            text = py_path.read_text(encoding="utf-8")
            matches = topic_pattern.findall(text)
            for m in matches:
                found_topics.setdefault(m, []).append(str(py_path.relative_to(root)))

    unknown_topics = set(found_topics.keys()) - all_known_topics
    assert not unknown_topics, (
        f"Found unknown topic strings in services/libs: {unknown_topics}\n"
        f"Occurrences: { {t: found_topics[t] for t in unknown_topics} }"
    )
