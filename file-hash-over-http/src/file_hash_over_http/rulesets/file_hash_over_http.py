#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""GUI rule (Setup > Services > HTTP, TCP, email, ... > File hash over HTTP(s)) for the file_hash_over_http active check."""

from cmk.rulesets.v1 import Help, Label, Title
from cmk.rulesets.v1.form_specs import (
    BooleanChoice,
    DefaultValue,
    DictElement,
    Dictionary,
    List,
    SingleChoice,
    SingleChoiceElement,
    String,
    TimeMagnitude,
    TimeSpan,
    validators,
)
from cmk.rulesets.v1.rule_specs import ActiveCheck, Topic

_HEX = r"^[0-9a-fA-F]+$"


def _file_entry() -> Dictionary:
    return Dictionary(
        title=Title("File"),
        elements={
            "url": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("URL of the file"),
                    help_text=Help("HTTP(S) URL of the file that the Checkmk server downloads."),
                    custom_validate=(
                        validators.Url(
                            protocols=[validators.UrlProtocol.HTTP, validators.UrlProtocol.HTTPS]
                        ),
                    ),
                ),
            ),
            "algorithm": DictElement(
                required=True,
                parameter_form=SingleChoice(
                    title=Title("Hash algorithm"),
                    elements=[
                        SingleChoiceElement(name="md5", title=Title("MD5")),
                        SingleChoiceElement(name="sha1", title=Title("SHA-1")),
                        SingleChoiceElement(name="sha256", title=Title("SHA-256")),
                        SingleChoiceElement(name="sha512", title=Title("SHA-512")),
                    ],
                    prefill=DefaultValue("sha256"),
                ),
            ),
            "expected_hash": DictElement(
                required=True,
                parameter_form=String(
                    title=Title("Expected hash"),
                    help_text=Help(
                        "Hexadecimal hash value. Comparison is case-insensitive; "
                        "spaces are ignored."
                    ),
                    custom_validate=(
                        validators.LengthInRange(min_value=32, max_value=160),
                    ),
                ),
            ),
            "name": DictElement(
                required=False,
                parameter_form=String(
                    title=Title("Service name"),
                    help_text=Help(
                        "Optional. The service will be called 'File hash over HTTP(s) <name>'. "
                        "If not set, the service is called 'File hash over HTTP(s) <URL>'."
                    ),
                    custom_validate=(validators.LengthInRange(min_value=1),),
                ),
            ),
        },
    )


def _form_spec() -> Dictionary:
    return Dictionary(
        title=Title("File hash over HTTP(s)"),
        help_text=Help(
            "Downloads one or more files from the Checkmk server and compares their hash "
            "(MD5/SHA-1/SHA-256/SHA-512) with the expected value. One service is created per file, "
            "named 'File hash over HTTP(s) <name or URL>': "
            "OK if the hash matches, CRIT on mismatch or download error."
        ),
        elements={
            "files": DictElement(
                required=True,
                parameter_form=List(
                    title=Title("Files to check"),
                    element_template=_file_entry(),
                    add_element_label=Label("Add file"),
                    remove_element_label=Label("Remove file"),
                    no_element_label=Label("No files configured"),
                    custom_validate=(validators.LengthInRange(min_value=1),),
                ),
            ),
            "timeout": DictElement(
                required=False,
                parameter_form=TimeSpan(
                    title=Title("Timeout"),
                    help_text=Help("Network timeout per file (connect and read)."),
                    displayed_magnitudes=[TimeMagnitude.SECOND, TimeMagnitude.MINUTE],
                    prefill=DefaultValue(30.0),
                    custom_validate=(validators.NumberInRange(min_value=1.0),),
                ),
            ),
            "verify_tls": DictElement(
                required=False,
                parameter_form=BooleanChoice(
                    title=Title("TLS certificate verification"),
                    label=Label("Verify the server certificate"),
                    prefill=DefaultValue(True),
                ),
            ),
        },
    )


rule_spec_file_hash_over_http = ActiveCheck(
    name="file_hash_over_http",
    title=Title("File hash over HTTP(s)"),
    topic=Topic.APPLICATIONS,
    parameter_form=_form_spec,
)
