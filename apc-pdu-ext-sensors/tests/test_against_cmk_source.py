#!/usr/bin/env python3
"""Validate the plug-ins and the built .mkp against a Checkmk 2.4 source checkout.

Needs a checkout of https://github.com/Checkmk/checkmk (branch 2.4.0) and pydantic:
    git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
    pip install pydantic
    CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
"""

import importlib
import os
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMK_SRC = Path(os.environ.get("CMK_SRC", "/tmp/cmk"))
for pkg in ("cmk-agent-based", "cmk-rulesets", "cmk-graphing", "cmk-mkp-tool"):
    sys.path.insert(0, str(CMK_SRC / "packages" / pkg))
sys.path.append(str(CMK_SRC))

sys.path.insert(0, str(ROOT))
import build_mkp  # noqa: E402

from cmk.agent_based.v2 import entry_point_prefixes as ab_prefixes  # noqa: E402
from cmk.discover_plugins import (  # noqa: E402
    PluginGroup,
    discover_modules,
    discover_plugins_from_modules,
)
from cmk.graphing.v1 import entry_point_prefixes as graph_prefixes  # noqa: E402
from cmk.mkp_tool._mkp import Manifest, PackagePart, extract_manifest, extract_mkp  # noqa: E402
from cmk.rulesets.v1 import entry_point_prefixes as rs_prefixes  # noqa: E402
from cmk.rulesets.v1.form_specs import LevelsType  # noqa: E402


def _discovered(module, prefixes):
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
        cls.site_py3 = Path(cls.tmp.name, "site/local/lib/python3")
        cls.plugins_dir = cls.site_py3 / "cmk_addons/plugins"
        cls.manifest = extract_manifest(cls.mkp.read_bytes())
        extract_mkp(
            cls.manifest,
            cls.mkp.read_bytes(),
            lambda part: {PackagePart.CMK_ADDONS_PLUGINS: cls.plugins_dir}[part],
        )
        sys.path.insert(0, str(cls.site_py3))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest(self):
        manifest = self.manifest
        self.assertIsInstance(manifest, Manifest)
        self.assertEqual((manifest.name, str(manifest.version)), ("apc_pdu_ext_sensors", "1.1.0"))
        self.assertEqual(manifest.version_min_required, "2.4.0")
        self.assertEqual(manifest.version_packaged, "2.4.0")
        self.assertIsNone(manifest.version_usable_until)
        self.assertEqual(manifest.author, "Hugo Proost (h.proost[at]iubentium[dot]nl)")
        self.assertEqual(
            manifest.download_url,
            "https://github.com/hg-prst/checkmk/tree/main/apc-pdu-ext-sensors",
        )
        with tarfile.open(self.mkp, "r:gz") as tgz:
            self.assertEqual(
                sorted(tgz.getnames()),
                ["cmk_addons_plugins.tar", "info", "info.json"],
            )
            json_manifest = Manifest.model_validate_json(tgz.extractfile("info.json").read())
        self.assertEqual(json_manifest, manifest)

    def test_ruleset_discovery_and_forms(self):
        module = importlib.import_module(
            "cmk_addons.plugins.apc_pdu_ext_sensors.rulesets.apc_rackpdu_ext_env"
        )
        found = _discovered(module, rs_prefixes())
        self.assertEqual(
            list(found),
            [
                "rule_spec_apc_rackpdu_ext_env_discovery",
                "rule_spec_apc_rackpdu_ext_env",
            ],
        )
        discovery = found["rule_spec_apc_rackpdu_ext_env_discovery"]
        self.assertEqual(discovery.name, "apc_rackpdu_ext_env_discovery")
        self.assertEqual(set(discovery.parameter_form().elements), {"names"})
        entry = discovery.parameter_form().elements["names"].parameter_form.element_template
        self.assertEqual(set(entry.elements), {"number", "name"})

        check = found["rule_spec_apc_rackpdu_ext_env"]
        self.assertEqual(check.name, "apc_rackpdu_ext_env")
        self.assertFalse(check.create_enforced_service)
        form = check.parameter_form()
        self.assertEqual(
            set(form.elements),
            {
                "temp_levels_upper",
                "temp_levels_lower",
                "temp_factor",
                "humidity_levels_upper",
                "humidity_levels_lower",
                "humidity_factor",
                "sensor_index",
                "sensor_number",
            },
        )
        self.assertEqual(form.elements["temp_factor"].parameter_form.prefill.value, 1.0)
        self.assertEqual(form.elements["humidity_factor"].parameter_form.prefill.value, 1.0)
        self.assertTrue(form.elements["sensor_index"].render_only)
        upper = form.elements["temp_levels_upper"].parameter_form
        lower = form.elements["humidity_levels_lower"].parameter_form
        self.assertEqual(upper.prefill_fixed_levels.value, (30.0, 35.0))
        self.assertEqual(upper.prefill_levels_type.value, LevelsType.FIXED)
        self.assertEqual(lower.prefill_levels_type.value, LevelsType.NONE)
        self.assertEqual(
            form.elements["humidity_levels_upper"].parameter_form.prefill_fixed_levels.value,
            (70.0, 80.0),
        )
        self.assertEqual(check.condition.item_title.localize(lambda text: text), "Service item")

    def test_real_checkmk_discovery(self):
        for group, prefixes, expected in (
            (
                PluginGroup.AGENT_BASED,
                ab_prefixes(),
                [
                    "check_plugin_apc_rackpdu_ext_env",
                    "snmp_section_apc_rackpdu_ext_env",
                ],
            ),
            (
                PluginGroup.RULESETS,
                rs_prefixes(),
                [
                    "rule_spec_apc_rackpdu_ext_env",
                    "rule_spec_apc_rackpdu_ext_env_discovery",
                ],
            ),
            (PluginGroup.GRAPHING, graph_prefixes(), []),
        ):
            modules = [
                name
                for name in discover_modules(group, raise_errors=True)
                if ".apc_pdu_ext_sensors." in name or name.endswith(".apc_rackpdu_ext_env")
            ]
            # old module names must be gone; exactly the new module is loaded
            self.assertEqual(len(modules), 1, modules)
            discovered = discover_plugins_from_modules(prefixes, modules, raise_errors=True)
            self.assertEqual(discovered.errors, [])
            self.assertEqual(sorted(location.name for location in discovered.plugins), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
