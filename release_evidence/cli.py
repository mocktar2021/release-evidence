"""Create and verify a manifest. A trusted manifest is required, not assumed."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

class EvidenceError(ValueError):
    pass

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise EvidenceError('Release root must be a real directory')
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise EvidenceError(f'Symlinks are not supported: {path}')
        if path.is_file():
            name = path.relative_to(root).as_posix()
            result[name] = {'path': name, 'size': path.stat().st_size, 'sha256': digest(path)}
        elif not path.is_dir():
            raise EvidenceError(f'Special files are not supported: {path}')
    return result

def validate_checks(checks):
    if not isinstance(checks, list):
        raise EvidenceError('Checks must be an array')
    for item in checks:
        if not isinstance(item, dict) or set(item) != {'name', 'status'}:
            raise EvidenceError('Each check needs only name and status')
        if not isinstance(item['name'], str) or not item['name'].strip():
            raise EvidenceError('Check name must be nonempty')
        if item['status'] not in ('passed', 'failed', 'skipped'):
            raise EvidenceError('Check status must be passed, failed or skipped')
    return checks

def create(root, version, output, checks=None):
    root, output = Path(root), Path(output)
    if not version.strip():
        raise EvidenceError('Version must not be empty')
    if output.resolve().is_relative_to(root.resolve()):
        raise EvidenceError('Write the manifest outside the release directory')
    files = inventory(root)
    if not files:
        raise EvidenceError('Release contains no files')
    manifest = {'schema_version': 1, 'release_version': version,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'algorithm': 'sha256', 'checks': validate_checks([] if checks is None else checks),
                'files': list(files.values())}
    # Exclusive creation prevents accidental overwrite of an existing evidence record.
    with output.open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    return digest(output)

def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise EvidenceError(f'Duplicate JSON key: {key}')
        obj[key] = value
    return obj

def verify(root, manifest_path, expected_digest=None):
    path = Path(manifest_path)
    if path.is_symlink():
        raise EvidenceError('Manifest must not be a symlink')
    if path.stat().st_size > 10 * 1024 * 1024:
        raise EvidenceError('Manifest exceeds the 10 MiB prototype limit')
    raw = path.read_bytes()
    if expected_digest is not None:
        if not re.fullmatch('[0-9a-fA-F]{64}', expected_digest):
            raise EvidenceError('Expected manifest digest must be 64 hexadecimal characters')
        if hashlib.sha256(raw).hexdigest() != expected_digest.lower():
            raise EvidenceError('Manifest does not match the trusted digest')
    data = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('algorithm') != 'sha256':
        raise EvidenceError('Unsupported manifest schema or algorithm')
    if not isinstance(data.get('release_version'), str) or not data['release_version'].strip():
        raise EvidenceError('Invalid release version')
    validate_checks(data.get('checks'))
    entries = data.get('files')
    if not isinstance(entries, list) or not entries:
        raise EvidenceError('Manifest needs a nonempty file list')
    recorded = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {'path', 'size', 'sha256'}:
            raise EvidenceError('Invalid file entry')
        name = entry['path']
        if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
            raise EvidenceError('Unsafe file path')
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or str(p) != name or name in recorded:
            raise EvidenceError('Unsafe or duplicate file path')
        if type(entry['size']) is not int or entry['size'] < 0:
            raise EvidenceError('Invalid file size')
        if not isinstance(entry['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise EvidenceError('Invalid SHA-256')
        recorded[name] = entry
    actual = inventory(root)
    issues = [f'missing: {p}' for p in sorted(recorded.keys() - actual.keys())]
    issues += [f'unexpected: {p}' for p in sorted(actual.keys() - recorded.keys())]
    issues += [f'changed: {p}' for p in sorted(actual.keys() & recorded.keys()) if actual[p] != recorded[p]]
    return {'ok': not issues, 'release_version': data['release_version'], 'issues': issues,
            'checks': data['checks'], 'manifest_digest_checked': expected_digest is not None}

def main(argv=None):
    parser = argparse.ArgumentParser(description='Create or verify offline release evidence (prototype)')
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('create')
    make.add_argument('directory')
    make.add_argument('--version', required=True)
    make.add_argument('--output', required=True)
    make.add_argument('--checks', help='JSON file with name/status objects; supplied claims, not independently verified')
    check = sub.add_parser('verify')
    check.add_argument('directory')
    check.add_argument('--manifest', required=True)
    check.add_argument('--manifest-sha256', help='Digest obtained independently from a trusted publisher')
    args = parser.parse_args(argv)
    try:
        if args.command == 'create':
            checks = json.loads(Path(args.checks).read_text()) if args.checks else []
            value = create(args.directory, args.version, args.output, checks)
            print(json.dumps({'manifest': args.output, 'sha256': value}))
            return 0
        result = verify(args.directory, args.manifest, args.manifest_sha256)
        print(json.dumps(result, indent=2))
        return 0 if result['ok'] else 1
    except (EvidenceError, OSError, ValueError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
