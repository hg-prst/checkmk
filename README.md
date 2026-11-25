# checkmk

Collection of CheckMK extensions (MKP) by hg-prst.

Each project lives in its own directory at the root of this repository.

## Projects

| Project | Description | CheckMK | Directory |
|---|---|---|---|
| File hash over HTTP(s) | Active check that downloads files over HTTP(S) and verifies the hash (MD5, SHA-1, SHA-256 or SHA-512). | 2.4+ | [file-hash-over-http](file-hash-over-http/) |
| APC PDU Temperature and Humidity metrics (external) | SNMP check `apc_rackpdu_ext_env` for external temperature and humidity sensors on APC rack PDUs (PowerNet-MIB). Services are called `Temperature Ext Sensor #N` and `Humidity Ext Sensor #N` by default. | 2.4+ | [apc-pdu-ext-sensors](apc-pdu-ext-sensors/) |

## Installation

Install a package in Checkmk via **Setup > Maintenance > Extension packages**: upload the `.mkp` file, set the package to enabled and activate the changes.

On the command line, as the site user:

```bash
mkp add /path/to/package.mkp
mkp enable <name> <version>
```

Details for each extension are in the project's README.
