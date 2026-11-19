# checkmk

Verzameling CheckMK-extensies (MKP) van hg-prst.

Elk project staat in een eigen map in de root van deze repository.

## Projecten

| Project | Beschrijving | CheckMK | Map |
|---|---|---|---|
| File hash over HTTP(s) | Active check die bestanden via HTTP(S) downloadt en de hash (MD5, SHA-1, SHA-256 of SHA-512) verifieert. | 2.4+ | [file-hash-check](file-hash-check/) |

## Installatie

Een pakket installeer je in Checkmk via **Setup > Maintenance > Extension packages**: upload het `.mkp`-bestand, zet het pakket op enabled en activeer de wijzigingen.

Op de command line, als site-gebruiker:

```bash
mkp add /pad/naar/pakket.mkp
mkp enable <naam> <versie>
```

Details per extensie staan in de README van het project.
