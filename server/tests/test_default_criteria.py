"""The four default-bucket criteria must match the structured shape the
classifier prompt expects. If a future edit breaks this shape the prompt
would silently regress."""

from app.llm.default_criteria import DEFAULT_BUCKETS


def test_default_bucket_names_are_canonical():
    names = [b["name"] for b in DEFAULT_BUCKETS]
    assert names == ["Important", "Can wait", "Auto-archive", "Newsletter"]


def test_each_default_bucket_has_structured_criteria():
    for b in DEFAULT_BUCKETS:
        text = b["criteria"]
        assert "Example cases:" in text, b["name"]
        assert text.count("<positive>") == 2 and text.count("</positive>") == 2, b["name"]
        assert text.count("<nearmiss>") == 2 and text.count("</nearmiss>") == 2, b["name"]
