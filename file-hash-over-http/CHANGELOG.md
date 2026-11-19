# Changelog

## 1.0.2

- Technische namen volgen nu de projectnaam "File hash over HTTP(s)": pakket `file_hash_over_http`, plug-in-familie `file_hash_over_http`, active check `file_hash_over_http` (uitvoerbaar bestand `check_file_hash_over_http`) en ruleset `file_hash_over_http`.
- Servicenaam is `File hash over HTTP(s) <naam of URL>`.
- Auteur van het MKP is Hugo Proost (h.proost[at]iubentium[dot]nl).
- Upgrade: omdat de pakketnaam is gewijzigd, verwijder eerst het oude pakket `file_hash_check` (`mkp disable` / `mkp remove`, of via de GUI) voordat je dit pakket installeert. Maak de regels opnieuw aan onder de nieuwe ruleset; bestaande regels van `file_hash` worden niet overgenomen.

## 1.0.1

- Weergavenaam van het pakket en van de GUI-regel is nu "File hash over HTTP(s)".
- Auteur van het MKP is Hugo Proost (h.proost[at]iubentium[dot]nl). Copyright in LICENSE staat op Hugo Proost.
- Technische pakketnaam `file_hash_check`, plug-in-familie en checknamen zijn ongewijzigd, zodat een upgrade bestaande regels en services behoudt.
- Projectmap hernoemd van `file-hash-check/` naar `file-hash-over-http/`.
