#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""SNMP checks for external temperature and humidity sensors on APC rack PDUs.

PowerNet-MIB table rPDU2SensorTempHumidityStatusTable
(.1.3.6.1.4.1.318.1.1.26.10.2.2). One service is created per sensor per
metric (Temperature and Humidity) so names and thresholds stay independent.

Temperature (rPDU2SensorTempHumidityStatusTempC) is defined as tenths of a
degree Celsius. Humidity (rPDU2SensorTempHumidityStatusRelativeHumidity) is
already percent. The configurable factor is applied after that MIB conversion:

    value = raw * mib_scale * factor

with mib_scale 0.1 for temperature and 1 for humidity, and factor 1.0 by default.
"""

from collections.abc import Iterable, Mapping, Sequence
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

SECTION_NAME = "apc_pdu_ext_sensors"
DISCOVERY_RULESET = "apc_pdu_ext_sensors"
TEMP_RULESET = "apc_pdu_ext_temp"
HUMIDITY_RULESET = "apc_pdu_ext_humidity"

# products.hardware.rPDU2.rPDU2Sensor.rPDU2SensorTempHumidity.rPDU2SensorTempHumidityStatusTable
_STATUS_TABLE = ".1.3.6.1.4.1.318.1.1.26.10.2.2.1"
_SYS_OBJECT_ID = ".1.3.6.1.2.1.1.2.0"
_SYS_DESCR = ".1.3.6.1.2.1.1.1.0"
# enterprises.apc, and products.system id used by rPDU2 (NUT: APC_PDU_MIB_SYSOID_RPDU2)
_APC_ENTERPRISE = ".1.3.6.1.4.1.318"
_RPDU2_SYS_OBJECT = ".1.3.6.1.4.1.318.1.3.4.5"

# rPDU2SensorTempHumidityStatusType
TYPE_TEMPERATURE_ONLY = 1
TYPE_TEMPERATURE_HUMIDITY = 2
TYPE_COMMS_LOST = 3
TYPE_NOT_INSTALLED = 4

# rPDU2SensorTempHumidityStatusCommStatus
COMM_NOT_INSTALLED = 1
COMM_OK = 2
COMM_LOST = 3

# rPDU2SensorTempHumidityStatusTempStatus / HumidityStatus
STATUS_NOT_PRESENT = 1

TEMP_MIB_SCALE = 0.1  # tenths of °C, per the MIB description
HUMIDITY_MIB_SCALE = 1.0  # percent relative humidity

TEMP_DEFAULT_PARAMETERS: dict[str, object] = {
    "levels_upper": ("fixed", (30.0, 35.0)),
    "levels_lower": ("no_levels", None),
    "factor": 1.0,
}
HUMIDITY_DEFAULT_PARAMETERS: dict[str, object] = {
    "levels_upper": ("fixed", (70.0, 80.0)),
    "levels_lower": ("no_levels", None),
    "factor": 1.0,
}
DISCOVERY_DEFAULT_PARAMETERS: dict[str, object] = {"aliases": []}

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


def parse_apc_pdu_ext_sensors(string_table: StringTable) -> Section | None:
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


def _aliases(params: Mapping[str, object]) -> list[tuple[str, str]]:
    raw = _param(params, "aliases", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    found: list[tuple[str, str]] = []
    for entry in raw:
        if not isinstance(entry, Mapping):
            continue
        match = str(entry.get("match", "")).strip()
        name = str(entry.get("name", "")).strip()
        if match and name:
            found.append((match, name))
    return found


def default_item(sensor: Sensor) -> str:
    return sensor.name or f"Sensor {sensor.index}"


def _match_keys(sensor: Sensor) -> set[str]:
    return {key for key in (sensor.index, sensor.number, sensor.name, default_item(sensor)) if key}


def item_names(sensors: Iterable[Sensor], params: Mapping[str, object]) -> dict[str, str]:
    """Map a sensor index to a unique service item.

    An alias matches the SNMP index, the sensor number, the PDU name, or the
    default item. The first alias wins. Identical results are suffixed with the
    index so two sensors cannot share one item.
    """
    aliases = _aliases(params)
    chosen: dict[str, str] = {}
    for sensor in sensors:
        keys = _match_keys(sensor)
        item = default_item(sensor)
        for match, name in aliases:
            if match in keys:
                item = name
                break
        chosen[sensor.index] = item

    counts: dict[str, int] = {}
    for item in chosen.values():
        counts[item] = counts.get(item, 0) + 1
    return {
        index: item if counts[item] == 1 else f"{item} [{index}]"
        for index, item in chosen.items()
    }


def _is_absent(sensor: Sensor) -> bool:
    return (
        sensor.comm_status == COMM_NOT_INSTALLED or sensor.sensor_type == TYPE_NOT_INSTALLED
    )


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


def scaled_value(raw: int, mib_scale: float, factor: float) -> float:
    return raw * mib_scale * factor


def _factor(params: Mapping[str, object]) -> float:
    raw = _param(params, "factor", 1.0)
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


def _find_sensor(item: str, params: Mapping[str, object], section: Section) -> Sensor | None:
    index = _param(params, "sensor_index")
    if isinstance(index, str) and index in section:
        return section[index]
    for sensor in section.values():
        if item in (default_item(sensor), sensor.index, sensor.number, sensor.name):
            return sensor
    if item.endswith("]") and " [" in item:
        suffix = item.rsplit(" [", 1)[1][:-1]
        return section.get(suffix)
    return None


def _unavailable_reason(sensor: Sensor) -> str:
    if sensor.comm_status in _COMM_STATUS and sensor.comm_status != COMM_OK:
        return _COMM_STATUS[sensor.comm_status]
    if sensor.sensor_type == TYPE_NOT_INSTALLED:
        return "not installed"
    if sensor.sensor_type == TYPE_COMMS_LOST or sensor.comm_status == COMM_LOST:
        return "communication lost"
    return "unavailable"


def _discover(params: Mapping[str, object], section: Section, *, kind: str) -> DiscoveryResult:
    present = [sensor for sensor in section.values() if _monitorable(sensor)]
    names = item_names(present, params)
    wanted = has_temperature if kind == "temp" else has_humidity
    for sensor in present:
        if not wanted(sensor):
            continue
        yield Service(item=names[sensor.index], parameters={"sensor_index": sensor.index})


def discover_apc_pdu_ext_temp(
    params: Mapping[str, object], section: Section
) -> DiscoveryResult:
    yield from _discover(params, section, kind="temp")


def discover_apc_pdu_ext_humidity(
    params: Mapping[str, object], section: Section
) -> DiscoveryResult:
    yield from _discover(params, section, kind="humidity")


def _render_temp(value: float) -> str:
    return f"{value:.1f} °C"


def _render_humidity(value: float) -> str:
    return f"{value:.1f}%"


def _check(
    item: str,
    params: Mapping[str, object],
    section: Section,
    *,
    kind: str,
) -> CheckResult:
    sensor = _find_sensor(item, params, section)
    if sensor is None:
        yield Result(state=State.UNKNOWN, summary=f"{item}: sensor disappeared from the SNMP table")
        return
    if not _monitorable(sensor):
        yield Result(
            state=State.CRIT,
            summary=f"{item}: sensor unavailable ({_unavailable_reason(sensor)})",
        )
        return

    if kind == "temp":
        raw, status, scale, metric = (
            sensor.temp_raw,
            sensor.temp_status,
            TEMP_MIB_SCALE,
            "temp",
        )
        render = _render_temp
        boundaries = (None, None)
        missing = "temperature reading is not present"
    else:
        raw, status, scale, metric = (
            sensor.humidity_raw,
            sensor.humidity_status,
            HUMIDITY_MIB_SCALE,
            "humidity",
        )
        render = _render_humidity
        boundaries = None  # set from the scaled value below
        missing = "humidity reading is not present"

    if not _reading_present(raw, status) or raw is None:
        yield Result(state=State.UNKNOWN, summary=f"{item}: {missing}")
        return

    factor = _factor(params)
    value = scaled_value(raw, scale, factor)
    if kind != "temp":
        boundaries = (0.0, 100.0) if 0.0 <= value <= 100.0 else (0.0, None)
    yield from check_levels(
        value,
        levels_upper=_levels(_param(params, "levels_upper")),  # type: ignore[arg-type]
        levels_lower=_levels(_param(params, "levels_lower")),  # type: ignore[arg-type]
        metric_name=metric,
        render_func=render,
        label=item,
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


def check_apc_pdu_ext_temp(
    item: str, params: Mapping[str, object], section: Section
) -> CheckResult:
    yield from _check(item, params, section, kind="temp")


def check_apc_pdu_ext_humidity(
    item: str, params: Mapping[str, object], section: Section
) -> CheckResult:
    yield from _check(item, params, section, kind="humidity")


# APC enterprise sysObjectID, narrowed to rack PDUs: the rPDU2 system id, or any
# APC device whose sysDescr identifies an rPDU / rack PDU. UPSs stay out.
snmp_section_apc_pdu_ext_sensors = SimpleSNMPSection(
    name=SECTION_NAME,
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
            OIDEnd(),  # index (rPDU2SensorTempHumidityStatusIndex)
            "2",  # rPDU2SensorTempHumidityStatusModule
            "3",  # rPDU2SensorTempHumidityStatusName
            "4",  # rPDU2SensorTempHumidityStatusNumber
            "5",  # rPDU2SensorTempHumidityStatusType
            "6",  # rPDU2SensorTempHumidityStatusCommStatus
            "8",  # rPDU2SensorTempHumidityStatusTempC (tenths of °C)
            "9",  # rPDU2SensorTempHumidityStatusTempStatus
            "10",  # rPDU2SensorTempHumidityStatusRelativeHumidity (percent)
            "11",  # rPDU2SensorTempHumidityStatusHumidityStatus
        ],
    ),
    parse_function=parse_apc_pdu_ext_sensors,
)

check_plugin_apc_pdu_ext_temp = CheckPlugin(
    name=TEMP_RULESET,
    sections=[SECTION_NAME],
    service_name="Temperature %s",
    discovery_function=discover_apc_pdu_ext_temp,
    discovery_default_parameters=DISCOVERY_DEFAULT_PARAMETERS,
    discovery_ruleset_name=DISCOVERY_RULESET,
    check_function=check_apc_pdu_ext_temp,
    check_default_parameters=TEMP_DEFAULT_PARAMETERS,
    check_ruleset_name=TEMP_RULESET,
)

check_plugin_apc_pdu_ext_humidity = CheckPlugin(
    name=HUMIDITY_RULESET,
    sections=[SECTION_NAME],
    service_name="Humidity %s",
    discovery_function=discover_apc_pdu_ext_humidity,
    discovery_default_parameters=DISCOVERY_DEFAULT_PARAMETERS,
    discovery_ruleset_name=DISCOVERY_RULESET,
    check_function=check_apc_pdu_ext_humidity,
    check_default_parameters=HUMIDITY_DEFAULT_PARAMETERS,
    check_ruleset_name=HUMIDITY_RULESET,
)
