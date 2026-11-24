#!/usr/bin/env python3
"""Parse, discovery and check tests with sample rPDU2 sensor rows.

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
    "apc_pdu_ext_sensors_agent",
    "src/apc_pdu_ext_sensors/agent_based/apc_pdu_ext_sensors.py",
)
graphing = _load(
    "apc_pdu_ext_sensors_graphing",
    "src/apc_pdu_ext_sensors/graphing/apc_pdu_ext_sensors.py",
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


# index, module, name, number, type, comm, tempC tenths, temp status, humidity %, humidity status
SAMPLE = [
    _row(1, 1, "Inlet", 1, 2, 2, 243, 4, 45, 4),  # temp + humidity, normal
    _row(2, 1, "Outlet", 2, 1, 2, 301, 5, 0, 1),  # temperature only, humidity not present
    _row(3, 1, "", 3, 4, 1, 0, 1, 0, 1),  # not installed
    _row(4, 1, "Lost", 4, 3, 3, 0, 1, 0, 1),  # communication lost
    _row(5, 1, "Inlet", 5, 2, 2, 180, 4, 55, 4),  # same PDU name as sensor 1
]


class ParseDiscoverCheckTest(unittest.TestCase):
    def setUp(self):
        self.section = agent.parse_apc_pdu_ext_sensors(SAMPLE)
        self.assertIsNotNone(self.section)

    def test_parse_keeps_absent_rows_and_scales_later(self):
        self.assertEqual(set(self.section), {"1", "2", "3", "4", "5"})
        inlet = self.section["1"]
        self.assertEqual(inlet.name, "Inlet")
        self.assertEqual(inlet.temp_raw, 243)
        self.assertEqual(inlet.humidity_raw, 45)
        self.assertIsNone(agent.parse_apc_pdu_ext_sensors([]))
        self.assertIsNone(agent.parse_apc_pdu_ext_sensors([["", "", ""]]))

    def test_wrapped_section_parse_unpacks_one_table(self):
        parsed = agent.snmp_section_apc_pdu_ext_sensors.parse_function([SAMPLE])
        self.assertEqual(set(parsed), set(self.section))

    def test_discovery_skips_absent_and_splits_metrics(self):
        params = agent.DISCOVERY_DEFAULT_PARAMETERS
        temp = list(agent.discover_apc_pdu_ext_temp(params, self.section))
        humidity = list(agent.discover_apc_pdu_ext_humidity(params, self.section))
        self.assertEqual(
            [(service.item, service.parameters) for service in temp],
            [
                ("Inlet [1]", {"sensor_index": "1"}),
                ("Outlet", {"sensor_index": "2"}),
                ("Inlet [5]", {"sensor_index": "5"}),
            ],
        )
        self.assertEqual(
            [(service.item, service.parameters) for service in humidity],
            [
                ("Inlet [1]", {"sensor_index": "1"}),
                ("Inlet [5]", {"sensor_index": "5"}),
            ],
        )

    def test_alias_renames_item_for_both_metrics(self):
        params = {"aliases": [{"match": "1", "name": "Hugo's inlet"}, {"match": "Outlet", "name": "Warm aisle"}]}
        temp = {service.item: service.parameters for service in agent.discover_apc_pdu_ext_temp(params, self.section)}
        humidity = {service.item for service in agent.discover_apc_pdu_ext_humidity(params, self.section)}
        self.assertEqual(temp["Hugo's inlet"], {"sensor_index": "1"})
        self.assertIn("Warm aisle", temp)
        self.assertIn("Hugo's inlet", humidity)
        self.assertNotIn("Warm aisle", humidity)

    def test_alias_matches_sensor_number_and_default_item(self):
        unnamed = agent.parse_apc_pdu_ext_sensors([
            _row(7, 2, "", 9, 2, 2, 200, 4, 40, 4),
        ])
        params = {"aliases": [{"match": "Sensor 7", "name": "Cold aisle"}]}
        (service,) = agent.discover_apc_pdu_ext_temp(params, unnamed)
        self.assertEqual(service.item, "Cold aisle")
        params = {"aliases": [{"match": "9", "name": "By number"}]}
        (service,) = agent.discover_apc_pdu_ext_humidity(params, unnamed)
        self.assertEqual(service.item, "By number")

    def test_temperature_scale_factor_and_levels(self):
        params = {
            **agent.TEMP_DEFAULT_PARAMETERS,
            "sensor_index": "2",
            "factor": 1.0,
        }
        results = list(agent.check_apc_pdu_ext_temp("Outlet", params, self.section))
        summary = next(item for item in results if isinstance(item, Result) and item.summary)
        metric = next(item for item in results if isinstance(item, Metric))
        # 301 tenths × 0.1 × 1.0 = 30.1 °C, warn/crit at 30/35 → WARN
        self.assertEqual(summary.state, State.WARN)
        self.assertIn("Outlet: 30.1 °C", summary.summary)
        self.assertEqual(metric.name, "temp")
        self.assertAlmostEqual(metric.value, 30.1)
        self.assertEqual(metric.levels, (30.0, 35.0))

        whole_degrees = {
            **agent.TEMP_DEFAULT_PARAMETERS,
            "sensor_index": "2",
            "factor": 10.0,
            "levels_upper": ("no_levels", None),
        }
        # firmware that returns 301 meaning 301 °C is out of scope; a raw 25 with factor 10:
        section = agent.parse_apc_pdu_ext_sensors([
            _row(2, 1, "Outlet", 2, 1, 2, 25, 4, 0, 1),
        ])
        metric = next(
            item
            for item in agent.check_apc_pdu_ext_temp("Outlet", whole_degrees, section)
            if isinstance(item, Metric)
        )
        self.assertAlmostEqual(metric.value, 25.0)

    def test_humidity_scale_and_lower_levels(self):
        params = {
            "levels_upper": ("fixed", (70.0, 80.0)),
            "levels_lower": ("fixed", (30.0, 20.0)),
            "factor": 1.0,
            "sensor_index": "1",
        }
        summary, metric = _summary_and_metric(
            agent.check_apc_pdu_ext_humidity("Hugo's inlet", params, self.section)
        )
        self.assertEqual(summary.state, State.OK)
        self.assertEqual(summary.summary, "Hugo's inlet: 45.0%")
        self.assertEqual(metric.name, "humidity")
        self.assertAlmostEqual(metric.value, 45.0)
        self.assertEqual(metric.boundaries, (0.0, 100.0))

        tenths = {
            **params,
            "factor": 0.1,
            "sensor_index": "1",
        }
        section = agent.parse_apc_pdu_ext_sensors([
            _row(1, 1, "Inlet", 1, 2, 2, 243, 4, 450, 4),
        ])
        metric = _summary_and_metric(agent.check_apc_pdu_ext_humidity("Inlet", tenths, section))[1]
        self.assertAlmostEqual(metric.value, 45.0)

        low = {**params, "sensor_index": "5"}
        summary = _summary_and_metric(
            agent.check_apc_pdu_ext_humidity("Inlet [5]", low, self.section)
        )[0]
        # 55% is inside 30..70
        self.assertEqual(summary.state, State.OK)

        colder = agent.parse_apc_pdu_ext_sensors([
            _row(1, 1, "Inlet", 1, 2, 2, 100, 3, 15, 2),
        ])
        summary = _summary_and_metric(
            agent.check_apc_pdu_ext_humidity("Inlet", params, colder)
        )[0]
        self.assertEqual(summary.state, State.CRIT)
        self.assertIn("warn/crit below", summary.summary)

    def test_upper_level_is_reached_at_the_threshold(self):
        params = {
            **agent.TEMP_DEFAULT_PARAMETERS,
            "sensor_index": "1",
            "levels_upper": ("fixed", (24.3, 40.0)),
        }
        summary = _summary_and_metric(
            agent.check_apc_pdu_ext_temp("Inlet [1]", params, self.section)
        )[0]
        self.assertEqual(summary.state, State.WARN)

    def test_lost_sensor_is_critical_and_missing_sensor_is_unknown(self):
        params = {**agent.TEMP_DEFAULT_PARAMETERS, "sensor_index": "4"}
        (result,) = [
            item
            for item in agent.check_apc_pdu_ext_temp("Lost", params, self.section)
            if isinstance(item, Result) and item.summary
        ]
        self.assertEqual(result.state, State.CRIT)
        self.assertIn("communication lost", result.summary)

        params = {**agent.TEMP_DEFAULT_PARAMETERS, "sensor_index": "99"}
        (result,) = [
            item
            for item in agent.check_apc_pdu_ext_temp("Gone", params, self.section)
            if isinstance(item, Result)
        ]
        self.assertEqual(result.state, State.UNKNOWN)
        self.assertIn("disappeared", result.summary)

    def test_detect_targets_apc_pdus_and_the_status_columns(self):
        detect = agent.snmp_section_apc_pdu_ext_sensors.detect
        clauses = [tuple(clause) for clause in detect]
        self.assertIn(
            (".1.3.6.1.2.1.1.2.0", r"\.1\.3\.6\.1\.4\.1\.318\.1\.3\.4\.5.*", True),
            clauses[0],
        )
        patterns = [pattern for clause in clauses for _oid, pattern, _expected in clause]
        self.assertTrue(any("rPDU" in pattern for pattern in patterns))
        self.assertTrue(any("rack[- ]pdu" in pattern for pattern in patterns))
        tree = agent.snmp_section_apc_pdu_ext_sensors.fetch[0]
        self.assertEqual(tree.base, ".1.3.6.1.4.1.318.1.1.26.10.2.2.1")
        columns = [getattr(oid, "column", None) for oid in tree.oids]
        self.assertIn("8", columns)
        self.assertIn("10", columns)

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
