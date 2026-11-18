# checkmk-file-hash

Checkmk **2.4** extensiepakket (MKP) met een **active check** die op de Checkmk-server
draait: de server downloadt één of meer bestanden via HTTP(S), berekent de hash
(MD5, SHA-1, SHA-256 of SHA-512) en vergelijkt die met de verwachte waarde.

Per bestand wordt één service aangemaakt: `File hash <naam of URL>`.

| Situatie | Status |
|---|---|
| Hash klopt (hoofdletterongevoelig) | **OK** |
| Hash klopt niet (verwacht vs. gekregen in de output) | **CRIT** |
| Downloadfout, HTTP-fout (bv. 404), timeout, TLS-fout | **CRIT** |
| Ongeldige parameters | **UNKNOWN** |

Performance data: `size` (bytes) en `duration` (seconden).

## Vereisten

- Checkmk 2.4.0 of nieuwer (alle edities, ook Raw/Community).
- Gebruikt de nieuwe plug-in-API's `cmk.rulesets.v1` en `cmk.server_side_calls.v1`.
- Het check-script gebruikt alleen de Python 3 standaardbibliotheek.

## Installatie

Download `file_hash_check-1.0.0.mkp` (zie `dist/` of de Releases).

### Via de GUI (Enterprise/Cloud-editie)

1. **Setup > Maintenance > Extension packages**
2. **Upload package**, kies het `.mkp`-bestand.
3. Zorg dat het pakket **enabled** is en **activeer de wijzigingen** (Activate changes).

### Via de command line (alle edities, ook Raw)

```bash
# als site-gebruiker
su - <sitenaam>
mkp add /tmp/file_hash_check-1.0.0.mkp
mkp enable file_hash_check 1.0.0
mkp list
cmk -R        # of: Activate changes in de GUI
```

Verwijderen: `mkp disable file_hash_check 1.0.0` en daarna `mkp remove file_hash_check 1.0.0`.

Na installatie staan de bestanden in
`~/local/lib/python3/cmk_addons/plugins/file_hash/`:

```
file_hash/
├── libexec/check_file_hash            # het check-script (uitvoerbaar)
├── rulesets/file_hash.py              # GUI-regel
└── server_side_calls/file_hash.py     # vertaling regel -> commando's
```

## Configuratie in de GUI

**Setup > Services > HTTP, TCP, email, ... > Check file hash**

(Of zoek in het Setup-menu op "file hash".)

1. Maak een nieuwe regel aan en kies onder **Conditions** voor welke host(s) de check
   moet gelden. De check draait altijd op de Checkmk-server; de host bepaalt alleen
   waar de services verschijnen. Een host als de Checkmk-server zelf of een host van
   de webserver ligt voor de hand.
2. Onder **Files to check** klik je op **Add file** per bestand en vul je in:
   - **URL of the file**: `http://` of `https://`
   - **Hash algorithm**: MD5, SHA-1, SHA-256 (standaard) of SHA-512
   - **Expected hash**: de hexadecimale hash (hoofdletters/kleine letters maakt niet uit)
   - **Service name** (optioneel): de service heet dan `File hash <naam>`, anders
     `File hash <URL>`
3. Algemene opties voor alle bestanden in de regel:
   - **Timeout**: netwerk-timeout per bestand (standaard 30 s)
   - **TLS certificate verification**: certificaat controleren (standaard aan)
4. **Save** > **Activate changes**. Daarna service discovery doen is niet nodig: active
   checks verschijnen meteen.

Macro's zoals `$HOSTNAME$` of `$HOSTADDRESS$` mogen in de URL en de servicenaam.

## Een hash berekenen

**Windows (PowerShell):**

```powershell
Get-FileHash .\bestand.iso -Algorithm SHA256
# andere algoritmes: MD5, SHA1, SHA512
(Get-FileHash .\bestand.iso -Algorithm SHA256).Hash   # alleen de hash
```

**Linux / macOS:**

```bash
sha256sum bestand.iso      # ook: md5sum, sha1sum, sha512sum
# macOS: shasum -a 256 bestand.iso
```

Direct vanaf de URL (Linux):

```bash
curl -fsSL https://voorbeeld.be/bestand.iso | sha256sum
```

## Het check-script handmatig testen

Als site-gebruiker op de Checkmk-server:

```bash
~/local/lib/python3/cmk_addons/plugins/file_hash/libexec/check_file_hash \
    --url https://voorbeeld.be/bestand.iso \
    --algorithm sha256 \
    --expected <hash> \
    --timeout 30            # optioneel; --no-verify-tls om TLS-controle uit te zetten
echo "exit code: $?"
```

## Ontwikkeling

```
src/file_hash/          # inhoud van het MKP-deel "cmk_addons_plugins"
build_mkp.py            # bouwt dist/file_hash_check-<versie>.mkp
tests/                  # tests
```

Bouwen (alleen Python 3 standaardbibliotheek):

```bash
python3 build_mkp.py                 # -> dist/file_hash_check-1.0.0.mkp
python3 build_mkp.py --version 1.0.1
```

Testen:

```bash
# check-script tegen een lokale http.server (match, mismatch, 404, foute argumenten)
python3 tests/test_check_file_hash.py

# plug-ins en MKP valideren tegen de Checkmk 2.4-broncode (vereist pydantic)
git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
pip install pydantic
CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
```

## Licentie

MIT, zie [LICENSE](../LICENSE).
