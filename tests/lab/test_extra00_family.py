"""Paytaca extra input-map 0x00: naive vs paytaca walk."""

from __future__ import annotations

import pytest

from ctlab.lab.extra00 import extra00_family


@pytest.fixture(scope="module")
def family():
    return extra00_family(0)


def test_extra00_one_output_naive_empty_paytaca_has_03_04(family):
    ones = [c for c in family if c.get("n_out") == 1 and not c.get("error")]
    assert ones, "expected 1-output extra00 cases"
    for c in ones:
        assert c.get("naive_first_map_empty") is True
        assert (c.get("naive") or {}).get("first_map_empty") is True
        types = c.get("paytaca_output_types") or []
        assert types, c.get("id")
        assert "03" in types[0] and "04" in types[0], (c.get("id"), types[0])
        assert c.get("naive_last_map_dropped") is False


def test_extra00_three_output_last_map_dropped(family):
    threes = [c for c in family if c.get("n_out") == 3 and not c.get("error")]
    assert threes, "expected 3-output extra00 cases"
    for c in threes:
        assert c.get("naive_first_map_empty") is True
        types = c.get("paytaca_output_types") or []
        assert types, c.get("id")
        for t in types:
            assert "03" in t and "04" in t, (c.get("id"), t)
        assert c.get("naive_last_map_dropped") is True
        assert c.get("extra_input_sep") is True
