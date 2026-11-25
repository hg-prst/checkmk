#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""Setup rules for APC PDU external temperature and humidity sensors.

Discovery rule (one per host, merged): optional aliases that become the service
item. Temperature and humidity then share that item, so a sensor called
"Hugo's inlet" is discovered as "Temperature Hugo's inlet" and
"Humidity Hugo's inlet".

Check rules (per metric, conditioned on the service item): upper and lower
warn/crit levels, and the multiplication factor applied after the MIB scale.
"""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    InputHint,
    LevelDirection,
    LevelsType,
    List,
    SimpleLevels,
    String,
    validators,
)
from cmk.rulesets.v1.rule_specs import CheckParameters, DiscoveryParameters, HostAndItemCondition, Topic


def _alias_entry() -> Dictionary:
    return Dictionary(
        title=Title("Sensor name"),
        elements={
            "match": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("Sensor"),
                    help_text=Help(
                        "Matches the SNMP index, the sensor number "
                        "(rPDU2SensorTempHumidityStatusNumber), the name configured on the PDU "
                        "(rPDU2SensorTempHumidityStatusName), or the default item "
                        "('Sensor <index>' when the PDU name is empty)."
                    ),
                    custom_validate=(validators.LengthInRange(min_value=1, max_value=64),),
                ),
            ),
            "name": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("Service item name"),
                    help_text=Help(
                        "Used as the service item. Services are named "
                        "'Temperature <name>' and 'Humidity <name>'. "
                        "Run service discovery again after changing a name; "
                        "threshold rules match this item."
                    ),
                    custom_validate=(validators.LengthInRange(min_value=1, max_value=64),),
                ),
            ),
        },
    )


def _discovery_form() -> Dictionary:
    return Dictionary(
        title=Title("APC PDU external sensor names"),
        help_text=Help(
            "Optional names for external temperature/humidity sensors on an APC rack PDU. "
            "Without a match, the service item is the name configured on the PDU, or "
            "'Sensor <index>' when that name is empty."
        ),
        elements={
            "aliases": DictElement(
                required=False,
                parameter_form=List(
                    title=Title("Sensor names"),
                    help_text=Help(
                        "The first matching entry wins. Put every sensor of a host in one rule; "
                        "when several rules match, Checkmk keeps the alias list of the most "
                        "specific rule."
                    ),
                    element_template=_alias_entry(),
                    add_element_label=Label("Add sensor name"),
                    remove_element_label=Label("Remove sensor name"),
                    no_element_label=Label("No custom sensor names"),
                ),
            ),
        },
    )


def _sensor_index() -> DictElement:
    return DictElement(
        required=False,
        render_only=True,
        parameter_form=String(
            title=Title("SNMP index"),
            help_text=Help(
                "Discovered row index in rPDU2SensorTempHumidityStatusTable. "
                "It keeps the service attached to the same sensor after the item is renamed."
            ),
            prefill=InputHint(""),
        ),
    )


def _factor(help_text: str) -> DictElement:
    return DictElement(
        required=True,
        parameter_form=Float(
            title=Title("Multiplication factor"),
            help_text=Help(help_text),
            prefill=DefaultValue(1.0),
        ),
    )


def _levels(
    title: str,
    direction: LevelDirection,
    prefill_type: LevelsType,
    fixed: tuple[float, float],
    unit: str,
) -> DictElement:
    return DictElement(
        required=True,
        parameter_form=SimpleLevels(
            title=Title(title),
            help_text=Help(
                "Warning and critical thresholds on the value after the MIB scale and the "
                "multiplication factor. The condition 'Sensor' is the service item "
                "(the PDU name or the name from the discovery rule)."
            ),
            form_spec_template=Float(unit_symbol=unit),
            level_direction=direction,
            prefill_levels_type=DefaultValue(prefill_type),
            prefill_fixed_levels=DefaultValue(fixed),
        ),
    )


def _temperature_form() -> Dictionary:
    return Dictionary(
        title=Title("APC PDU external temperature"),
        help_text=Help(
            "Upper and lower levels for one external APC PDU temperature sensor, "
            "and the factor applied to that sensor. "
            "Defaults without a rule: warn/crit at 30/35 °C, no lower levels, factor 1.0."
        ),
        elements={
            "levels_upper": _levels(
                "Upper temperature levels",
                LevelDirection.UPPER,
                LevelsType.FIXED,
                (30.0, 35.0),
                "°C",
            ),
            "levels_lower": _levels(
                "Lower temperature levels",
                LevelDirection.LOWER,
                LevelsType.NONE,
                (15.0, 10.0),
                "°C",
            ),
            "factor": _factor(
                "Applied after the MIB conversion, before levels and the metric: "
                "value = raw × 0.1 × factor. The MIB reports temperature in tenths of °C, "
                "so factor 1.0 turns 243 into 24.3 °C. Set the factor to 10 when this firmware "
                "already returns whole degrees (raw 25 with factor 10 is 25 °C)."
            ),
            "sensor_index": _sensor_index(),
        },
    )


def _humidity_form() -> Dictionary:
    return Dictionary(
        title=Title("APC PDU external humidity"),
        help_text=Help(
            "Upper and lower levels for one external APC PDU humidity sensor, "
            "and the factor applied to that sensor. "
            "Defaults without a rule: warn/crit at 70/80 %, no lower levels, factor 1.0."
        ),
        elements={
            "levels_upper": _levels(
                "Upper humidity levels",
                LevelDirection.UPPER,
                LevelsType.FIXED,
                (70.0, 80.0),
                "%",
            ),
            "levels_lower": _levels(
                "Lower humidity levels",
                LevelDirection.LOWER,
                LevelsType.NONE,
                (30.0, 20.0),
                "%",
            ),
            "factor": _factor(
                "Applied after the MIB conversion, before levels and the metric: "
                "value = raw × 1 × factor. The MIB reports relative humidity in percent, "
                "so factor 1.0 leaves the reading unchanged. Set the factor to 0.1 when this "
                "firmware returns tenths of a percent (raw 450 with factor 0.1 is 45%)."
            ),
            "sensor_index": _sensor_index(),
        },
    )


def _item_condition() -> HostAndItemCondition:
    return HostAndItemCondition(item_title=Title("Sensor"))


rule_spec_apc_pdu_ext_sensors = DiscoveryParameters(
    name="apc_pdu_ext_sensors",
    title=Title("APC PDU external sensor names"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_discovery_form,
    help_text=Help(
        "Sets the service item for external temperature and humidity sensors on APC rack PDUs. "
        "Rediscover services after a change."
    ),
)

rule_spec_apc_pdu_ext_temp = CheckParameters(
    name="apc_pdu_ext_temp",
    title=Title("APC PDU external temperature"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_temperature_form,
    condition=_item_condition(),
    create_enforced_service=False,
    help_text=Help(
        "Levels and multiplication factor for the Temperature service of an APC PDU sensor."
    ),
)

rule_spec_apc_pdu_ext_humidity = CheckParameters(
    name="apc_pdu_ext_humidity",
    title=Title("APC PDU external humidity"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_humidity_form,
    condition=_item_condition(),
    create_enforced_service=False,
    help_text=Help(
        "Levels and multiplication factor for the Humidity service of an APC PDU sensor."
    ),
)
