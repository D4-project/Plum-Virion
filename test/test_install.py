"""Check Codex registration without changing the user's actual Codex config."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallerTest(unittest.TestCase):
    """Run the actual installer with fake Python and Codex executables."""

    def test_paths_and_existing_registration_preserved(self):
        """Support spaces and preserve existing local configuration/registration."""
        with tempfile.TemporaryDirectory(prefix="virion installer ") as folder:
            root = Path(folder)
            shutil.copy(ROOT / "install.sh", root / "install.sh")
            shutil.copy(ROOT / "config.yaml.sample", root / "config.yaml.sample")
            binaries = root / "bin"
            binaries.mkdir()
            (root / ".venv/bin").mkdir(parents=True)
            log = root / "codex.args"
            scripts = {
                binaries / "python3": "#!/bin/sh\nexit 0\n",
                root / ".venv/bin/python": "#!/bin/sh\nexit 0\n",
                binaries
                / "codex": (
                    '#!/bin/sh\nif [ "$2" = get ]; then '
                    'exit "${VIRION_TEST_EXISTS:-1}"; fi\n'
                    'printf "%s\\n" "$@" > "$VIRION_TEST_LOG"\n'
                ),
            }
            for path, content in scripts.items():
                path.write_text(content)
                path.chmod(0o755)
            env = {
                **os.environ,
                "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                "VIRION_TEST_LOG": str(log),
            }
            subprocess.run(
                ["bash", str(root / "install.sh"), "--codex"],
                env=env,
                check=True,
                capture_output=True,
            )
            self.assertEqual(
                log.read_text().splitlines(),
                [
                    "mcp",
                    "add",
                    "plum-virion",
                    "--",
                    str(root / ".venv/bin/plum-virion"),
                    "--config",
                    str(root / "config.yaml"),
                ],
            )
            self.assertEqual((root / "config.yaml").stat().st_mode & 0o777, 0o600)
            original = (root / "config.yaml").read_text()
            log.unlink()
            env["VIRION_TEST_EXISTS"] = "0"
            result = subprocess.run(
                ["bash", str(root / "install.sh"), "--codex"],
                env=env,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(log.exists())
            self.assertEqual((root / "config.yaml").read_text(), original)
