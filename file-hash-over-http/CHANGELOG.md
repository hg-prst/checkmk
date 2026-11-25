# Changelog

## 1.0.2

- Technical names now follow the project name "File hash over HTTP(s)": package `file_hash_over_http`, plug-in family `file_hash_over_http`, active check `file_hash_over_http` (executable `check_file_hash_over_http`) and ruleset `file_hash_over_http`.
- The service name is `File hash over HTTP(s) <name or URL>`.
- Author of the MKP is Hugo Proost (h.proost[at]iubentium[dot]nl).
- Upgrade: because the package name changed, remove the old package `file_hash_check` first (`mkp disable` / `mkp remove`, or via the GUI) before installing this package. Create the rules again under the new ruleset; existing rules from `file_hash` are not carried over.

## 1.0.1

- The display name of the package and of the GUI rule is now "File hash over HTTP(s)".
- Author of the MKP is Hugo Proost (h.proost[at]iubentium[dot]nl). The copyright in LICENSE is Hugo Proost.
- The technical package name `file_hash_check`, the plug-in family and the check names are unchanged, so an upgrade keeps existing rules and services.
- Project directory renamed from `file-hash-check/` to `file-hash-over-http/`.
