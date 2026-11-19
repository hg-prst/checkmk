#!/usr/bin/env python3
# Copyright (C) 2026 Hugo Proost - License: MIT
"""Turns the 'File hash over HTTP(s)' rule into one active check command per file.

Checkmk 2.4 looks for the executable 'check_file_hash' in
  1. ../../libexec relative to this file (cmk_addons/plugins/file_hash/libexec/)
  2. ~/local/lib/nagios/plugins
  3. ~/lib/nagios/plugins
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from cmk.server_side_calls.v1 import (
    ActiveCheckCommand,
    ActiveCheckConfig,
    HostConfig,
    replace_macros,
)

_ALGORITHMS = ("md5", "sha1", "sha256", "sha512")


@dataclass(frozen=True)
class FileEntry:
    url: str
    algorithm: str
    expected_hash: str
    name: str | None = None


@dataclass(frozen=True)
class Params:
    files: tuple[FileEntry, ...]
    timeout: float | None = None
    verify_tls: bool = True


def parse_params(raw: Mapping[str, object]) -> Params:
    files = []
    for item in raw.get("files", []) or []:  # type: ignore[union-attr]
        if not isinstance(item, Mapping):
            raise TypeError(f"invalid file entry: {item!r}")
        algorithm = str(item.get("algorithm", "sha256"))
        if algorithm not in _ALGORITHMS:
            raise ValueError(f"unsupported algorithm: {algorithm}")
        name = item.get("name")
        files.append(
            FileEntry(
                url=str(item["url"]),
                algorithm=algorithm,
                expected_hash=str(item["expected_hash"]),
                name=str(name) if name else None,
            )
        )
    timeout = raw.get("timeout")
    return Params(
        files=tuple(files),
        timeout=float(timeout) if timeout is not None else None,  # type: ignore[arg-type]
        verify_tls=bool(raw.get("verify_tls", True)),
    )


def commands_file_hash(params: Params, host_config: HostConfig) -> Iterable[ActiveCheckCommand]:
    for entry in params.files:
        url = replace_macros(entry.url, host_config.macros)
        label = replace_macros(entry.name, host_config.macros) if entry.name else url
        args: list[str] = [
            "--url",
            url,
            "--algorithm",
            entry.algorithm,
            "--expected",
            entry.expected_hash,
        ]
        if params.timeout is not None:
            args += ["--timeout", f"{params.timeout:g}"]
        if not params.verify_tls:
            args.append("--no-verify-tls")
        yield ActiveCheckCommand(service_description=f"File hash {label}", command_arguments=args)


active_check_file_hash = ActiveCheckConfig(
    name="file_hash",
    parameter_parser=parse_params,
    commands_function=commands_file_hash,
)
