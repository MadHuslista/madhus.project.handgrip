"""End-to-end CLI smoke tests.

These tests invoke the installed ``lsl-viewer`` entry-point as a subprocess
and verify that:

* The help flag exits cleanly.
* An invalid mode exits with a non-zero code.
* CSV replay raises a clear error when the data files are absent.

NiceGUI's ``ui.run()`` is a blocking call that starts a web server, so full
replay/live UI tests are out of scope for this test file — they require a
real LSL network or hardware.  These smoke tests validate the import chain,
config resolution, and mode-dispatch guard rail.
"""

from __future__ import annotations

import subprocess
import sys


def _run(*args: str, timeout: int = 20) -> subprocess.CompletedProcess:
    """Run lsl-viewer as a subprocess."""
    return subprocess.run(
        [sys.executable, "-m", "lsl_viewer", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd="/tmp",  # Neutral cwd — no accidental config files
    )


class TestHelpFlag:
    def test_hydra_help_exits_zero(self):
        """Hydra's --help flag should print usage and exit cleanly."""
        result = _run("--help")
        # Hydra exits 0 on --help
        assert result.returncode == 0, result.stderr

    def test_hydra_cfg_flag_exits_zero(self):
        """Hydra's --cfg job flag dumps the resolved config and exits 0."""
        result = _run("--cfg", "job")
        assert result.returncode == 0, result.stderr
        assert "viewer" in result.stdout


class TestInvalidMode:
    def test_unsupported_mode_raises_runtime_error(self):
        """Passing an unknown mode should exit non-zero with a clear message."""
        result = _run("mode=unsupported_xyz", timeout=15)
        # Hydra wraps RuntimeError into a non-zero exit code
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        assert "unsupported_xyz" in combined or "Unsupported" in combined or "Error" in combined


class TestMissingReplayFiles:
    def test_csv_replay_missing_files_exits_nonzero(self):
        """CSV replay with non-existent files should fail, not hang."""
        result = _run(
            "mode=csv_replay",
            "reference.target_csv_path=/tmp/__nonexistent_target__.csv",
            "reference.reference_csv_path=/tmp/__nonexistent_reference__.csv",
            timeout=20,
        )
        assert result.returncode != 0
        combined = result.stdout + result.stderr
        # Should mention the missing file or an error condition
        assert any(kw in combined for kw in ("nonexistent", "not found", "No such file", "Error", "error"))
