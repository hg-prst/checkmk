# Changelog

## 1.1.0

- One check plug-in `apc_rackpdu_ext_env` for temperature and humidity. The SNMP section has the same name.
- The default service name is `Temperature Ext Sensor #N` and `Humidity Ext Sensor #N`. `#N` follows the SNMP index order of sensors that are present.
- A custom service name per sensor number `#N` in the discovery rule. That replaces `Ext Sensor #N`; service discovery is required afterwards.
- Thresholds (upper and lower) and the factor for both metrics are on one check parameter page `apc_rackpdu_ext_env`. The name belongs in a separate discovery rule; Checkmk 2.4 cannot put those two in the same ruleset.
- The summary is `Current: 18.7 °C` and `Current: 29.0%`.
- Upgrade from 1.0.0: the package is still called `apc_pdu_ext_sensors`, but the check and ruleset names have changed. Old services disappear after a new discovery and the old rules (`apc_pdu_ext_temp`, `apc_pdu_ext_humidity`, `apc_pdu_ext_sensors`) are not carried over.

## 1.0.0

- First version: SNMP check for external temperature and humidity sensors on APC rack PDUs (PowerNet-MIB `rPDU2SensorTempHumidityStatusTable`).
- For each present sensor, a separate service `Temperature <name>` and, for a combined sensor, `Humidity <name>`.
- Service name via a discovery rule; thresholds (upper and lower) and multiplication factor per item via the Setup rules.
- Temperature from the MIB is in tenths of °C (scale 0.1); humidity is already percent. The default factor of 1.0 is applied on top of that.
- Author of the MKP is Hugo Proost (h.proost[at]iubentium[dot]nl).
