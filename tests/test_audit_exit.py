"""
The audit script has to fail the run when an output is wrong. It is run as a
subprocess on a copy of the repository, once untouched and once with a metric
corrupted, and only its exit status and output are checked.
"""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import BASE


@pytest.fixture()
def repo_copy(tmp_path):
    shutil.copytree(BASE / "data", tmp_path / "data")
    shutil.copytree(BASE / "figures", tmp_path / "figures")
    (tmp_path / "src").mkdir()
    shutil.copy(BASE / "src" / "validate_results.py", tmp_path / "src")
    return tmp_path


def audit(root):
    return subprocess.run([sys.executable, str(root / "src" / "validate_results.py")],
                          capture_output=True, text=True, encoding="utf-8")


def test_audit_passes_on_the_committed_outputs(repo_copy):
    done = audit(repo_copy)
    assert done.returncode == 0, done.stdout[-800:]
    assert "0 failed" in done.stdout


def test_audit_exits_nonzero_when_a_reported_metric_is_wrong(repo_copy):
    path = repo_copy / "data" / "processed" / "metrics.json"
    metrics = json.loads(path.read_text())
    metrics["COMBO"]["rmse"] = 999.0
    path.write_text(json.dumps(metrics))
    done = audit(repo_copy)
    assert done.returncode != 0
    assert "[FAIL]" in done.stdout
