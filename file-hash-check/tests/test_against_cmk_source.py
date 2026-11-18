#!/usr/bin/env python3
"""Validate the plug-ins and the built .mkp against a Checkmk 2.4 source checkout.

Needs a checkout of https://github.com/Checkmk/checkmk (branch 2.4.0) and pydantic:
    git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
    CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
"""

import importlib
import importlib.util
import os
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMK_SRC = Path(os.environ.get("CMK_SRC", "/tmp/cmk"))
for pkg in ("cmk-rulesets", "cmk-server-side-calls", "cmk-mkp-tool"):
    sys.path.insert(0, str(CMK_SRC / "packages" / pkg))
sys.path.append(str(CMK_SRC))  # for cmk.discover_plugins (namespace package "cmk")

sys.path.insert(0, str(ROOT))
import build_mkp  # noqa: E402

from cmk.mkp_tool._mkp import Manifest, PackagePart, extract_manifest, extract_mkp  # noqa: E402
from cmk.rulesets.v1 import entry_point_prefixes as rs_prefixes  # noqa: E402
from cmk.server_side_calls.v1 import (  # noqa: E402
    ActiveCheckCommand,
    HostConfig,
    IPv4Config,
)
from cmk.server_side_calls.v1 import entry_point_prefixes as ssc_prefixes  # noqa: E402


def _load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _discovered(module, prefixes):
    """Mimic cmk.discover_plugins: top-level names with the right prefix and type."""
    return {
        name: obj
        for name, obj in vars(module).items()
        for typ, prefix in prefixes.items()
        if name.startswith(prefix) and isinstance(obj, typ)
    }


class TestAgainstCmk24(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.mkp = build_mkp.build(build_mkp.MANIFEST["version"], Path(cls.tmp.name) / "dist")
        # install into a fake site: ~/local/lib/python3/cmk_addons/plugins
        cls.site_py3 = Path(cls.tmp.name, "site/local/lib/python3")
        cls.plugins_dir = cls.site_py3 / "cmk_addons/plugins"
        cls.manifest = extract_manifest(cls.mkp.read_bytes())
        extract_mkp(cls.manifest, cls.mkp.read_bytes(),
                    lambda part: {PackagePart.CMK_ADDONS_PLUGINS: cls.plugins_dir}[part])
        sys.path.insert(0, str(cls.site_py3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest(self):
        m = self.manifest
        self.assertIsInstance(m, Manifest)
        self.assertEqual((m.name, str(m.version)), ("file_hash_check", "1.0.0"))
        self.assertEqual(m.version_min_required, "2.4.0")
        with tarfile.open(self.mkp, "r:gz") as tgz:
            self.assertEqual(sorted(tgz.getnames()),
                             ["cmk_addons_plugins.tar", "info", "info.json"])
            json_manifest = Manifest.model_validate_json(tgz.extractfile("info.json").read())
        self.assertEqual(json_manifest, m)

    def test_executable_bit_after_install(self):
        exe = self.plugins_dir / "file_hash/libexec/check_file_hash"
        self.assertTrue(exe.stat().st_mode & stat.S_IXUSR, oct(exe.stat().st_mode))

    def test_ruleset_discovery_and_form(self):
        mod = importlib.import_module("cmk_addons.plugins.file_hash.rulesets.file_hash")
        found = _discovered(mod, rs_prefixes())
        self.assertEqual(list(found), ["rule_spec_file_hash"])
        rs = found["rule_spec_file_hash"]
        self.assertEqual(rs.name, "file_hash")
        form = rs.parameter_form()
        self.assertEqual(set(form.elements), {"files", "timeout", "verify_tls"})
        entry = form.elements["files"].parameter_form.element_template
        self.assertEqual(set(entry.elements), {"url", "algorithm", "expected_hash", "name"})
        self.assertEqual(entry.elements["algorithm"].parameter_form.prefill.value, "sha256")
        url_validator = entry.elements["url"].parameter_form.custom_validate[0]
        url_validator("https://example.com/a.iso")
        with self.assertRaises(Exception):
            url_validator("ftp://example.com/a.iso")

    def test_ssc_discovery_and_commands(self):
        mod = importlib.import_module("cmk_addons.plugins.file_hash.server_side_calls.file_hash")
        found = _discovered(mod, ssc_prefixes())
        self.assertEqual(list(found), ["active_check_file_hash"])
        ac = found["active_check_file_hash"]
        self.assertEqual(ac.name, "file_hash")  # -> executable check_file_hash

        # Checkmk 2.4 executable lookup (cmk/discover_plugins/_libexec.py)
        # (same logic as family_libexec_dir: <module dir>/../libexec)
        module_file = Path(mod.__file__)
        family_libexec = module_file.parent.parent / "libexec"
        self.assertTrue((family_libexec / f"check_{ac.name}").exists())

        host = HostConfig(name="cmk-server", ipv4_config=IPv4Config(address="127.0.0.1"),
                          macros={"$HOSTNAME$": "cmk-server"})
        params = {
            "files": [
                {"url": "https://example.com/a.iso", "algorithm": "sha256",
                 "expected_hash": "AB" * 32},
                {"url": "http://$HOSTNAME$/b.bin", "algorithm": "md5",
                 "expected_hash": "cd" * 16, "name": "Firmware B"},
            ],
            "timeout": 12.5,
            "verify_tls": False,
        }
        cmds = list(ac(params, host))
        self.assertTrue(all(isinstance(c, ActiveCheckCommand) for c in cmds))
        self.assertEqual([c.service_description for c in cmds],
                         ["File hash https://example.com/a.iso", "File hash Firmware B"])
        self.assertEqual(list(cmds[1].command_arguments),
                         ["--url", "http://cmk-server/b.bin", "--algorithm", "md5",
                          "--expected", "cd" * 16, "--timeout", "12.5", "--no-verify-tls"])
        for c in cmds:
            print(" ", c.service_description, "->", list(c.command_arguments))

        # defaults: no timeout, TLS verification on
        cmd = next(iter(ac({"files": [params["files"][0]]}, host)))
        self.assertNotIn("--no-verify-tls", cmd.command_arguments)
        self.assertNotIn("--timeout", cmd.command_arguments)

    def test_real_checkmk_discovery_and_executable_lookup(self):
        """Use Checkmk's own plug-in discovery and libexec lookup (cmk.discover_plugins)."""
        from cmk.discover_plugins import (
            discover_executable,
            discover_modules,
            discover_plugins_from_modules,
            family_libexec_dir,
            PluginGroup,
        )

        for group, prefixes, expected in (
            (PluginGroup.RULESETS, rs_prefixes(), "rule_spec_file_hash"),
            (PluginGroup.SERVER_SIDE_CALLS, ssc_prefixes(), "active_check_file_hash"),
        ):
            mods = [m for m in discover_modules(group, raise_errors=False) if ".file_hash." in m]
            self.assertEqual(len(mods), 1, mods)
            res = discover_plugins_from_modules(prefixes, mods, raise_errors=True)
            self.assertEqual(res.errors, [])
            self.assertEqual([loc.name for loc in res.plugins], [expected])
            if group is PluginGroup.SERVER_SIDE_CALLS:
                (loc,) = res.plugins
                exe = discover_executable("check_file_hash", family_libexec_dir(loc.module))
                self.assertEqual(exe, self.plugins_dir / "file_hash/libexec/check_file_hash")


if __name__ == "__main__":
    unittest.main(verbosity=2)
