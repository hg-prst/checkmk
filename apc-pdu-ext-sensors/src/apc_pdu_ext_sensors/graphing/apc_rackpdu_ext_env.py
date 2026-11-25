#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""Graphing notes for check apc_rackpdu_ext_env.

The check publishes Checkmk's builtin metrics ``temp`` (°C) and ``humidity`` (%).
Those already have a unit, a color, a graph and a perfometer.

Do not register ``metric_`` / ``graph_`` / ``perfometer_`` objects for those names
from this package. An API metric replaces the builtin metric site-wide, and an
API perfometer is tried before the builtin one for every service that has the
metric. The objects below only document the units. Their Python names do not
use the discovery prefixes.
"""

from cmk.graphing.v1 import Title
from cmk.graphing.v1.graphs import Graph, MinimalRange
from cmk.graphing.v1.metrics import Color, DecimalNotation, Metric, StrictPrecision, Unit
from cmk.graphing.v1.perfometers import Closed, FocusRange, Open, Perfometer

TEMPERATURE_METRIC = Metric(
    name="temp",
    title=Title("Temperature"),
    unit=Unit(DecimalNotation("°C"), StrictPrecision(1)),
    color=Color.ORANGE,
)

HUMIDITY_METRIC = Metric(
    name="humidity",
    title=Title("Humidity"),
    unit=Unit(DecimalNotation("%"), StrictPrecision(1)),
    color=Color.BLUE,
)

TEMPERATURE_GRAPH = Graph(
    name="apc_rackpdu_ext_env_temperature",
    title=Title("Temperature"),
    minimal_range=MinimalRange(-10, 50),
    compound_lines=["temp"],
)

HUMIDITY_GRAPH = Graph(
    name="apc_rackpdu_ext_env_humidity",
    title=Title("Relative humidity"),
    minimal_range=MinimalRange(0, 100),
    compound_lines=["humidity"],
)

TEMPERATURE_PERFOMETER = Perfometer(
    name="apc_rackpdu_ext_env_temperature",
    focus_range=FocusRange(Open(-10), Open(50)),
    segments=["temp"],
)

HUMIDITY_PERFOMETER = Perfometer(
    name="apc_rackpdu_ext_env_humidity",
    focus_range=FocusRange(Closed(0), Closed(100)),
    segments=["humidity"],
)
