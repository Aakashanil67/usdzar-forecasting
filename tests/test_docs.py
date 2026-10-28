"""
The README and METHODOLOGY are generated from templates and the saved outputs.
These tests check that the committed copies are current, that nothing was left
unfilled, and that the headline numbers they print match values recomputed here
from the forecast log, not read from the JSON the documents were built from.
"""
import re

import numpy as np
import pandas as pd
import pytest

import render_docs
from conftest import BASE, PROC

DOCS = {"README.md.tmpl": BASE / "README.md",
        "METHODOLOGY.md.tmpl": BASE / "docs" / "METHODOLOGY.md"}


@pytest.mark.parametrize("tmpl", DOCS)
def test_committed_document_is_what_the_template_renders(tmpl):
    rendered = render_docs.render(render_docs.TEMPLATES / tmpl)
    assert DOCS[tmpl].read_text(encoding="utf-8") == rendered


@pytest.mark.parametrize("tmpl", DOCS)
def test_no_placeholder_is_left_unfilled(tmpl):
    assert not re.search(r"\{\{\w+\}\}", DOCS[tmpl].read_text(encoding="utf-8"))


def test_an_unknown_key_is_an_error_not_a_blank():
    with pytest.raises(KeyError):
        render_docs.fill("{{no_such_key}}")


@pytest.mark.parametrize("path", DOCS.values())
def test_headline_rmse_values_match_the_forecast_log(path):
    log = pd.read_csv(PROC / "forecast_log.csv")
    text = path.read_text(encoding="utf-8")
    for model in ("COMBO", "AR1_log", "RW"):
        rmse = np.sqrt(((log[model] - log["realized"]) ** 2).mean())
        assert f"{rmse:.4f}" in text, model
