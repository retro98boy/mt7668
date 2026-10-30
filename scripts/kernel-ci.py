#!/usr/bin/env python3
"""Fetch pinned upstream kernels, build ARM64 modules, and report CI results."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'ci/kernels.json'
COMPONENTS = {
    'wifi': ('MT7668-WiFi/drv_wlan/MT6632/wlan', 'wlan_mt76x8_sdio'),
    'bluetooth': ('MT7668-Bluetooth', 'bt_mt7668'),
}


def entries():
    items = json.loads(MANIFEST.read_text())
    if not isinstance(items, list) or not 1 <= len(items) <= 256:
        raise ValueError('The kernel matrix must contain 1 to 256 entries')
    seen = set()
    for item in items:
        if (set(item) != {'version', 'sha256'} or
                not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', item['version']) or
                not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or
                item['version'] in seen):
            raise ValueError(f'Invalid or duplicate kernel entry: {item}')
        seen.add(item['version'])
    return items


def entry(version):
    return next(item for item in entries() if item['version'] == version)


def digest(path):
    with path.open('rb') as stream:
        value = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
        return value.hexdigest()


def fetch(args):
    item = entry(args.version)
    cache, source = args.cache.resolve(), args.source.resolve()
    if source.exists():
        raise ValueError(f'Source destination already exists: {source}')
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f'linux-{args.version}.tar.xz'
    if archive.exists() and digest(archive) != item['sha256']:
        archive.unlink()
    if not archive.exists():
        url = (f'https://cdn.kernel.org/pub/linux/kernel/v{args.version.split(".")[0]}.x/'
               f'{archive.name}')
        partial = archive.with_suffix('.xz.part')
        subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location', '--retry', '3',
                        '--connect-timeout', '30', '--max-time', '900',
                        '--output', str(partial), url], check=True)
        if digest(partial) != item['sha256']:
            partial.unlink()
            raise ValueError(f'SHA256 mismatch for {url}')
        partial.replace(archive)
    source.mkdir(parents=True)
    subprocess.run(['tar', '-xJf', str(archive), '--strip-components=1',
                    '-C', str(source)], check=True)
    (source / '.mt7668-ci-source.json').write_text(json.dumps(item) + '\n')
    print(f'Verified and extracted Linux {args.version}: {item["sha256"]}')


def run(command, log):
    print(f'Running {log.name}: {" ".join(map(str, command))}', flush=True)
    with log.open('w') as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)


def build(args):
    item = entry(args.version)
    source, output = args.source.resolve(), args.output.resolve()
    kernel = (args.kernel_output or output / 'kernel').resolve()
    for destination in [output, kernel]:
        if any(parent == destination or destination in parent.parents
               for parent in [ROOT, source]):
            raise ValueError('Build output must not contain the repository or kernel sources')
    logs = output / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').unlink(missing_ok=True)
    if (output / 'modules').exists():
        shutil.rmtree(output / 'modules')
    report = {
        'version': args.version, 'architecture': 'arm64',
        'driver_commit': None,
        'source_verified': False, 'source_sha256': None,
        'kernel': 'NOT RUN', 'modules': 'NOT RUN', 'result': 'FAIL',
    }
    phase = 'configuration'
    try:
        report['driver_commit'] = subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
        marker = source / '.mt7668-ci-source.json'
        if marker.exists():
            if json.loads(marker.read_text()) != item:
                raise ValueError('Extracted kernel does not match the manifest')
            report.update(source_verified=True, source_sha256=item['sha256'])
        cross = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
        report['compiler'] = subprocess.check_output(
            [cross + 'gcc', '--version'], text=True).splitlines()[0]
        kernel.mkdir(parents=True, exist_ok=True)
        make = ['make', '-C', str(source), f'O={kernel}', 'ARCH=arm64',
                f'CROSS_COMPILE={cross}', 'LOCALVERSION=-mt7668-compat',
                'KBUILD_MODPOST_WARN=']
        run(make + [f'KCONFIG_ALLCONFIG={ROOT / "ci/arm64.config"}', 'allnoconfig'],
            logs / 'config.log')
        config = (kernel / '.config').read_text()
        for symbol in ['MODULES', 'MODULE_UNLOAD', 'MODVERSIONS', 'CFG80211',
                       'CFG80211_WEXT', 'BT', 'MMC', 'GPIOLIB', 'FW_LOADER']:
            if not re.search(rf'^CONFIG_{symbol}=[ym]$', config, re.M):
                raise ValueError(f'Missing CONFIG_{symbol}')
        release = subprocess.check_output(make + ['-s', 'kernelrelease'], text=True).strip()
        base = args.version + ('.0' if args.version.count('.') == 1 else '')
        if release != base + '-mt7668-compat':
            raise ValueError(f'Unexpected kernel release: {release}')
        report['kernel_release'] = release
        phase = 'kernel'
        run(make + [f'-j{args.jobs}', 'vmlinux', 'modules'], logs / 'kernel.log')
        for name in ['vmlinux', 'Module.symvers']:
            if not (kernel / name).is_file() or not (kernel / name).stat().st_size:
                raise ValueError(f'Kernel build did not produce {name}')
        report.update(kernel='PASS', config_sha256=digest(kernel / '.config'),
                      symvers_sha256=digest(kernel / 'Module.symvers'))
        phase = 'modules'
        driver = output / 'driver'
        if driver.exists():
            shutil.rmtree(driver)
        driver.mkdir()
        shutil.copy2(ROOT / 'Makefile', driver / 'Makefile')
        for directory, _ in COMPONENTS.values():
            shutil.copytree(ROOT / directory, driver / directory,
                            ignore=shutil.ignore_patterns('*.o', '*.o.*', '*.ko', '*.mod',
                                '*.mod.c', '.*.cmd', 'Module.symvers', 'modules.order',
                                '.tmp_versions'))
        run(['make', '-C', str(driver), f'KDIR={kernel}', 'ARCH=arm64',
             f'CROSS_COMPILE={cross}', 'KBUILD_MODPOST_WARN=', f'-j{args.jobs}'],
            logs / 'modules.log')
        if re.search(r'(WARNING|ERROR): modpost:', (logs / 'modules.log').read_text()):
            raise ValueError('Driver modpost reported warnings or errors')
        artifacts = output / 'modules'
        artifacts.mkdir(exist_ok=True)
        report['module_details'] = {}
        for component, (directory, name) in COMPONENTS.items():
            module = driver / directory / (name + '.ko')
            with module.open('rb') as stream:
                header = stream.read(20)
            if header[:6] != b'\x7fELF\x02\x01' or int.from_bytes(header[18:20], 'little') != 183:
                raise ValueError(f'{name} is not an ARM64 module')
            vermagic = subprocess.check_output(
                ['modinfo', '-F', 'vermagic', str(module)], text=True).strip()
            if vermagic.split()[0] != release:
                raise ValueError(f'{name} vermagic mismatch: {vermagic}')
            if subprocess.check_output(['modinfo', '-F', 'name', str(module)], text=True).strip() != name:
                raise ValueError(f'Unexpected module name: {module}')
            shutil.copy2(module, artifacts / module.name)
            report['module_details'][component] = {
                'name': name, 'vermagic': vermagic, 'sha256': digest(module),
                'compile_and_modpost': 'PASS',
            }
        report.update(modules='PASS', result='PASS')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        report.update(failed_stage=phase, error=str(error))
        if phase in ['kernel', 'modules']:
            report[phase] = 'FAIL'
        log = logs / {'configuration': 'config.log', 'kernel': 'kernel.log',
                      'modules': 'modules.log'}[phase]
        if log.exists():
            print('\n'.join(log.read_text(errors='replace').splitlines()[-80:]), file=sys.stderr)
        print(f'Linux {args.version} {phase}: {error}', file=sys.stderr)
    finally:
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(f'Linux {args.version}: {report["result"]}', flush=True)
    return 0 if report['result'] == 'PASS' else 1


def summarize(args):
    versions = args.versions or [item['version'] for item in entries()]
    print('| Linux / ARM64 | Kernel | WiFi + Bluetooth / modpost | Result |')
    print('| --- | --- | --- | --- |')
    success = True
    reports = {}
    for path in args.results.rglob('result.json'):
        report = json.loads(path.read_text())
        reports.setdefault(report['version'], []).append(report)
    for version in versions:
        entry(version)
        candidates = reports.get(version, [])
        if len(candidates) != 1:
            reason = 'missing result' if not candidates else 'duplicate results'
            print(f'| {version} | NOT RUN | NOT RUN | FAIL: {reason} |')
            success = False
            continue
        result = candidates[0]
        passed = result['version'] == version and result['result'] == 'PASS'
        passed = passed and result['kernel'] == result['modules'] == 'PASS'
        details = result.get('module_details', {})
        passed = passed and set(details) == set(COMPONENTS)
        passed = passed and all(details.get(name, {}).get('compile_and_modpost') == 'PASS'
                                for name in COMPONENTS)
        success = success and passed
        print(f'| {version} | {result["kernel"]} | {result["modules"]} | '
              f'{"PASS" if passed else "FAIL"} |')
    return 0 if success else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('matrix')
    prepare = commands.add_parser('fetch')
    prepare.add_argument('version')
    prepare.add_argument('cache', type=Path)
    prepare.add_argument('source', type=Path)
    compile_kernel = commands.add_parser('build')
    compile_kernel.add_argument('version')
    compile_kernel.add_argument('source', type=Path)
    compile_kernel.add_argument('output', type=Path)
    compile_kernel.add_argument('--kernel-output', type=Path,
                                help='Reuse a local kernel build directory; CI uses a fresh one')
    compile_kernel.add_argument('--jobs', type=int, default=2)
    summary = commands.add_parser('summary')
    summary.add_argument('results', type=Path)
    summary.add_argument('versions', nargs='*')
    args = parser.parse_args()
    if args.command == 'matrix':
        print(json.dumps({'include': entries()}, separators=(',', ':')))
    elif args.command == 'fetch':
        fetch(args)
    elif args.command == 'build':
        if args.jobs < 1:
            parser.error('--jobs must be positive')
        return build(args)
    else:
        return summarize(args)
    return 0


if __name__ == '__main__':
    sys.exit(main())
