# APC PDU Temperature and Humidity metrics (external)

Checkmk **2.4** extensiepakket (MKP) `apc_pdu_ext_sensors` **1.1.0**. Het leest externe
temperatuur- en vochtigheidssensoren op APC (Schneider) rack-PDU's uit via SNMP
(PowerNet-MIB `rPDU2SensorTempHumidityStatusTable`).

Er is **één checkplug-in**, `apc_rackpdu_ext_env`. Temperatuur en vochtigheid zijn
aparte services van die check, zodat drempels en de factor onafhankelijk blijven:

| Service (standaard) | Metriek | Eenheid |
|---|---|---|
| `Temperature Ext Sensor #N` | `temp` | °C |
| `Humidity Ext Sensor #N` | `humidity` | % |

`#N` is 1, 2, 3, … in de volgorde van de SNMP-index van sensoren die echt aanwezig
zijn. De laagste index is `#1`. Een temperatuur-only sensor krijgt geen
humidity-service, maar telt wel mee in de nummering. Rijen die niet geïnstalleerd
zijn of waarvan de communicatie weg is, worden bij discovery overgeslagen.

De plugin-output is `Current: 18.7 °C` of `Current: 29.0%`. Drempeltekst
(`warn/crit at …` / `warn/crit below …`) volgt daarop wanneer de status niet OK is.

De metrieken `temp` en `humidity` zijn de standaardmetrieken van Checkmk. Daardoor
werken de ingebouwde grafiek en perfometer (graden Celsius en procent). Dit pakket
definieert die metrieken niet opnieuw: dat zou de grafieken van alle andere
temperatuur- en vochtigheidsservices op de site vervangen.

## Vereisten

- Checkmk 2.4.0 of nieuwer (alle edities, ook Raw/Community).
- SNMP naar de PDU (de host moet als SNMP-host geconfigureerd zijn).
- Plug-in-API's `cmk.agent_based.v2`, `cmk.rulesets.v1` en `cmk.graphing.v1`.

Het pakket geldt alleen voor APC-PDU's:

- `sysObjectID` (`.1.3.6.1.2.1.1.2.0`) begint met `.1.3.6.1.4.1.318.1.3.4.5`
  (PowerNet `products.system` voor rPDU2), of
- `sysObjectID` begint met de APC-enterprise `.1.3.6.1.4.1.318` **en** `sysDescr`
  bevat `rPDU` of `rack pdu` / `rack-pdu`.

## Upgrade vanaf 1.0.0

Het pakket heet nog `apc_pdu_ext_sensors`, dus een installatie van 1.1.0 vervangt
1.0.0. De checknaam is wel veranderd van `apc_pdu_ext_temp` / `apc_pdu_ext_humidity`
naar `apc_rackpdu_ext_env`. Na **Activate changes** en een service discovery verdwijnen
de oude services en verschijnen `Temperature Ext Sensor #N` en `Humidity Ext Sensor #N`.

Oude regels onder `apc_pdu_ext_sensors`, `apc_pdu_ext_temp` en `apc_pdu_ext_humidity`
worden niet overgenomen. Maak ze opnieuw aan zoals hieronder.

## Installatie

Download `apc_pdu_ext_sensors-1.1.0.mkp` (zie `dist/`).

### Via de GUI (Enterprise/Cloud-editie)

1. **Setup > Maintenance > Extension packages**
2. **Upload package**, kies het `.mkp`-bestand.
3. Zorg dat het pakket **enabled** is en **activeer de wijzigingen**.

### Via de command line (alle edities, ook Raw)

```bash
# als site-gebruiker
su - <sitenaam>
mkp add /tmp/apc_pdu_ext_sensors-1.1.0.mkp
mkp enable apc_pdu_ext_sensors 1.1.0
mkp list
cmk -R
```

Verwijderen: `mkp disable apc_pdu_ext_sensors 1.1.0` en daarna
`mkp remove apc_pdu_ext_sensors 1.1.0`.

Na installatie staan de bestanden in
`~/local/lib/python3/cmk_addons/plugins/apc_pdu_ext_sensors/`:

```
apc_pdu_ext_sensors/
├── agent_based/apc_rackpdu_ext_env.py   # SNMP-sectie en de check
├── rulesets/apc_rackpdu_ext_env.py      # namen, drempels en factor
└── graphing/apc_rackpdu_ext_env.py      # eenheden; gebruikt de ingebouwde grafieken
```

Daarna op de PDU-host een service discovery draaien.

## OIDs

Tabel `rPDU2SensorTempHumidityStatusTable`, entry
`.1.3.6.1.4.1.318.1.1.26.10.2.2.1` (één rij per sensor). Bron: PowerNet-MIB 4.6.0.

| Kolom | Object | Betekenis |
|---|---|---|
| 1 | `...StatusIndex` | Index van de rij |
| 2 | `...StatusModule` | Numeriek PDU-id |
| 3 | `...StatusName` | Naam van de sensor, zoals op de PDU gezet |
| 4 | `...StatusNumber` | Numeriek sensor-id op de PDU |
| 5 | `...StatusType` | 1 temperature only, 2 temperature+humidity, 3 comms lost, 4 not installed |
| 6 | `...StatusCommStatus` | 1 not installed, 2 comms OK, 3 comms lost |
| 8 | `...StatusTempC` | Temperatuur in **tienden van °C** (243 = 24,3 °C) |
| 9 | `...StatusTempStatus` | 1 not present, 2 below min, 3 below low, 4 normal, 5 above high, 6 above max |
| 10 | `...StatusRelativeHumidity` | Relatieve vochtigheid in **procent** |
| 11 | `...StatusHumidityStatus` | Zelfde statussen als de temperatuur |

Kolom 7 is dezelfde sensor in tienden van °F en wordt niet gebruikt.

Discovery slaat een rij over wanneer de communicatiestatus niet `comms OK` is, het type
`not installed` of `comms lost` is, of de betreffende meetwaarde `not present` is.
Bestaat de service al en valt de sensor later weg, dan wordt de service **CRIT**
(communicatie weg of niet geïnstalleerd) of **UNKNOWN** (rij of meetwaarde verdwenen).

## Schaal en factor

```
waarde = ruwe SNMP-integer × MIB-schaal × factor
```

| Metriek | MIB-schaal | Factor 1,0 |
|---|---|---|
| Temperatuur | 0,1 (tienden °C) | ruw 243 → 24,3 °C |
| Vochtigheid | 1 (procent) | ruw 45 → 45% |

De factor staat standaard op **1,0** en is per metriek in te stellen. Hele graden in
plaats van tienden: temperatuurfactor **10** (25 × 0,1 × 10 = 25). Vochtigheid in
tienden van een procent: vochtigheidsfactor **0,1** (450 × 0,1 = 45). De
service-details tonen ruwe waarde, schaal en factor.

## Configuratie in de GUI

Checkmk 2.4 houdt discovery-parameters en checkparameters in aparte rulesets. De
servicenaam wordt bij discovery vastgelegd; drempels worden pas bij de check gelezen.
Daarom zijn er twee pagina's. Ze kunnen niet worden samengevoegd.

### Servicenaam

**Setup > Service discovery rules > APC rack PDU external sensor names**

(Ruleset `apc_rackpdu_ext_env_discovery`, onderwerp Environmental.)

Zonder regel:

- `Temperature Ext Sensor #1`
- `Humidity Ext Sensor #1`

`#1` is de aanwezige sensor met de laagste SNMP-index, `#2` de volgende, enzovoort.
Een gat in de index (1, 2, 5) wordt dus `#1`, `#2`, `#3`. Een sensor die later
wegvalt of erbij komt met een lagere index hernummert de sensoren erna.

**Add sensor name** voegt een tekstveld toe, gekoppeld aan dat nummer:

- **Sensor number**: `#N`
- **Service name**: vervangt `Ext Sensor #N`

Sensor 1 met tekst `Cold aisle` wordt:

- `Temperature Cold aisle`
- `Humidity Cold aisle`

Het voorvoegsel `Temperature` / `Humidity` blijft staan, zodat de twee services van
dezelfde sensor niet dezelfde naam krijgen. De eerste regel voor een nummer wint.
Zet alle sensoren van een host in één regel.

**Daarna opnieuw service discovery doen.** Zonder discovery blijft de oude
servicenaam staan. Het ontdekte SNMP-indexnummer blijft aan de service hangen.

Checkmk kan in een ruleset geen tekstveld per live sensor uit de SNMP-walk
genereren. Je voegt zelf een rij toe per nummer `#N`.

### Drempels en factor

**Setup > Services > Service monitoring rules > APC rack PDU external environment**

Eén pagina (ruleset `apc_rackpdu_ext_env`) voor beide metrieken:

- boven- en onderdrempels temperatuur
- factor temperatuur
- boven- en onderdrempels vochtigheid
- factor vochtigheid

Een temperatuurservice leest alleen de temperatuurvelden, een vochtigheidsservice
alleen de vochtigheidsvelden.

Zonder regel:

| Service | Boven (warn/crit) | Onder | Factor |
|---|---|---|---|
| Temperature | 30 / 35 °C | geen | 1,0 |
| Humidity | 70 / 80% | geen | 1,0 |

De conditie **Service item** is een reguliere expressie op de service-item, en dat
item is de volledige servicenaam. Voorbeelden:

- `Temperature Ext Sensor #1` — alleen die temperatuurservice
- `.*Ext Sensor #1` — temperatuur én vochtigheid van sensor 1
- `.*Cold aisle` — beide services nadat sensor 1 zo hernoemd is

Laat de itemconditie leeg om de regel op alle sensoren van de gekozen hosts toe te
passen. Checkmk vergelijkt de bovengrens met `>=` en de ondergrens met `<`. Exact
30 °C bij bovengrens 30/35 is daardoor **WARN**.

De grafiek toont de bovenste warn/crit-lijnen. De onderste drempels bepalen de
status; Checkmk zet alleen de bovenste levels op de metriek.

## Handmatig een sensor bekijken

```bash
snmpwalk -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.8.1
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.10.1
```

## Ontwikkeling

```
src/apc_pdu_ext_sensors/   # inhoud van het MKP-deel "cmk_addons_plugins"
build_mkp.py               # bouwt dist/apc_pdu_ext_sensors-<versie>.mkp
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

## Licentie

MIT, zie [LICENSE](../LICENSE).
