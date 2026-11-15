"""Assemble the workbench payload, the MCP tarball and a signed-by-hash manifest.

Two modes share one assembly path:

* ``--tag vX.Y.Z`` packages a clean tagged checkout for public delivery.
* ``--candidate`` packages the current working tree, including uncommitted and
  untracked source, and marks every record as a local candidate that must not be
  published.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'src/workbench/backend'
FRONTEND = ROOT / 'src/workbench/frontend'
MCP = ROOT / 'src/mcp'
CUSTOM_NODES = BACKEND / 'custom_nodes/astrophotoflow'
SCHEMA_VERSION = 2
VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-dev\.(0|[1-9]\d*))?$')
COMMIT = re.compile(r'^[a-f0-9]{40}$')
CONTROLLER_FILES = {
    'astrophotoflow/cli.py',
    'astrophotoflow/__main__.py',
    'astrophotoflow/contracts/lifecycle.py',
    'astrophotoflow/interfaces/application/workbench.py',
    'astrophotoflow/interfaces/http/app.py',
    'astrophotoflow/interfaces/http/lifecycle.py',
    'astrophotoflow/interfaces/native/lifecycle.py',
    'custom_nodes/astrophotoflow/__init__.py',
}
BACKEND_DIRECTORIES = {
    'astrophotoflow', 'api_server', 'app', 'comfy', 'comfy_api', 'comfy_config', 'comfy_execution',
    'comfy_extras', 'middleware', 'utils',
}
BACKEND_FILES = {
    'main.py', 'nodes.py', 'server.py', 'execution.py', 'folder_paths.py', 'node_helpers.py',
    'comfyui_version.py', 'protocol.py', 'cuda_malloc.py', 'hook_breaker_ac10a0.py', 'pyproject.toml',
    'uv.lock', 'requirements.txt', 'manager_requirements.txt', '.python-version', 'README.md', 'LICENSE',
}
SOURCE_DIRECTORIES = {'scripts', 'src', 'docs', '.agents', '.github'}
SOURCE_FILES = {'AGENTS.md', 'README.md', 'LICENSE', 'NOTICE', 'package.json', 'pnpm-lock.yaml',
                'pnpm-workspace.yaml', 'tsconfig.json', '.node-version', '.gitattributes', '.gitignore'}


def run(arguments, **kwargs):
    return subprocess.check_output(arguments, cwd=ROOT, text=True, **kwargs).strip()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def settings():
    product = json.loads((ROOT / 'package.json').read_text())
    runtime = json.loads((Path(__file__).with_name('runtime.json')).read_text())
    if not VERSION.fullmatch(product['version']):
        raise ValueError('Root package.json version must be X.Y.Z or X.Y.Z-dev.N.')
    if not runtime['python'].startswith((BACKEND / '.python-version').read_text().strip() + '.'):
        raise ValueError('Release Python patch must match the backend Python line.')
    if set(runtime) != {'repository', 'uv', 'python'}:
        raise ValueError('runtime.json must declare exactly repository, uv and python.')
    return product, runtime


def source_state():
    dirty = bool(run(['git', 'status', '--porcelain', '--untracked-files=normal']))
    return dirty, run(['git', 'rev-parse', 'HEAD'])


def source_digest():
    """Hash the exact source snapshot a candidate packages."""
    tracked = run(['git', 'diff', 'HEAD', '--binary'])
    untracked = run(['git', 'ls-files', '--others', '--exclude-standard'])
    hashed = hashlib.sha256(tracked.encode())
    for name in sorted(filter(None, untracked.splitlines())):
        path = ROOT / name
        if path.is_file():
            hashed.update(name.encode())
            hashed.update(path.read_bytes())
    return hashed.hexdigest()


def preflight(tag=None, candidate=False):
    product, runtime = settings()
    missing = [name for name in CONTROLLER_FILES if not (BACKEND / name).is_file()]
    if missing:
        raise ValueError('CONTROLLER_UNAVAILABLE: missing backend files: ' + ', '.join(missing))
    dirty, commit = source_state()
    if not COMMIT.fullmatch(commit):
        raise ValueError('Cannot determine the source commit.')
    if candidate:
        return product, runtime, dirty, commit
    if tag is None:
        raise ValueError('A public assembly requires --tag.')
    if tag != 'v' + product['version']:
        raise ValueError('Release tag does not match root package.json version.')
    if dirty:
        raise ValueError('Release requires a clean checkout; commit the reviewed source first.')
    if run(['git', 'rev-parse', tag + '^{commit}']) != commit:
        raise ValueError('The release tag must name the checked-out commit.')
    return product, runtime, False, commit


def npm_cli():
    executable = shutil.which('npm')
    if not executable:
        raise ValueError('npm is required to produce the MCP tarball.')
    path = Path(executable)
    cli = path.parent / 'node_modules/npm/bin/npm-cli.js' if os.name == 'nt' else path.resolve()
    if not cli.is_file():
        raise ValueError('Cannot locate npm-cli.js next to the Node installation.')
    return cli


def pack_mcp(output, version):
    if not (MCP / 'dist/index.js').is_file():
        raise ValueError('Build MCP before packaging: node scripts/build-mcp.ts')
    if not (MCP / 'dist/installer/install.ps1').is_file():
        raise ValueError('The MCP build is missing its installer; rebuild the MCP.')
    with tempfile.TemporaryDirectory(prefix='apf-npm-') as temporary:
        stage = Path(temporary)
        shutil.copytree(MCP / 'dist', stage / 'dist')
        metadata = json.loads((MCP / 'package.json').read_text())
        metadata.update(version=version, private=False)
        for key in ['scripts', 'devDependencies', 'packageManager']:
            metadata.pop(key, None)
        (stage / 'package.json').write_text(json.dumps(metadata, indent=2) + '\n')
        shutil.copy2(ROOT / 'LICENSE', stage / 'LICENSE')
        (stage / 'NOTICE').write_text(
            'AstroPhotoFlow MCP. Corresponding source: https://github.com/MaojieXu/astrophoto-flow\n'
            'This package contains no ComfyUI engine code. Dependencies retain their licenses.\n'
        )
        result = json.loads(run([shutil.which('node'), str(npm_cli()), 'pack', str(stage), '--ignore-scripts',
                                '--json', '--pack-destination', str(output)]))
    package = output / result[0]['filename']
    return {'name': metadata['name'], 'version': version, 'file': package.name,
            'sha256': digest(package), 'integrity': result[0]['integrity']}


def payload_entries(web):
    names = run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
                 'src/workbench/backend']).split('\0')
    handed_out = set()
    for name in names:
        if not name:
            continue
        relative = Path(name).relative_to('src/workbench/backend')
        if '__pycache__' in relative.parts or relative.parts[0] == 'web':
            continue
        allowed = relative.parts[0] in BACKEND_DIRECTORIES or relative.as_posix() in BACKEND_FILES
        source = ROOT / name
        if allowed and source.is_file() and not source.is_symlink():
            handed_out.add(source)
            yield source, 'workbench/backend/' + relative.as_posix()
    # The vendored engine ignores its own custom_nodes directory, so the
    # application node package is copied explicitly instead of through git.
    for source in sorted(CUSTOM_NODES.rglob('*')):
        if source in handed_out or not source.is_file() or source.is_symlink():
            continue
        if '__pycache__' in source.parts:
            continue
        yield source, 'workbench/backend/' + source.relative_to(BACKEND).as_posix()
    for source in sorted(web.rglob('*')):
        if source.is_file() and not source.is_symlink():
            yield source, 'workbench/backend/web/' + source.relative_to(web).as_posix()


def build_payload(output, version, commit, publication):
    web = FRONTEND / 'dist'
    if not (web / 'index.html').is_file():
        raise ValueError('Build the frontend before assembling the release.')
    archive = output / f'astrophoto-flow-{version}-windows-x64.zip'
    identity = json.dumps({'version': version, 'commit': commit, 'publication': publication}) + '\n'
    written = set()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
        for source, name in payload_entries(web):
            zipped.write(source, name)
            written.add(name)
        zipped.writestr('workbench/backend/release-version.json', identity)
        for name in ['LICENSE', 'NOTICE']:
            zipped.write(ROOT / name, name)
    missing = sorted(entry for entry in CONTROLLER_FILES | {'main.py', 'web/index.html'} if 'workbench/backend/' + entry not in written)
    if missing:
        raise ValueError('The payload is missing required files: ' + ', '.join(missing))
    return {'file': archive.name, 'sha256': digest(archive)}


def normalize_tarinfo(info):
    """Pin archive metadata so a snapshot is reproducible across machines."""

    info.uid = 0
    info.gid = 0
    info.uname = ''
    info.gname = ''
    info.mtime = 0
    return info


def build_source_snapshot(output, version, commit, candidate):
    archive = output / f'astrophoto-flow-{version}-source.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        if candidate:
            names = run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split('\0')
            for name in sorted(filter(None, names)):
                if name.split('/')[0] not in SOURCE_DIRECTORIES and name not in SOURCE_FILES:
                    continue
                path = ROOT / name
                if path.is_file() and not path.is_symlink():
                    tar.add(path, arcname=name, recursive=False, filter=normalize_tarinfo)
        else:
            with tempfile.TemporaryDirectory(prefix='apf-src-') as temporary:
                staged = Path(temporary) / 'source.tar'
                subprocess.run(['git', 'archive', '--format=tar', '--output', str(staged), commit],
                               cwd=ROOT, check=True)
                with tarfile.open(staged) as source:
                    for member in source.getmembers():
                        tar.addfile(member, source.extractfile(member) if member.isfile() else None)
    return archive.name


def assemble(output, tag, candidate):
    product, runtime, dirty, commit = preflight(tag, candidate)
    if not candidate and os.name != 'nt':
        raise ValueError('A public workstation release must be assembled on Windows x64.')
    version = product['version']
    publication = 'candidate' if candidate else 'published'
    if candidate and tag is not None:
        raise ValueError('A candidate is built from the working tree and takes no release tag.')
    output.mkdir(parents=True, exist_ok=True)
    if list(output.iterdir()):
        raise ValueError('Release output directory must be empty; use a new output path.')
    workbench = build_payload(output, version, commit, publication)
    source = build_source_snapshot(output, version, commit, candidate)
    mcp = pack_mcp(output, version)
    manifest = {
        'schema_version': SCHEMA_VERSION,
        'version': version,
        'commit': commit,
        'dirty': dirty,
        'source_digest': source_digest() if candidate else None,
        'repository': runtime['repository'],
        'publication': publication,
        'runtime': {
            'uv': {**runtime['uv'], 'url': (
                'https://github.com/astral-sh/uv/releases/download/'
                f"{runtime['uv']['version']}/uv-x86_64-pc-windows-msvc.zip")},
            'python': runtime['python'],
        },
        'workbench': workbench,
        'mcp': mcp,
        'source': source,
        'web_index_sha256': digest(FRONTEND / 'dist/index.html'),
    }
    (output / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    sums = ''.join(f'{digest(path)}  {path.name}\n' for path in sorted(output.iterdir()) if path.is_file())
    (output / 'SHA256SUMS').write_text(sums)
    if candidate:
        (output / 'candidate.json').write_text(json.dumps({
            'publication': 'candidate',
            'publishable': False,
            'reason': 'Built from a working tree snapshot; public publication requires a clean tagged release.',
            'version': version,
            'commit': commit,
            'dirty': dirty,
            'source_digest': manifest['source_digest'],
            'artifacts': {name: value for name, value in sorted(
                {path.name: digest(path) for path in output.iterdir() if path.is_file()}.items())},
        }, indent=2) + '\n')
        sums += f"{digest(output / 'candidate.json')}  candidate.json\n"
        (output / 'SHA256SUMS').write_text(sums)
    print(json.dumps({'version': version, 'commit': commit, 'publication': publication,
                      'dirty': dirty, 'output': str(output)}))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--candidate', action='store_true', help='Package the working tree as a local candidate.')
    parser.add_argument('--mcp-only', action='store_true', help='Produce a local MCP review tarball only.')
    parser.add_argument('--tag')
    parser.add_argument('--output', type=Path, default=ROOT / '.artifacts/dist')
    args = parser.parse_args()
    try:
        if args.preflight:
            preflight(args.tag, args.candidate)
            print('Release source preflight passed.')
        elif args.mcp_only:
            product, _ = settings()
            args.output.mkdir(parents=True, exist_ok=True)
            print(json.dumps(pack_mcp(args.output.resolve(), product['version'])))
        else:
            if not args.tag and not args.candidate:
                raise ValueError('Supply --tag for a release or --candidate for a local build.')
            assemble(args.output.resolve(), args.tag, args.candidate)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
