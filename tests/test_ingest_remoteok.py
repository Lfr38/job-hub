"""Test per ingest_remoteok — caricamento config e struttura dati."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'execution'))

from ingest_remoteok import _default_tags


def test_default_tags_from_config():
    """I tag devono essere letti dal config YAML (non hardcoded)."""
    tags = _default_tags()
    assert isinstance(tags, list), f"Expected list, got {type(tags)}"
    assert len(tags) > 0, "Tags list should not be empty"
    # Must include the AI/LLM tags we added
    assert "ai" in tags or "machine-learning" in tags, "Should include AI-related tags"
    assert "python" in tags, "Should include python"
    assert "cybersecurity" in tags, "Should include cybersecurity"


def test_tags_are_deduplicated():
    """I tag non dovrebbero avere duplicati."""
    tags = _default_tags()
    assert len(tags) == len(set(tags)), f"Duplicates found in tags: {tags}"
