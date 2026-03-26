import pytest
from battle.tests.base import get_template


def test_spa_template_loads():
    t = get_template("spa")
    assert t.name == "spa"
    assert len(t.prompt) > 100
    assert len(t.acceptance_criteria) >= 3


def test_tooling_template_loads():
    t = get_template("tooling")
    assert t.name == "tooling"
    assert len(t.acceptance_criteria) >= 3


def test_mobile_template_loads():
    t = get_template("mobile")
    assert t.name == "mobile"
    assert len(t.acceptance_criteria) >= 3


def test_api_template_loads():
    t = get_template("api")
    assert t.name == "api"
    assert len(t.acceptance_criteria) >= 6


def test_unknown_template_raises():
    with pytest.raises(KeyError, match="unknown"):
        get_template("unknown")
