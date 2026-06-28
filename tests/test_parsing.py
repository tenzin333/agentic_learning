"""Tests for parse_model_json - the function that survives messy LLM output.

This is the highest-value thing to test, because its whole job is coping with
the many shapes a model response can arrive in.
"""

import pytest

from utils import parse_model_json


def test_clean_json():
    # The happy path: the model returned exactly a JSON object.
    assert parse_model_json('{"category": "billing"}') == {"category": "billing"}


def test_fenced_json():
    # Models love wrapping JSON in ```json ... ``` code fences.
    raw = '```json\n{"category": "technical"}\n```'
    assert parse_model_json(raw) == {"category": "technical"}


def test_json_with_surrounding_prose():
    # "Sure! Here's the answer: {...} hope that helps" - extract the {...}.
    raw = 'Sure! Here is the result: {"category": "account"} hope that helps'
    assert parse_model_json(raw) == {"category": "account"}


def test_garbage_raises():
    # No JSON at all -> should raise, so the caller can mark it parse_error.
    with pytest.raises(ValueError):
        parse_model_json("this is not json at all")
