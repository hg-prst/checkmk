#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""One SNMP check for external temperature and humidity sensors on APC rack PDUs.

Check plugin name: apc_rackpdu_ext_env. Temperature and humidity are separate
services of that single plugin. The service item is the full description, so
Checkmk shows one check name for both:

    Temperature Ext Sensor #1
    Humidity Ext Sensor #1

Numbers follow the SNMP index order of sensors that are actually present.
A discovery rule can replace "Ext Sensor #N" with a chosen label. The summary
is always "Current: <value>".
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cmk.agent_based.v2 import (
    CheckPlugin,
    CheckResult,
    DiscoveryResult,
    OIDEnd,
    Result,
    Service,
    SimpleSNMPSection,
    SNMPTree,
    State,
    StringTable,
    all_of,
    any_of,
    check_levels,
    matches,
    startswith,
)

CHECK_NAME = "apc_rackpdu_ext_env"
DISCOVERY_RULESET = "apc_rackpdu_ext_env_discovery"

_STATUS_TABLE = ".1.3.6.1.4.1.318.1.1.26.10.2.2.1"
_SYS_OBJECT_ID = ".1.3.6.1.2.1.1.2.0"
_SYS_DESCR = ".1.3.6.1.2.1.1.1.0"
_APC_ENTERPRISE = ".1.3.6.1.4.1.318"
_RPDU2_SYS_OBJECT = ".1.3.6.1.4.1.318.1.3.4.5"

TYPE_TEMPERATURE_ONLY = 1
TYPE_TEMPERATURE_HUMIDITY = 2
TYPE_COMMS_LOST = 3
TYPE_NOT_INSTALLED = 4

COMM_NOT_INSTALLED = 1
COMM_OK = 2
COMM_LOST = 3

STATUS_NOT_PRESENT = 1

TEMP_MIB_SCALE = 0.1
HUMIDITY_MIB_SCALE = 1.0

CHECK_DEFAULT_PARAMETERS: dict[str, object] = {
    "temp_levels_upper": ("fixed", (30.0, 35.0)),
    "temp_levels_lower": ("no_levels", None),
    "temp_factor": 1.0,
    "humidity_levels_upper": ("fixed", (70.0, 80.0)),
    "humidity_levels_lower": ("no_levels", None),
    "humidity_factor": 1.0,
}
DISCOVERY_DEFAULT_PARAMETERS: dict[str, object] = {"names": []}

_PROBE_STATUS = {
    1: "not present",
    2: "below minimum",
    3: "below low",
    4: "normal",
    5: "above high",
    6: "above maximum",
}
_COMM_STATUS = {
    COMM_NOT_INSTALLED: "not installed",
    COMM_OK: "ok",
    COMM_LOST: "communication lost",
}
_DEFAULT_ITEM = re.compile(r"^(Temperature|Humidity) Ext Sensor #(\d+)$")


@dataclass(frozen=True)
class Sensor:
    index: str
    module: str
    name: str
    number: str
    sensor_type: int | None
    comm_status: int | None
    temp_raw: int | None
    temp_status: int | None
    humidity_raw: int | None
    humidity_status: int | None


Section = dict[str, Sensor]


def _parse_int(value: object) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_apc_rackpdu_ext_env(string_table: StringTable) -> Section | None:
    sensors: Section = {}
    for row in string_table:
        cells = [str(cell).strip() for cell in row]
        cells += [""] * (10 - len(cells))
        index = cells[0].lstrip(".")
        if not index:
            continue
        sensors[index] = Sensor(
            index=index,
            module=cells[1],
            name=cells[2],
            number=cells[3],
            sensor_type=_parse_int(cells[4]),
            comm_status=_parse_int(cells[5]),
            temp_raw=_parse_int(cells[6]),
            temp_status=_parse_int(cells[7]),
            humidity_raw=_parse_int(cells[8]),
            humidity_status=_parse_int(cells[9]),
        )
    return sensors or None


def _param(params: Mapping[str, object], key: str, default: object = None) -> object:
    if key in params:
        return params[key]
    return default


def _index_key(sensor: Sensor) -> tuple[int, int | str]:
    try:
        return (0, int(sensor.index))
    except ValueError:
        return (1, sensor.index)


def _is_absent(sensor: Sensor) -> bool:
    return sensor.comm_status == COMM_NOT_INSTALLED or sensor.sensor_type == TYPE_NOT_INSTALLED


def _is_unavailable(sensor: Sensor) -> bool:
    return sensor.comm_status == COMM_LOST or sensor.sensor_type == TYPE_COMMS_LOST


def _monitorable(sensor: Sensor) -> bool:
    return sensor.comm_status == COMM_OK and not _is_absent(sensor) and not _is_unavailable(sensor)


def _reading_present(raw: int | None, status: int | None) -> bool:
    return raw is not None and status != STATUS_NOT_PRESENT


def has_temperature(sensor: Sensor) -> bool:
    return (
        _monitorable(sensor)
        and sensor.sensor_type in (TYPE_TEMPERATURE_ONLY, TYPE_TEMPERATURE_HUMIDITY)
        and _reading_present(sensor.temp_raw, sensor.temp_status)
    )


def has_humidity(sensor: Sensor) -> bool:
    return (
        _monitorable(sensor)
        and sensor.sensor_type == TYPE_TEMPERATURE_HUMIDITY
        and _reading_present(sensor.humidity_raw, sensor.humidity_status)
    )


def present_sensors(section: Section) -> list[tuple[int, Sensor]]:
    """Sensors that produce a service, numbered 1..N in SNMP index order."""
    sensors = [sensor for sensor in section.values() if has_temperature(sensor) or has_humidity(sensor)]
    sensors.sort(key=_index_key)
    return list(enumerate(sensors, start=1))


def custom_names(params: Mapping[str, object]) -> dict[int, str]:
    raw = _param(params, "names", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return {}
    found: dict[int, str] = {}
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        number = _parse_int(entry.get("number"))
        name = str(entry.get("name", "")).strip()
        if number is None or number < 1 or not name or number in found:
            continue
        found[number] = name
    return found


def service_item(kind: str, number: int, names: Mapping[int, str]) -> str:
    prefix = "Temperature" if kind == "temp" else "Humidity"
    label = names.get(number) or f"Ext Sensor #{number}"
    return f"{prefix} {label}"


def scaled_value(raw: int, mib_scale: float, factor: float) -> float:
    return raw * mib_scale * factor


def _factor(params: Mapping[str, object], key: str) -> float:
    raw = _param(params, key, 1.0)
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1.0
    if value != value or value in (float("inf"), float("-inf")):
        return 1.0
    return value


def _levels(value: object) -> tuple[str, object] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    kind, payload = value
    if kind == "no_levels":
        return ("no_levels", None)
    if kind == "fixed" and isinstance(payload, (tuple, list)) and len(payload) == 2:
        try:
            return ("fixed", (float(payload[0]), float(payload[1])))
        except (TypeError, ValueError):
            return None
    return None


def _kind(item: str) -> str | None:
    if item.startswith("Temperature "):
        return "temp"
    if item.startswith("Humidity "):
        return "humidity"
    return None


def _find_sensor(item: str, params: Mapping[str, object], section: Section) -> Sensor | None:
    index = _param(params, "sensor_index")
    if isinstance(index, str) and index.strip() and index in section:
        return section[index]
    numbered = dict(present_sensors(section))
    match = _DEFAULT_ITEM.match(item)
    if match:
        return numbered.get(int(match.group(2)))
    number = _parse_int(_param(params, "sensor_number"))
    if number is not None:
        return numbered.get(number)
    return None


def _unavailable_reason(sensor: Sensor) -> str:
    if sensor.comm_status in _COMM_STATUS and sensor.comm_status != COMM_OK:
        return _COMM_STATUS[sensor.comm_status]
    if sensor.sensor_type == TYPE_NOT_INSTALLED:
        return "not installed"
    if sensor.sensor_type == TYPE_COMMS_LOST or sensor.comm_status == COMM_LOST:
        return "communication lost"
    return "unavailable"


def discover_apc_rackpdu_ext_env(
    params: Mapping[str, object], section: Section
) -> DiscoveryResult:
    names = custom_names(params)
    for number, sensor in present_sensors(section):
        discovered = {"sensor_index": sensor.index, "sensor_number": number}
        if has_temperature(sensor):
            yield Service(item=service_item("temp", number, names), parameters=discovered)
        if has_humidity(sensor):
            yield Service(item=service_item("humidity", number, names), parameters=discovered)


def _render_temp(value: float) -> str:
    return f"{value:.1f} °C"


def _render_humidity(value: float) -> str:
    return f"{value:.1f}%"


def check_apc_rackpdu_ext_env(
    item: str, params: Mapping[str, object], section: Section
) -> CheckResult:
    kind = _kind(item)
    if kind is None:
        yield Result(state=State.UNKNOWN, summary=f"Unknown service item {item!r}")
        return
    sensor = _find_sensor(item, params, section)
    if sensor is None:
        yield Result(state=State.UNKNOWN, summary="Current: sensor disappeared from the SNMP table")
        return
    if not _monitorable(sensor):
        yield Result(
            state=State.CRIT,
            summary=f"Current: sensor unavailable ({_unavailable_reason(sensor)})",
        )
        return

    if kind == "temp":
        raw, status, scale, metric, factor_key = (
            sensor.temp_raw,
            sensor.temp_status,
            TEMP_MIB_SCALE,
            "temp",
            "temp_factor",
        )
        levels_upper, levels_lower = "temp_levels_upper", "temp_levels_lower"
        render = _render_temp
        boundaries: tuple[float | None, float | None] | None = (None, None)
        missing = "temperature reading is not present"
    else:
        raw, status, scale, metric, factor_key = (
            sensor.humidity_raw,
            sensor.humidity_status,
            HUMIDITY_MIB_SCALE,
            "humidity",
            "humidity_factor",
        )
        levels_upper, levels_lower = "humidity_levels_upper", "humidity_levels_lower"
        render = _render_humidity
        boundaries = None
        missing = "humidity reading is not present"

    if not _reading_present(raw, status) or raw is None:
        yield Result(state=State.UNKNOWN, summary=f"Current: {missing}")
        return

    factor = _factor(params, factor_key)
    value = scaled_value(raw, scale, factor)
    if kind != "temp":
        boundaries = (0.0, 100.0) if 0.0 <= value <= 100.0 else (0.0, None)
    yield from check_levels(
        value,
        levels_upper=_levels(_param(params, levels_upper)),  # type: ignore[arg-type]
        levels_lower=_levels(_param(params, levels_lower)),  # type: ignore[arg-type]
        metric_name=metric,
        render_func=render,
        label="Current",
        boundaries=boundaries,
    )
    device_status = _PROBE_STATUS.get(status, "unknown") if status is not None else "not reported"
    snmp_name = sensor.name or "-"
    yield Result(
        state=State.OK,
        notice=(
            f"SNMP index {sensor.index}, name {snmp_name!r}, module {sensor.module or '-'}, "
            f"raw {raw}, MIB scale {scale:g}, factor {factor:g}, device status {device_status}"
        ),
    )


snmp_section_apc_rackpdu_ext_env = SimpleSNMPSection(
    name=CHECK_NAME,
    detect=any_of(
        startswith(_SYS_OBJECT_ID, _RPDU2_SYS_OBJECT),
        all_of(
            startswith(_SYS_OBJECT_ID, _APC_ENTERPRISE),
            any_of(
                matches(_SYS_DESCR, "(?i).*rPDU.*"),
                matches(_SYS_DESCR, "(?i).*rack[- ]pdu.*"),
            ),
        ),
    ),
    fetch=SNMPTree(
        base=_STATUS_TABLE,
        oids=[
            OIDEnd(),
            "2",  # module
            "3",  # name
            "4",  # sensor number on the PDU
            "5",  # type
            "6",  # comm status
            "8",  # temperature, tenths of °C
            "9",  # temperature status
            "10",  # humidity, percent
            "11",  # humidity status
        ],
    ),
    parse_function=parse_apc_rackpdu_ext_env,
)

check_plugin_apc_rackpdu_ext_env = CheckPlugin(
    name=CHECK_NAME,
    sections=[CHECK_NAME],
    service_name="%s",
    discovery_function=discover_apc_rackpdu_ext_env,
    discovery_default_parameters=DISCOVERY_DEFAULT_PARAMETERS,
    discovery_ruleset_name=DISCOVERY_RULESET,
    check_function=check_apc_rackpdu_ext_env,
    check_default_parameters=CHECK_DEFAULT_PARAMETERS,
    check_ruleset_name=CHECK_NAME,
)
