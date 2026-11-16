# Release Evidence

A small, dependency-free Python prototype for software handovers in small nonprofits.
It records the files in a release, their SHA-256 fingerprints, a version label and selected
check results. A second maintainer can verify the files offline without reconstructing old CI logs.

## Status and limits

This is a working prototype, not a security certification, deployed service or proof of nonprofit adoption.
No fellowship eligibility is claimed. This project was developed with AI assistance under Mocktar Tairou's direction.

**Trust matters:** hashes detect changes relative to a manifest you trust. They do not establish who
published the manifest. An attacker who replaces both files and an untrusted manifest can make them agree.
Keep the manifest or its digest in an independently trusted channel. `--manifest-sha256` checks that digest;
it is not a signature. Without it, verification checks file consistency only.

Recorded checks are supplied claims. A `passed` entry does not prove a test ran. Verification does not
rerun tests, judge code quality, or fail because a recorded check says `failed`. It reports those statuses
separately. There is no remote service, telemetry or network access in the CLI.

## Run from source (Python 3.10+)

No installation or dependencies are needed:

```sh
python -m release_evidence create examples/release --version 0.1.0 --checks examples/checks.json --output manifest.json
python -m release_evidence verify examples/release --manifest manifest.json
```

The first command prints the manifest's SHA-256. Record that through an independent trusted channel.
To check it later:

```sh
python -m release_evidence verify examples/release --manifest manifest.json --manifest-sha256 YOUR_64_CHARACTER_DIGEST
```

Alternatively, install the package with `python -m pip install .` and use `release-evidence`.
The packaging route requires setuptools; direct execution remains dependency-free.

## Handover demonstration

1. Copy the `examples/release` directory, manifest and this source tool to another machine.
2. Verify the original release: expect `ok: true` and exit code 0.
3. Edit `service.txt` in the copied release and verify again: expect `changed: service.txt` and exit code 1.
4. Missing or additional files also fail verification.
5. If an independently trusted manifest digest was supplied, changing the manifest itself fails with exit code 2.

No execution of the release contents occurs. The manifest is JSON, not a runnable script or archive.

## Inputs and outputs

All regular files recursively under the release directory are included, including hidden files. **Use a clean
staging directory and review it for credentials/private data before making a bundle public.** The tool does
not copy artifact bytes; hand over the directory alongside the manifest. Empty directories, timestamps and
permissions are not covered. Symlinks and special files are rejected. Do not modify files during hashing.
The release directory must be stable and trusted locally; concurrent mutation is outside this prototype's threat model.

The manifest output must be outside the release directory. Existing outputs are never overwritten.
Checks JSON is an array of `{"name": "unit tests", "status": "passed"}` objects. Supported statuses:
`passed`, `failed`, `skipped`. Avoid secrets or personal data in names/version labels.

Exit codes: `0` success, `1` integrity mismatch, `2` invalid input or read/write failure.
Manifest verification rejects duplicate paths/JSON keys, traversal/absolute paths, malformed hashes and
unsupported schemas. Manifests are limited to 10 MiB. File hashing is streamed.

## GitHub Actions example

`.github/workflows/evidence.yml` runs tests, creates a demonstration evidence bundle and uploads it as a
short-retention workflow artifact. It runs manually, not on every commit. It has read-only repository permissions,
uses no application secrets, does not publish releases, and does not deploy anything. The demonstration check
status is written only after the unit tests succeed. Replace the sample release with your own clean build output
before production use. GitHub-hosted execution requires network; verification after download does not.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests cover clean and changed releases, missing/extra files, trusted-manifest tampering, malformed paths,
symlinks, duplicate JSON keys/file records, invalid inputs and binary/Unicode nested files.

## Next steps

- Have another maintainer follow the instructions from a fresh checkout.
- Keep the hosted workflow and supported action versions tested.
- Evaluate signed manifests and a durable trusted distribution channel.
- Pilot with nonprofit maintainers before claiming usability or adoption.

## License

MIT License. Copyright (c) 2026 Mocktar Tairou. See [LICENSE](LICENSE).

The source in this repository was developed for this project; no third-party source is vendored.
Python, setuptools and the referenced GitHub Actions retain their respective licenses.
