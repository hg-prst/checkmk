# File hash over HTTP(s)

Checkmk **2.4** extension package (MKP) with an **active check** that runs on the Checkmk
server: the server downloads one or more files over HTTP(S), computes the hash
(MD5, SHA-1, SHA-256 or SHA-512) and compares it with the expected value.

One service is created per file: `File hash over HTTP(s) <name or URL>`.

| Situation | Status |
|---|---|
| Hash matches (case-insensitive) | **OK** |
| Hash does not match (expected vs. received in the output) | **CRIT** |
| Download error, HTTP error (e.g. 404), timeout, TLS error | **CRIT** |
| Invalid parameters | **UNKNOWN** |

Performance data: `size` (bytes) and `duration` (seconds).

## Requirements

- Checkmk 2.4.0 or newer (all editions, including Raw/Community).
- Uses the new plug-in APIs `cmk.rulesets.v1` and `cmk.server_side_calls.v1`.
- The check script uses only the Python 3 standard library.

## Upgrade from 1.0.1 or older

The package name changed from `file_hash_check` to `file_hash_over_http`. Checkmk
treats that as a different package and does not replace the old package. Remove
the old package `file_hash_check` first, then create the rules again under
the new ruleset.

On the command line, as the site user:

```bash
mkp disable file_hash_check 1.0.1
mkp remove file_hash_check 1.0.1
```

If `mkp list` shows a different version, use that version. The same can be done in the GUI:
**Setup > Maintenance > Extension packages** — disable and remove the package `file_hash_check`.

Then install version 1.0.2 (see below) and create the rules again via
**Setup > Services > HTTP, TCP, email, ... > File hash over HTTP(s)**. Existing rules
from the old ruleset `file_hash` are not carried over.

## Installation

Download `file_hash_over_http-1.0.2.mkp` (see `dist/` or the Releases).

### Via the GUI (Enterprise/Cloud edition)

1. **Setup > Maintenance > Extension packages**
2. **Upload package**, choose the `.mkp` file.
3. Make sure the package is **enabled** and **activate the changes** (Activate changes).

### Via the command line (all editions, including Raw)

```bash
# as the site user
su - <sitename>
mkp add /tmp/file_hash_over_http-1.0.2.mkp
mkp enable file_hash_over_http 1.0.2
mkp list
cmk -R        # or: Activate changes in the GUI
```

Removal: `mkp disable file_hash_over_http 1.0.2` and then `mkp remove file_hash_over_http 1.0.2`.

After installation the files are in
`~/local/lib/python3/cmk_addons/plugins/file_hash_over_http/`:

```
file_hash_over_http/
├── libexec/check_file_hash_over_http          # the check script (executable)
├── rulesets/file_hash_over_http.py            # GUI rule
└── server_side_calls/file_hash_over_http.py   # translates the rule into commands
```

## Configuration in the GUI

**Setup > Services > HTTP, TCP, email, ... > File hash over HTTP(s)**

(Or search the Setup menu for "file hash".)

1. Create a new rule and, under **Conditions**, choose which host(s) the check
   applies to. The check always runs on the Checkmk server; the host only determines
   where the services appear. A host such as the Checkmk server itself, or a host
   belonging to the web server, is the obvious choice.
2. Under **Files to check**, click **Add file** for each file and fill in:
   - **URL of the file**: `http://` or `https://`
   - **Hash algorithm**: MD5, SHA-1, SHA-256 (default) or SHA-512
   - **Expected hash**: the hexadecimal hash (uppercase and lowercase do not matter)
   - **Service name** (optional): the service is then called `File hash over HTTP(s) <name>`, otherwise
     `File hash over HTTP(s) <URL>`
3. General options for every file in the rule:
   - **Timeout**: network timeout per file (default 30 s)
   - **TLS certificate verification**: verify the certificate (on by default)
4. **Save** > **Activate changes**. Service discovery is not required afterwards: active
   checks show up immediately.

Macros such as `$HOSTNAME$` or `$HOSTADDRESS$` are allowed in the URL and the service name.

## Computing a hash

**Windows (PowerShell):**

```powershell
Get-FileHash .\file.iso -Algorithm SHA256
# other algorithms: MD5, SHA1, SHA512
(Get-FileHash .\file.iso -Algorithm SHA256).Hash   # the hash only
```

**Linux / macOS:**

```bash
sha256sum file.iso      # also: md5sum, sha1sum, sha512sum
# macOS: shasum -a 256 file.iso
```

Straight from the URL (Linux):

```bash
curl -fsSL https://example.com/file.iso | sha256sum
```

## Testing the check script by hand

As the site user on the Checkmk server:

```bash
~/local/lib/python3/cmk_addons/plugins/file_hash_over_http/libexec/check_file_hash_over_http \
    --url https://example.com/file.iso \
    --algorithm sha256 \
    --expected <hash> \
    --timeout 30            # optional; --no-verify-tls to turn TLS verification off
echo "exit code: $?"
```

## Development

The source lives in `file-hash-over-http/` at the root of this repository.

```
src/file_hash_over_http/  # contents of the MKP part "cmk_addons_plugins"
build_mkp.py                # builds dist/file_hash_over_http-<version>.mkp
tests/                      # tests
```

Build (Python 3 standard library only):

```bash
python3 build_mkp.py                 # -> dist/file_hash_over_http-1.0.2.mkp
python3 build_mkp.py --version 1.0.3
```

Testing:

```bash
# check script against a local http.server (match, mismatch, 404, bad arguments)
python3 tests/test_check_file_hash_over_http.py

# validate plug-ins and the MKP against the Checkmk 2.4 source (requires pydantic)
git clone --depth 1 --branch 2.4.0 https://github.com/Checkmk/checkmk.git /tmp/cmk
pip install pydantic
CMK_SRC=/tmp/cmk python3 tests/test_against_cmk_source.py
```

## License

MIT, see [LICENSE](../LICENSE).
