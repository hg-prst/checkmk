# Changelog

## 1.0.0

- Eerste versie: SNMP-check voor externe temperatuur- en vochtigheidssensoren op APC rack-PDU's (PowerNet-MIB `rPDU2SensorTempHumidityStatusTable`).
- Per aanwezige sensor een aparte service `Temperature <naam>` en, bij een gecombineerde sensor, `Humidity <naam>`.
- Servicenaam via een discovery-regel; drempels (boven en onder) en vermenigvuldigingsfactor per item via de Setup-regels.
- Temperatuur uit de MIB is in tienden van °C (schaal 0,1); vochtigheid is al procent. Factor standaard 1,0 komt daar bovenop.
- Auteur van het MKP is Hugo Proost (h.proost[at]iubentium[dot]nl).
