"""Validate the existing Windows release assets; --publish performs the manually approved publication."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from package import ROOT, VERSION, digest, npm_cli, run
import shutil

REQUIRED_CHECKS = {
    'asset-checksums', 'mcp-installer-extracted', 'mcp-tarball-install', 'tool-surface',
    'arbitrary-argument-rejected', 'status-before-init', 'init-completed', 'install-receipt',
    'start-ready', 'start-identity', 'port-conflict-avoided', 'packaged-frontend', 'nodes-find',
    'nodes-get', 'start-reused', 'web-survives-mcp', 'stop-completed', 'stop-ports-closed',
    'status-after-stop', 'workspace-preserved', 'restart-after-stop', 'restart-frontend',
    'shutdown-controlled', 'idempotent-reinstall-preserves-workspace', 'interrupted-download-resumed',
    'checksum-failure-not-activated', 'directory-guards', 'foreign-pid-stop-refused',
    'workspace-data-preserved'
}


def validate(directory, tag):
    manifest = json.loads((directory / 'release-manifest.json').read_text())
    if manifest['schema_version'] != 2 or tag != 'v' + manifest['version'] or not VERSION.fullmatch(manifest['version']):
        raise ValueError('Release manifest and tag do not agree.')
    if manifest['publication'] != 'published':
        raise ValueError('A local candidate is not publishable; only a clean tagged build may be published.')
    if (directory / 'candidate.json').exists():
        raise ValueError('Candidate assets must never reach the public release channel.')
    product = json.loads((ROOT / 'package.json').read_text())
    runtime = json.loads((Path(__file__).with_name('runtime.json')).read_text())
    if manifest['version'] != product['version'] or manifest['repository'] != runtime['repository']:
        raise ValueError('Release identity differs from the checked-out product.')
    if manifest['runtime']['uv'] != {**runtime['uv'], 'url': (
            'https://github.com/astral-sh/uv/releases/download/'
            f"{runtime['uv']['version']}/uv-x86_64-pc-windows-msvc.zip")}:
        raise ValueError('The release must download the pinned official uv runtime.')
    if manifest['runtime']['python'] != runtime['python']:
        raise ValueError('The release must use the pinned Python runtime.')
    if manifest['commit'] != run(['git', 'rev-parse', 'HEAD']):
        raise ValueError('Verification must name the checked-out release commit.')
    hashes = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        if Path(name).name != name or '\\' in name or name in hashes:
            raise ValueError('Invalid or duplicate checksum asset name.')
        if digest(directory / name) != expected:
            raise ValueError('Asset checksum mismatch: ' + name)
        hashes[name] = expected
    for name in ['release-manifest.json', manifest['workbench']['file'], manifest['mcp']['file'],
                 f"astrophoto-flow-{manifest['version']}-source.tar.gz"]:
        if name not in hashes:
            raise ValueError('Required release asset is not covered by checksums: ' + name)
    if hashes[manifest['workbench']['file']] != manifest['workbench']['sha256'] or hashes[manifest['mcp']['file']] != manifest['mcp']['sha256']:
        raise ValueError('Manifest asset hashes do not match SHA256SUMS.')
    report = json.loads((directory / 'verification.json').read_text())
    if report['schema_version'] != 2:
        raise ValueError('The verification report predates the MCP lifecycle release format; rerun scripts/release/verify.ps1.')
    if report['status'] != 'passed' or report['platform'] != 'windows-x64' or report['version'] != manifest['version'] or report['commit'] != manifest['commit']:
        raise ValueError('A passing Windows-native verification report for these assets is required.')
    if report['publication'] != manifest['publication']:
        raise ValueError('Verification and manifest disagree about the publication channel.')
    if report['artifacts'] != hashes or not REQUIRED_CHECKS.issubset(report['checks']):
        raise ValueError('Windows verification is incomplete or belongs to different assets.')
    if manifest['mcp']['name'] != '@xu123/astrophoto-flow' or manifest['mcp']['version'] != manifest['version']:
        raise ValueError('MCP and workstation release identities differ.')
    with (directory / manifest['mcp']['file']).open('rb') as stream:
        integrity = 'sha512-' + base64.b64encode(hashlib.file_digest(stream, 'sha512').digest()).decode()
    if manifest['mcp']['integrity'] != integrity:
        raise ValueError('MCP npm integrity does not describe the actual tarball.')
    return manifest


def publish(directory, tag):
    manifest = validate(directory, tag)
    repository = manifest['repository']
    metadata = json.loads(run(['gh', 'api', 'repos/' + repository]))
    if metadata['private']:
        raise ValueError('The first public release requires the maintainer to make the corresponding source repository public.')
    release = json.loads(run(['gh', 'release', 'view', tag, '--repo', repository, '--json', 'isDraft']))
    package_url = 'https://registry.npmjs.org/' + urllib.parse.quote(manifest['mcp']['name'], safe='') + '/' + manifest['version']
    try:
        with urllib.request.urlopen(package_url, timeout=30) as response:
            existing = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        existing = None
    if existing:
        if existing['dist']['integrity'] != manifest['mcp']['integrity']:
            raise ValueError('The npm version already exists with different tarball bytes; do not overwrite or rebuild it.')
    else:
        if not release['isDraft']:
            raise ValueError('The GitHub release is already public but its npm counterpart is missing; investigate before publishing.')
        npm_version = run([shutil.which('node'), str(npm_cli()), '--version'])
        if tuple(map(int, npm_version.split('.'))) < (11, 5, 1):
            raise ValueError('npm trusted publishing requires npm >=11.5.1.')
        subprocess.run([shutil.which('node'), str(npm_cli()), 'publish', str(directory / manifest['mcp']['file']), '--access', 'public', '--tag', 'next' if '-dev.' in manifest['version'] else 'latest'], cwd=ROOT, check=True)
    if release['isDraft']:
        run(['gh', 'release', 'edit', tag, '--repo', repository, '--draft=false'])
    print(json.dumps({'status': 'published', 'tag': tag, 'repository': repository}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    try:
        if not args.tag.startswith('v') or not VERSION.fullmatch(args.tag[1:]):
            raise ValueError('Invalid version tag.')
        if args.assets:
            manifest = validate(args.assets.resolve(), args.tag)
            if args.publish:
                publish(args.assets.resolve(), args.tag)
            else:
                print(json.dumps({'status': 'validated', 'version': manifest['version']}))
        else:
            if not args.publish:
                raise ValueError('Supply --assets for local validation or --publish for approved draft publication.')
            repository = json.loads((Path(__file__).with_name('runtime.json')).read_text())['repository']
            with tempfile.TemporaryDirectory(prefix='apf-publish-') as temporary:
                directory = Path(temporary)
                run(['gh', 'release', 'download', args.tag, '--repo', repository, '--dir', str(directory)])
                publish(directory, args.tag)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
