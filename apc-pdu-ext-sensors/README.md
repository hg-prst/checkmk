# APC PDU Temperature and Humidity metrics (external)

Checkmk **2.4** extension package (MKP) `apc_pdu_ext_sensors` **1.1.0**. It reads external
temperature and humidity sensors on APC (Schneider) rack PDUs over SNMP
(PowerNet-MIB `rPDU2SensorTempHumidityStatusTable`).

There is **one check plug-in**, `apc_rackpdu_ext_env`. Temperature and humidity are
separate services of that check, so the thresholds and the factor stay independent:

| Service (default) | Metric | Unit |
|---|---|---|
| `Temperature Ext Sensor #N` | `temp` | °C |
| `Humidity Ext Sensor #N` | `humidity` | % |

`#N` is 1, 2, 3, … in SNMP index order of sensors that are actually present.
The lowest index is `#1`. A temperature-only sensor does not get a
humidity service, but it still counts in the numbering. Rows that are not installed,
or whose communication is down, are skipped during discovery.

The plug-in output is `Current: 18.7 °C` or `Current: 29.0%`. Threshold text
(`warn/crit at …` / `warn/crit below …`) follows that when the status is not OK.

The metrics `temp` and `humidity` are Checkmk's standard metrics. The built-in
graph and perfometer (degrees Celsius and percent) therefore work. This package
does not define those metrics again: that would replace the graphs of every other
temperature and humidity service on the site.

## Requirements

- Checkmk 2.4.0 or newer (all editions, including Raw/Community).
- SNMP to the PDU (the host must be configured as an SNMP host).
- Plug-in APIs `cmk.agent_based.v2`, `cmk.rulesets.v1` and `cmk.graphing.v1`.

The package applies only to APC PDUs:

- `sysObjectID` (`.1.3.6.1.2.1.1.2.0`) starts with `.1.3.6.1.4.1.318.1.3.4.5`
  (PowerNet `products.system` for rPDU2), or
- `sysObjectID` starts with the APC enterprise `.1.3.6.1.4.1.318` **and** `sysDescr`
  contains `rPDU` or `rack pdu` / `rack-pdu`.

## Upgrade from 1.0.0

The package is still called `apc_pdu_ext_sensors`, so installing 1.1.0 replaces
1.0.0. The check name did change, from `apc_pdu_ext_temp` / `apc_pdu_ext_humidity`
to `apc_rackpdu_ext_env`. After **Activate changes** and a service discovery, the
old services disappear and `Temperature Ext Sensor #N` and `Humidity Ext Sensor #N` appear.

Old rules under `apc_pdu_ext_sensors`, `apc_pdu_ext_temp` and `apc_pdu_ext_humidity`
are not carried over. Create them again as described below.

## Installation

Download `apc_pdu_ext_sensors-1.1.0.mkp` (see `dist/`).

### Via the GUI (Enterprise/Cloud edition)

1. **Setup > Maintenance > Extension packages**
2. **Upload package**, choose the `.mkp` file.
3. Make sure the package is **enabled** and **activate the changes**.

### Via the command line (all editions, including Raw)

```bash
# as the site user
su - <sitename>
mkp add /tmp/apc_pdu_ext_sensors-1.1.0.mkp
mkp enable apc_pdu_ext_sensors 1.1.0
mkp list
cmk -R
```

Removal: `mkp disable apc_pdu_ext_sensors 1.1.0` and then
`mkp remove apc_pdu_ext_sensors 1.1.0`.

After installation the files are in
`~/local/lib/python3/cmk_addons/plugins/apc_pdu_ext_sensors/`:

```
apc_pdu_ext_sensors/
├── agent_based/apc_rackpdu_ext_env.py   # SNMP section and the check
├── rulesets/apc_rackpdu_ext_env.py      # names, thresholds and factor
└── graphing/apc_rackpdu_ext_env.py      # units; uses the built-in graphs
```

Then run a service discovery on the PDU host.

## OIDs

Table `rPDU2SensorTempHumidityStatusTable`, entry
`.1.3.6.1.4.1.318.1.1.26.10.2.2.1` (one row per sensor). Source: PowerNet-MIB 4.6.0.

| Column | Object | Meaning |
|---|---|---|
| 1 | `...StatusIndex` | Index of the row |
| 2 | `...StatusModule` | Numeric PDU id |
| 3 | `...StatusName` | Name of the sensor, as set on the PDU |
| 4 | `...StatusNumber` | Numeric sensor id on the PDU |
| 5 | `...StatusType` | 1 temperature only, 2 temperature+humidity, 3 comms lost, 4 not installed |
| 6 | `...StatusCommStatus` | 1 not installed, 2 comms OK, 3 comms lost |
| 8 | `...StatusTempC` | Temperature in **tenths of °C** (243 = 24.3 °C) |
| 9 | `...StatusTempStatus` | 1 not present, 2 below min, 3 below low, 4 normal, 5 above high, 6 above max |
| 10 | `...StatusRelativeHumidity` | Relative humidity in **percent** |
| 11 | `...StatusHumidityStatus` | The same statuses as temperature |

Column 7 is the same sensor in tenths of °F and is not used.

Discovery skips a row when the communication status is not `comms OK`, the type
is `not installed` or `comms lost`, or the reading in question is `not present`.
If the service already exists and the sensor later disappears, the service becomes **CRIT**
(communication down or not installed) or **UNKNOWN** (row or reading gone).

## Scale and factor

```
value = raw SNMP integer × MIB scale × factor
```

| Metric | MIB scale | Factor 1.0 |
|---|---|---|
| Temperature | 0.1 (tenths of °C) | raw 243 → 24.3 °C |
| Humidity | 1 (percent) | raw 45 → 45% |

The factor defaults to **1.0** and can be set per metric. Whole degrees instead
of tenths: temperature factor **10** (25 × 0.1 × 10 = 25). Humidity in
tenths of a percent: humidity factor **0.1** (450 × 0.1 = 45). The
service details show the raw value, the scale and the factor.

## Configuration in the GUI

Checkmk 2.4 keeps discovery parameters and check parameters in separate rulesets. The
service name is fixed at discovery; thresholds are read only when the check runs.
That is why there are two pages. They cannot be combined.

### Service name

**Setup > Service discovery rules > APC rack PDU external sensor names**

(Ruleset `apc_rackpdu_ext_env_discovery`, topic Environmental.)

Without a rule:

- `Temperature Ext Sensor #1`
- `Humidity Ext Sensor #1`

`#1` is the present sensor with the lowest SNMP index, `#2` the next, and so on.
A gap in the index (1, 2, 5) therefore becomes `#1`, `#2`, `#3`. A sensor that later
disappears, or one that is added with a lower index, renumbers the sensors after it.

**Add sensor name** adds a text field, tied to that number:

- **Sensor number**: `#N`
- **Service name**: replaces `Ext Sensor #N`

Sensor 1 with the text `Cold aisle` becomes:

- `Temperature Cold aisle`
- `Humidity Cold aisle`

The prefix `Temperature` / `Humidity` stays, so the two services of the
same sensor do not get the same name. The first rule for a number wins.
Put every sensor of a host in one rule.

**Then run service discovery again.** Without discovery the old
service name stays. The discovered SNMP index stays attached to the service.

Checkmk cannot generate a text field per live sensor from the SNMP walk
inside a ruleset. You add a row yourself for each number `#N`.

### Thresholds and factor

**Setup > Services > Service monitoring rules > APC rack PDU external environment**

One page (ruleset `apc_rackpdu_ext_env`) for both metrics:

- upper and lower temperature thresholds
- temperature factor
- upper and lower humidity thresholds
- humidity factor

A temperature service reads only the temperature fields; a humidity service
reads only the humidity fields.

Without a rule:

| Service | Upper (warn/crit) | Lower | Factor |
|---|---|---|---|
| Temperature | 30 / 35 °C | none | 1.0 |
| Humidity | 70 / 80% | none | 1.0 |

The **Service item** condition is a regular expression on the service item, and that
item is the full service name. Examples:

- `Temperature Ext Sensor #1` — only that temperature service
- `.*Ext Sensor #1` — temperature and humidity of sensor 1
- `.*Cold aisle` — both services after sensor 1 has been renamed that way

Leave the item condition empty to apply the rule to every sensor of the selected hosts.
Checkmk compares the upper limit with `>=` and the lower limit with `<`. Exactly
30 °C with an upper limit of 30/35 is therefore **WARN**.

The graph shows the upper warn/crit lines. The lower thresholds determine the
status; Checkmk only puts the upper levels on the metric.

## Inspecting a sensor by hand

```bash
snmpwalk -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.8.1
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.10.1
```

## Development

```
src/apc_pdu_ext_sensors/   # contents of the MKP part "cmk_addons_plugins"
build_mkp.py               # builds dist/apc_pdu_ext_sensors-<version>.mkp
tests/
```

```bash
python3 build_mkp.py                 # -> dist/apc_pdu_ext_sensors-1.1.0.mkp
python3 build_mkp.py --version 1.1.1
```

```bash
git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
pip install pydantic
CMK_SRC=/tmp/cmk python3 tests/test_apc_pdu_ext_sensors.py
CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
```

## License

MIT, see [LICENSE](../LICENSE).
