#!/usr/bin/env python3
"""Fetch pinned upstream kernels, build ARM64 modules, and report CI results."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
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


def kernel_key(version, source, kernel):
    cross = os.environ.get('CROSS_COMPILE', 'aarch64-linux-gnu-')
    tools = {}
    for program in ['gcc', 'ld', 'make', cross + 'gcc', cross + 'ld']:
        tools[program] = subprocess.check_output([program, '--version'], text=True)
    settings = {
        'source': entry(version), 'architecture': 'arm64',
        'host_architecture': platform.machine(), 'tools': tools,
        'source_directory': str(source.resolve()), 'kernel_directory': str(kernel.resolve()),
        'config': digest(ROOT / 'ci/arm64.config'), 'builder': digest(Path(__file__)),
        'flags': {name: os.environ.get(name, '') for name in
                  ['KCFLAGS', 'KCPPFLAGS', 'HOSTCFLAGS', 'HOSTLDFLAGS', 'KBUILD_EXTRA_SYMBOLS']},
    }
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


def kernel_state(kernel, key):
    return {'key': key, 'files': {name: digest(kernel / name)
                                for name in ['.config', 'vmlinux', 'Module.symvers']}}


def kernel_cache_valid(kernel, key):
    try:
        saved = json.loads((kernel / '.mt7668-kernel.json').read_text())
        return saved == kernel_state(kernel, key)
    except (OSError, ValueError):
        return False


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
        'source_verified': False, 'source_sha256': None, 'kernel_cache_reused': False,
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
        key = kernel_key(args.version, source, kernel)
        reused = kernel_cache_valid(kernel, key)
        report.update(kernel_cache_key=key, kernel_cache_reused=reused)
        if not reused and kernel.exists() and args.kernel_output is None:
            shutil.rmtree(kernel)
        kernel.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.fromtimestamp((source / 'Makefile').stat().st_mtime,
                                           timezone.utc).strftime('%a %b %d %H:%M:%S UTC %Y')
        make = ['make', '-C', str(source), f'O={kernel}', 'ARCH=arm64',
                f'CROSS_COMPILE={cross}', 'LOCALVERSION=-mt7668-compat',
                'KBUILD_MODPOST_WARN=', 'KBUILD_BUILD_USER=mt7668', 'KBUILD_BUILD_HOST=ci',
                'KBUILD_BUILD_VERSION=1', f'KBUILD_BUILD_TIMESTAMP={timestamp}']
        if reused:
            (logs / 'config.log').write_text('Reusing verified kernel configuration and build.\n')
        else:
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
        stamp = kernel / '.mt7668-kernel.json'
        pending = stamp.with_suffix('.json.tmp')
        pending.write_text(json.dumps(kernel_state(kernel, key), sort_keys=True) + '\n')
        pending.replace(stamp)
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
        if args.keep_modules:
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
            if args.keep_modules:
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
    for command in ['cache-key', 'cache-ready']:
        cache = commands.add_parser(command)
        cache.add_argument('version')
        cache.add_argument('source', type=Path)
        cache.add_argument('kernel', type=Path)
    prepare = commands.add_parser('fetch')
    prepare.add_argument('version')
    prepare.add_argument('cache', type=Path)
    prepare.add_argument('source', type=Path)
    compile_kernel = commands.add_parser('build')
    compile_kernel.add_argument('version')
    compile_kernel.add_argument('source', type=Path)
    compile_kernel.add_argument('output', type=Path)
    compile_kernel.add_argument('--kernel-output', type=Path,
                                help='Use a separate local kernel build directory')
    compile_kernel.add_argument('--jobs', type=int, default=2)
    compile_kernel.add_argument('--keep-modules', action='store_true',
                                help='Copy validated modules into the artifact directory')
    summary = commands.add_parser('summary')
    summary.add_argument('results', type=Path)
    summary.add_argument('versions', nargs='*')
    args = parser.parse_args()
    if args.command == 'matrix':
        print(json.dumps({'include': entries()}, separators=(',', ':')))
    elif args.command in ['cache-key', 'cache-ready']:
        key = kernel_key(args.version, args.source, args.kernel)
        if args.command == 'cache-key':
            print(key)
        else:
            try:
                report = json.loads((args.kernel.parent / 'result.json').read_text())
                ready = report.get('kernel') == 'PASS' and report.get('kernel_cache_key') == key
            except (OSError, ValueError):
                ready = False
            print(str(ready and kernel_cache_valid(args.kernel, key)).lower())
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
