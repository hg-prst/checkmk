#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""One check-parameter page and one discovery page for apc_rackpdu_ext_env.

Checkmk 2.4 cannot put discovery parameters and check parameters in the same
ruleset: service names are chosen while discovering, and levels are applied
later by the check. The name overrides therefore live in
apc_rackpdu_ext_env_discovery. Levels and factors for both metrics live in
apc_rackpdu_ext_env.
"""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    DefaultValue,
    DictElement,
    Dictionary,
    Float,
    InputHint,
    Integer,
    LevelDirection,
    LevelsType,
    List,
    SimpleLevels,
    String,
    validators,
)
from cmk.rulesets.v1.rule_specs import (
    CheckParameters,
    DiscoveryParameters,
    HostAndItemCondition,
    Topic,
)


def _name_entry() -> Dictionary:
    return Dictionary(
        title=Title("Sensor name"),
        elements={
            "number": DictElement(
                required=True,
                parameter_form=Integer(
                    title=Title("Sensor number"),
                    help_text=Help(
                        "The #N in the default service name 'Temperature Ext Sensor #N' "
                        "(and the humidity service with the same number). "
                        "Numbers follow the SNMP index order of sensors that are present: "
                        "the lowest index is #1."
                    ),
                    custom_validate=(validators.NumberInRange(min_value=1),),
                ),
            ),
            "name": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("Service name"),
                    help_text=Help(
                        "Replaces 'Ext Sensor #N'. The services become "
                        "'Temperature <text>' and 'Humidity <text>'. "
                        "Run service discovery again after changing this."
                    ),
                    custom_validate=(validators.LengthInRange(min_value=1, max_value=64),),
                ),
            ),
        },
    )


def _discovery_form() -> Dictionary:
    return Dictionary(
        title=Title("APC rack PDU external sensor names"),
        help_text=Help(
            "Optional names for the external sensors, keyed by sensor number #N. "
            "Without an entry the services are 'Temperature Ext Sensor #N' and "
            "'Humidity Ext Sensor #N'."
        ),
        elements={
            "names": DictElement(
                required=False,
                parameter_form=List(
                    title=Title("Sensor names"),
                    help_text=Help(
                        "One row per sensor number. Put every sensor of a host in one rule; "
                        "when several rules match, Checkmk keeps the list of the most specific rule. "
                        "Rediscover services after a change. Adding or removing a sensor with a "
                        "lower SNMP index renumbers the sensors after it."
                    ),
                    element_template=_name_entry(),
                    add_element_label=Label("Add sensor name"),
                    remove_element_label=Label("Remove sensor name"),
                    no_element_label=Label("No custom sensor names"),
                ),
            ),
        },
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
                "factor. The service item condition is a regular expression on the service "
                "description. Leave it unset to cover every sensor, or use "
                "'.*Ext Sensor #1' to cover both services of sensor 1."
            ),
            form_spec_template=Float(unit_symbol=unit),
            level_direction=direction,
            prefill_levels_type=DefaultValue(prefill_type),
            prefill_fixed_levels=DefaultValue(fixed),
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


def _parameter_form() -> Dictionary:
    return Dictionary(
        title=Title("APC rack PDU external environment"),
        help_text=Help(
            "Upper and lower levels and the multiplication factor for external APC PDU "
            "temperature and humidity. A temperature service uses the temperature fields; "
            "a humidity service uses the humidity fields. "
            "Defaults without a rule: temperature 30/35 °C, humidity 70/80%, "
            "no lower levels, factor 1.0."
        ),
        elements={
            "temp_levels_upper": _levels(
                "Upper temperature levels",
                LevelDirection.UPPER,
                LevelsType.FIXED,
                (30.0, 35.0),
                "°C",
            ),
            "temp_levels_lower": _levels(
                "Lower temperature levels",
                LevelDirection.LOWER,
                LevelsType.NONE,
                (15.0, 10.0),
                "°C",
            ),
            "temp_factor": _factor(
                "Applied to temperature after the MIB conversion: value = raw × 0.1 × factor. "
                "Factor 1.0 turns 243 into 24.3 °C. Set 10 when this firmware already returns "
                "whole degrees (raw 25 × 0.1 × 10 = 25 °C)."
            ),
            "humidity_levels_upper": _levels(
                "Upper humidity levels",
                LevelDirection.UPPER,
                LevelsType.FIXED,
                (70.0, 80.0),
                "%",
            ),
            "humidity_levels_lower": _levels(
                "Lower humidity levels",
                LevelDirection.LOWER,
                LevelsType.NONE,
                (30.0, 20.0),
                "%",
            ),
            "humidity_factor": _factor(
                "Applied to humidity after the MIB conversion: value = raw × 1 × factor. "
                "The MIB reports percent, so factor 1.0 leaves the reading unchanged. "
                "Set 0.1 when this firmware returns tenths of a percent "
                "(raw 450 × 0.1 = 45%)."
            ),
            "sensor_index": DictElement(
                required=False,
                render_only=True,
                parameter_form=String(
                    title=Title("SNMP index"),
                    help_text=Help(
                        "Discovered row index. It keeps the service attached to the same sensor "
                        "after the service name is changed."
                    ),
                    prefill=InputHint(""),
                ),
            ),
            "sensor_number": DictElement(
                required=False,
                render_only=True,
                parameter_form=Integer(
                    title=Title("Sensor number"),
                    help_text=Help("Discovered position #N in SNMP index order."),
                    prefill=InputHint(0),
                ),
            ),
        },
    )


rule_spec_apc_rackpdu_ext_env_discovery = DiscoveryParameters(
    name="apc_rackpdu_ext_env_discovery",
    title=Title("APC rack PDU external sensor names"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_discovery_form,
    help_text=Help(
        "Replaces 'Ext Sensor #N' in the service names of check apc_rackpdu_ext_env. "
        "Rediscover services after a change."
    ),
)

rule_spec_apc_rackpdu_ext_env = CheckParameters(
    name="apc_rackpdu_ext_env",
    title=Title("APC rack PDU external environment"),
    topic=Topic.ENVIRONMENTAL,
    parameter_form=_parameter_form,
    condition=HostAndItemCondition(
        item_title=Title("Service item"),
        item_form=String(
            title=Title("Service item"),
            help_text=Help(
                "Regular expression matched against the service item, which is the full "
                "service description. Examples: 'Temperature Ext Sensor #1', "
                "'Humidity Ext Sensor #1', or '.*Ext Sensor #1' for both services of sensor 1. "
                "After a rename, match the new description, for example '.*Cold aisle'."
            ),
            custom_validate=(validators.LengthInRange(min_value=1),),
        ),
    ),
    create_enforced_service=False,
    help_text=Help(
        "Levels and factors for the temperature and humidity services of an APC rack PDU."
    ),
)
