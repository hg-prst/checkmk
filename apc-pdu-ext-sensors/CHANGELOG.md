# Changelog

## 1.1.0

- Eén checkplug-in `apc_rackpdu_ext_env` voor temperatuur en vochtigheid. De SNMP-sectie heet hetzelfde.
- Standaardservicenaam is `Temperature Ext Sensor #N` en `Humidity Ext Sensor #N`. `#N` volgt de volgorde van de SNMP-index van aanwezige sensoren.
- Eigen servicenaam per sensornummer `#N` in de discovery-regel. Die vervangt `Ext Sensor #N`; daarna is service discovery nodig.
- Drempels (boven en onder) en de factor voor beide metrieken staan op één checkparameterpagina `apc_rackpdu_ext_env`. De naam hoort in een aparte discovery-regel; Checkmk 2.4 kan die twee niet in dezelfde ruleset zetten.
- De samenvatting is `Current: 18.7 °C` en `Current: 29.0%`.
- Upgrade vanaf 1.0.0: het pakket heet nog `apc_pdu_ext_sensors`, maar de check- en rulesetnamen zijn gewijzigd. Oude services verdwijnen na een nieuwe discovery en de oude regels (`apc_pdu_ext_temp`, `apc_pdu_ext_humidity`, `apc_pdu_ext_sensors`) worden niet overgenomen.

## 1.0.0

- Eerste versie: SNMP-check voor externe temperatuur- en vochtigheidssensoren op APC rack-PDU's (PowerNet-MIB `rPDU2SensorTempHumidityStatusTable`).
- Per aanwezige sensor een aparte service `Temperature <naam>` en, bij een gecombineerde sensor, `Humidity <naam>`.
- Servicenaam via een discovery-regel; drempels (boven en onder) en vermenigvuldigingsfactor per item via de Setup-regels.
- Temperatuur uit de MIB is in tienden van °C (schaal 0,1); vochtigheid is al procent. Factor standaard 1,0 komt daar bovenop.
- Auteur van het MKP is Hugo Proost (h.proost[at]iubentium[dot]nl).
