#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""Graphing notes for the APC PDU external sensor checks.

The checks publish Checkmk's builtin metrics ``temp`` (°C) and ``humidity`` (%).
Those already have a unit, a color, a graph and a perfometer.

Do not register ``metric_`` / ``graph_`` / ``perfometer_`` objects for those names
from this package:

* an API metric replaces the builtin metric of the same name for the whole site
* an API perfometer is tried before the builtin perfometer, so a perfometer on
  ``temp`` alone would become the perfometer of every temperature service
* an extra graph that only contains ``temp`` is shown on every temperature service

The objects below document the units the builtin metrics already provide. Their
Python names deliberately do not use the discovery prefixes.
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
    name="apc_pdu_ext_temperature",
    title=Title("Temperature"),
    minimal_range=MinimalRange(-10, 50),
    compound_lines=["temp"],
)

HUMIDITY_GRAPH = Graph(
    name="apc_pdu_ext_humidity",
    title=Title("Relative humidity"),
    minimal_range=MinimalRange(0, 100),
    compound_lines=["humidity"],
)

TEMPERATURE_PERFOMETER = Perfometer(
    name="apc_pdu_ext_temperature",
    focus_range=FocusRange(Open(-10), Open(50)),
    segments=["temp"],
)

HUMIDITY_PERFOMETER = Perfometer(
    name="apc_pdu_ext_humidity",
    focus_range=FocusRange(Closed(0), Closed(100)),
    segments=["humidity"],
)
