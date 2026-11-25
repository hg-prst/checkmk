#!/usr/bin/env python3
"""Parse, discovery and check tests for apc_rackpdu_ext_env.

Needs the Checkmk 2.4 plugin API (a source checkout is enough):

    git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
    pip install pydantic
    python3 tests/test_apc_pdu_ext_sensors.py
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMK_SRC = Path(os.environ.get("CMK_SRC", "/tmp/cmk"))
for pkg in ("cmk-agent-based", "cmk-rulesets", "cmk-graphing"):
    sys.path.insert(0, str(CMK_SRC / "packages" / pkg))
sys.path.append(str(CMK_SRC))


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent = _load(
    "apc_rackpdu_ext_env_agent",
    "src/apc_pdu_ext_sensors/agent_based/apc_rackpdu_ext_env.py",
)
graphing = _load(
    "apc_rackpdu_ext_env_graphing",
    "src/apc_pdu_ext_sensors/graphing/apc_rackpdu_ext_env.py",
)

from cmk.agent_based.v2 import Metric, Result, State  # noqa: E402


def _row(index, module, name, number, sensor_type, comm, temp, temp_status, humidity, humidity_status):
    return [
        str(index),
        str(module),
        name,
        str(number),
        str(sensor_type),
        str(comm),
        str(temp),
        str(temp_status),
        str(humidity),
        str(humidity_status),
    ]


# SNMP indexes 1, 2, 5 are present. 3 is not installed, 4 has lost communication.
# Display numbers follow index order: #1, #2, #3.
SAMPLE = [
    _row(5, 1, "Inlet", 5, 2, 2, 180, 4, 55, 4),
    _row(1, 1, "Inlet", 1, 2, 2, 243, 4, 45, 4),
    _row(2, 1, "Outlet", 2, 1, 2, 301, 5, 0, 1),
    _row(3, 1, "", 3, 4, 1, 0, 1, 0, 1),
    _row(4, 1, "Lost", 4, 3, 3, 0, 1, 0, 1),
]


class ParseDiscoverCheckTest(unittest.TestCase):
    def setUp(self):
        self.section = agent.parse_apc_rackpdu_ext_env(SAMPLE)
        self.assertIsNotNone(self.section)

    def test_parse_keeps_absent_rows(self):
        self.assertEqual(set(self.section), {"1", "2", "3", "4", "5"})
        self.assertIsNone(agent.parse_apc_rackpdu_ext_env([]))

    def test_wrapped_section_parse_unpacks_one_table(self):
        parsed = agent.snmp_section_apc_rackpdu_ext_env.parse_function([SAMPLE])
        self.assertEqual(set(parsed), set(self.section))

    def test_discovery_numbers_by_snmp_index_and_splits_metrics(self):
        services = list(agent.discover_apc_rackpdu_ext_env(agent.DISCOVERY_DEFAULT_PARAMETERS, self.section))
        self.assertEqual(
            [(service.item, service.parameters["sensor_index"], service.parameters["sensor_number"]) for service in services],
            [
                ("Temperature Ext Sensor #1", "1", 1),
                ("Humidity Ext Sensor #1", "1", 1),
                ("Temperature Ext Sensor #2", "2", 2),
                ("Temperature Ext Sensor #3", "5", 3),
                ("Humidity Ext Sensor #3", "5", 3),
            ],
        )

    def test_custom_name_replaces_ext_sensor_label(self):
        params = {"names": [{"number": 1, "name": "Hugo's inlet"}, {"number": 2, "name": "Warm aisle"}]}
        items = [service.item for service in agent.discover_apc_rackpdu_ext_env(params, self.section)]
        self.assertEqual(
            items,
            [
                "Temperature Hugo's inlet",
                "Humidity Hugo's inlet",
                "Temperature Warm aisle",
                "Temperature Ext Sensor #3",
                "Humidity Ext Sensor #3",
            ],
        )

    def test_first_name_for_a_number_wins_and_blank_names_are_ignored(self):
        params = {"names": [{"number": 1, "name": "First"}, {"number": 1, "name": "Second"}, {"number": 2, "name": "  "}]}
        items = [service.item for service in agent.discover_apc_rackpdu_ext_env(params, self.section)]
        self.assertEqual(items[0], "Temperature First")
        self.assertEqual(items[2], "Temperature Ext Sensor #2")

    def test_summary_is_current_and_scales_temperature(self):
        params = {**agent.CHECK_DEFAULT_PARAMETERS, "sensor_index": "2", "sensor_number": 2}
        summary, metric = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Temperature Ext Sensor #2", params, self.section)
        )
        # 301 tenths × 0.1 × 1.0 = 30.1 °C, warn/crit at 30/35 → WARN
        self.assertEqual(summary.state, State.WARN)
        self.assertTrue(summary.summary.startswith("Current: 30.1 °C"))
        self.assertIn("warn/crit at", summary.summary)
        self.assertEqual(metric.name, "temp")
        self.assertAlmostEqual(metric.value, 30.1)
        self.assertEqual(metric.levels, (30.0, 35.0))

        whole_degrees = {**params, "temp_factor": 10.0, "temp_levels_upper": ("no_levels", None)}
        section = agent.parse_apc_rackpdu_ext_env([
            _row(2, 1, "Outlet", 2, 1, 2, 25, 4, 0, 1),
        ])
        metric = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Temperature Ext Sensor #1", whole_degrees, section)
        )[1]
        self.assertAlmostEqual(metric.value, 25.0)

    def test_humidity_summary_factor_and_lower_levels(self):
        params = {
            **agent.CHECK_DEFAULT_PARAMETERS,
            "sensor_index": "1",
            "humidity_levels_lower": ("fixed", (30.0, 20.0)),
        }
        summary, metric = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Humidity Hugo's inlet", params, self.section)
        )
        self.assertEqual(summary.state, State.OK)
        self.assertEqual(summary.summary, "Current: 45.0%")
        self.assertEqual(metric.name, "humidity")
        self.assertAlmostEqual(metric.value, 45.0)
        self.assertEqual(metric.boundaries, (0.0, 100.0))

        tenths = {**params, "humidity_factor": 0.1, "sensor_index": "1"}
        section = agent.parse_apc_rackpdu_ext_env([
            _row(1, 1, "Inlet", 1, 2, 2, 243, 4, 450, 4),
        ])
        metric = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Humidity Ext Sensor #1", tenths, section)
        )[1]
        self.assertAlmostEqual(metric.value, 45.0)

        colder = agent.parse_apc_rackpdu_ext_env([
            _row(1, 1, "Inlet", 1, 2, 2, 100, 3, 15, 2),
        ])
        summary = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Humidity Ext Sensor #1", params, colder)
        )[0]
        self.assertEqual(summary.state, State.CRIT)
        self.assertTrue(summary.summary.startswith("Current: 15.0%"))
        self.assertIn("warn/crit below", summary.summary)

    def test_upper_level_is_reached_at_the_threshold(self):
        params = {
            **agent.CHECK_DEFAULT_PARAMETERS,
            "sensor_index": "1",
            "temp_levels_upper": ("fixed", (24.3, 40.0)),
        }
        summary = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env("Temperature Ext Sensor #1", params, self.section)
        )[0]
        self.assertEqual(summary.state, State.WARN)
        self.assertTrue(summary.summary.startswith("Current: 24.3 °C"))

    def test_lost_sensor_is_critical_and_missing_sensor_is_unknown(self):
        params = {**agent.CHECK_DEFAULT_PARAMETERS, "sensor_index": "4"}
        (result,) = [
            item
            for item in agent.check_apc_rackpdu_ext_env("Temperature Ext Sensor #9", params, self.section)
            if isinstance(item, Result) and item.summary
        ]
        self.assertEqual(result.state, State.CRIT)
        self.assertIn("communication lost", result.summary)
        self.assertTrue(result.summary.startswith("Current:"))

        params = {**agent.CHECK_DEFAULT_PARAMETERS, "sensor_index": "99"}
        (result,) = [
            item
            for item in agent.check_apc_rackpdu_ext_env("Temperature Ext Sensor #9", params, self.section)
            if isinstance(item, Result) and item.summary
        ]
        self.assertEqual(result.state, State.UNKNOWN)
        self.assertIn("disappeared", result.summary)

    def test_default_item_finds_sensor_without_discovered_index(self):
        summary, metric = _summary_and_metric(
            agent.check_apc_rackpdu_ext_env(
                "Humidity Ext Sensor #1", agent.CHECK_DEFAULT_PARAMETERS, self.section
            )
        )
        self.assertEqual(summary.summary, "Current: 45.0%")
        self.assertAlmostEqual(metric.value, 45.0)

    def test_detect_targets_apc_pdus_and_the_status_columns(self):
        detect = agent.snmp_section_apc_rackpdu_ext_env.detect
        clauses = [tuple(clause) for clause in detect]
        self.assertIn(
            (".1.3.6.1.2.1.1.2.0", r"\.1\.3\.6\.1\.4\.1\.318\.1\.3\.4\.5.*", True),
            clauses[0],
        )
        patterns = [pattern for clause in clauses for _oid, pattern, _expected in clause]
        self.assertTrue(any("rPDU" in pattern for pattern in patterns))
        tree = agent.snmp_section_apc_rackpdu_ext_env.fetch[0]
        self.assertEqual(tree.base, ".1.3.6.1.4.1.318.1.1.26.10.2.2.1")
        columns = [getattr(oid, "column", None) for oid in tree.oids]
        self.assertIn("8", columns)
        self.assertIn("10", columns)
        self.assertEqual(agent.check_plugin_apc_rackpdu_ext_env.name, "apc_rackpdu_ext_env")
        self.assertEqual(agent.check_plugin_apc_rackpdu_ext_env.service_name, "%s")

    def test_graphing_uses_builtin_metric_names_without_registering_them(self):
        self.assertEqual(graphing.TEMPERATURE_METRIC.name, "temp")
        self.assertEqual(graphing.TEMPERATURE_METRIC.unit.notation.symbol, "°C")
        self.assertEqual(graphing.HUMIDITY_METRIC.name, "humidity")
        self.assertEqual(graphing.HUMIDITY_METRIC.unit.notation.symbol, "%")
        registered = [
            name
            for name in vars(graphing)
            if name.startswith(("metric_", "graph_", "perfometer_"))
        ]
        self.assertEqual(registered, [])


def _summary_and_metric(items):
    results = list(items)
    summary = next(item for item in results if isinstance(item, Result) and item.summary)
    metric = next(item for item in results if isinstance(item, Metric))
    return summary, metric


if __name__ == "__main__":
    unittest.main(verbosity=2)
