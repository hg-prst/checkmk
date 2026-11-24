# APC PDU Temperature and Humidity metrics (external)

Checkmk **2.4** extensiepakket (MKP) dat externe temperatuur- en vochtigheidssensoren
op APC (Schneider) rack-PDU's uitleest via SNMP. De gegevens komen uit de
PowerNet-MIB-tabel `rPDU2SensorTempHumidityStatusTable`.

Per aanwezige sensor worden **twee services** ontdekt, zodat drempels en de factor
onafhankelijk zijn:

| Service | Metriek | Eenheid |
|---|---|---|
| `Temperature <item>` | `temp` | °C |
| `Humidity <item>` | `humidity` | % |

`<item>` is de naam van de sensor op de PDU, of een naam die je in de discovery-regel
zet. Een temperatuur-only sensor krijgt geen humidity-service. Rijen die niet
geïnstalleerd zijn of waarvan de communicatie weg is, worden bij discovery overgeslagen.

De metrieken `temp` en `humidity` zijn de standaardmetrieken van Checkmk. Daardoor
werken de ingebouwde grafiek en perfometer (graden Celsius en procent) zonder dat dit
pakket die metrieken opnieuw definieert. Opnieuw definiëren zou de grafieken van
alle andere temperatuur- en vochtigheidsservices op de site vervangen.

## Vereisten

- Checkmk 2.4.0 of nieuwer (alle edities, ook Raw/Community).
- SNMP naar de PDU (de host moet als SNMP-host geconfigureerd zijn).
- Gebruikt de plug-in-API's `cmk.agent_based.v2`, `cmk.rulesets.v1` en `cmk.graphing.v1`.

Het pakket geldt alleen voor APC-PDU's:

- `sysObjectID` (`.1.3.6.1.2.1.1.2.0`) begint met `.1.3.6.1.4.1.318.1.3.4.5`
  (PowerNet `products.system` voor rPDU2), of
- `sysObjectID` begint met de APC-enterprise `.1.3.6.1.4.1.318` **en** `sysDescr`
  bevat `rPDU` of `rack pdu` / `rack-pdu`.

UPS'en en andere APC-apparaten vallen daar buiten.

## Installatie

Download `apc_pdu_ext_sensors-1.0.0.mkp` (zie `dist/`).

### Via de GUI (Enterprise/Cloud-editie)

1. **Setup > Maintenance > Extension packages**
2. **Upload package**, kies het `.mkp`-bestand.
3. Zorg dat het pakket **enabled** is en **activeer de wijzigingen** (Activate changes).

### Via de command line (alle edities, ook Raw)

```bash
# als site-gebruiker
su - <sitenaam>
mkp add /tmp/apc_pdu_ext_sensors-1.0.0.mkp
mkp enable apc_pdu_ext_sensors 1.0.0
mkp list
cmk -R        # of: Activate changes in de GUI
```

Verwijderen: `mkp disable apc_pdu_ext_sensors 1.0.0` en daarna `mkp remove apc_pdu_ext_sensors 1.0.0`.

Na installatie staan de bestanden in
`~/local/lib/python3/cmk_addons/plugins/apc_pdu_ext_sensors/`:

```
apc_pdu_ext_sensors/
├── agent_based/apc_pdu_ext_sensors.py   # SNMP-sectie en checks
├── rulesets/apc_pdu_ext_sensors.py      # discovery-namen, drempels en factor
└── graphing/apc_pdu_ext_sensors.py      # eenheden; gebruikt de ingebouwde grafieken
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
| 4 | `...StatusNumber` | Numeriek sensor-id |
| 5 | `...StatusType` | 1 temperature only, 2 temperature+humidity, 3 comms lost, 4 not installed |
| 6 | `...StatusCommStatus` | 1 not installed, 2 comms OK, 3 comms lost |
| 8 | `...StatusTempC` | Temperatuur in **tienden van °C** (243 = 24,3 °C) |
| 9 | `...StatusTempStatus` | 1 not present, 2 below min, 3 below low, 4 normal, 5 above high, 6 above max |
| 10 | `...StatusRelativeHumidity` | Relatieve vochtigheid in **procent** |
| 11 | `...StatusHumidityStatus` | Zelfde statussen als de temperatuur |

Kolom 7 is dezelfde sensor in tienden van °F. Die kolom wordt niet gebruikt.

Discovery slaat een rij over wanneer de communicatiestatus niet `comms OK` is, het type
`not installed` of `comms lost` is, of de betreffende meetwaarde `not present` is.
Een sensor die alleen temperatuur meet (type 1) krijgt geen humidity-service.
Bestaat de service al en valt de sensor later weg, dan wordt de service **CRIT**
(communicatie weg of niet geïnstalleerd) of **UNKNOWN** (rij of meetwaarde verdwenen).

## Schaal en factor

De MIB legt de eenheid vast. De factor in de Setup-regel komt daar bovenop en staat
standaard op **1,0**:

```
waarde = ruwe SNMP-integer × MIB-schaal × factor
```

| Metriek | MIB-schaal | Voorbeeld met factor 1,0 |
|---|---|---|
| Temperatuur | 0,1 (tienden °C) | ruw 243 → 24,3 °C |
| Vochtigheid | 1 (procent) | ruw 45 → 45% |

Drempels en de metriek gebruiken die waarde, niet het ruwe getal.

Wijkt de firmware af van de MIB, dan corrigeer je dat per sensor en per metriek met de factor:

- Temperatuur al in hele graden (ruw 25 betekent 25 °C): factor **10** (25 × 0,1 × 10 = 25).
- Vochtigheid in tienden van een procent (ruw 450 betekent 45%): factor **0,1**.

De service-details tonen het ruwe getal, de MIB-schaal en de factor, zodat je dit naast
de webinterface van de PDU kunt leggen.

## Configuratie in de GUI

### Servicenaam

**Setup > Service discovery rules > APC PDU external sensor names**

(Of zoek in Setup op "APC PDU". Onderwerp: Environmental.)

Zonder regel is het item de naam uit `rPDU2SensorTempHumidityStatusName`. Is die leeg,
dan heet het item `Sensor <index>`.

Met **Add sensor name** koppel je een eigen naam:

- **Sensor**: de SNMP-index, het sensornummer, de PDU-naam, of `Sensor <index>`.
- **Service item name**: het item. De services heten dan `Temperature <naam>` en
  `Humidity <naam>`. De plugin-output begint met diezelfde naam, bijvoorbeeld
  `Hugo's inlet: 24.3 °C`.

De eerste match wint. Twee sensoren met dezelfde naam krijgen een suffix
` [<index>]`, zodat de items uniek blijven.

Na een wijziging opnieuw service discovery doen. Drempelregels matchen op dit item,
dus zet de naam vast vóór je per sensor drempels maakt. Het ontdekte SNMP-indexnummer
blijft aan de service hangen, zodat de check dezelfde sensor blijft volgen.

### Drempels en factor

Twee aparte regels, allebei met een conditie op het service-item (**Sensor**):

- **Setup > Services > Service monitoring rules > APC PDU external temperature**
- **Setup > Services > Service monitoring rules > APC PDU external humidity**

Elke regel heeft:

- **Upper levels**: warning en critical bij een te hoge waarde.
- **Lower levels**: warning en critical bij een te lage waarde. Standaard uit;
  de vaste voorbeeldwaarden zijn 15/10 °C en 30/20%.
- **Multiplication factor**: zie hierboven, standaard 1,0.

Zonder regel gelden deze standaardwaarden (al op de geschaalde waarde):

| Service | Boven (warn/crit) | Onder | Factor |
|---|---|---|---|
| Temperature | 30 / 35 °C | geen | 1,0 |
| Humidity | 70 / 80% | geen | 1,0 |

De conditie **Sensor** is het item (`Hugo's inlet`), niet de volledige servicenaam
`Temperature Hugo's inlet`. Temperatuur en vochtigheid hebben elk hun eigen regel,
dus de factor en de drempels hoeven niet gelijk te zijn.

Checkmk vergelijkt de bovengrens met `>=` en de ondergrens met `<`. Een temperatuur
van exact 30 °C met bovengrens 30/35 is daardoor al **WARN**.

De grafiek toont de bovenste warn/crit-lijnen op de metriek. De onderste drempels
bepalen wel de status, maar Checkmk zet alleen de bovenste levels op de metriek.

## Handmatig een sensor bekijken

```bash
snmpwalk -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1
# temperatuur sensor 1, in tienden van °C
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.8.1
# vochtigheid sensor 1, in procent
snmpget -v2c -c <community> <pdu> .1.3.6.1.4.1.318.1.1.26.10.2.2.1.10.1
```

## Ontwikkeling

Bron staat in `apc-pdu-ext-sensors/` in de root van deze repository.

```
src/apc_pdu_ext_sensors/   # inhoud van het MKP-deel "cmk_addons_plugins"
build_mkp.py               # bouwt dist/apc_pdu_ext_sensors-<versie>.mkp
tests/                     # tests
```

Bouwen (alleen Python 3 standaardbibliotheek):

```bash
python3 build_mkp.py                 # -> dist/apc_pdu_ext_sensors-1.0.0.mkp
python3 build_mkp.py --version 1.0.1
```

Testen:

```bash
git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
pip install pydantic
CMK_SRC=/tmp/cmk python3 tests/test_apc_pdu_ext_sensors.py
CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
```

## Licentie

MIT, zie [LICENSE](../LICENSE).
