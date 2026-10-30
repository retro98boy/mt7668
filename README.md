# MT7668 SDIO WiFi and Bluetooth

Out-of-tree Linux SDIO drivers for MediaTek MT7668. **The driver code was imported from [CoreELEC/MT7668](https://github.com/CoreELEC/MT7668.git)** and is maintained here with kernel compatibility updates and DKMS packaging.

| Function | Module | Source directory |
| --- | --- | --- |
| WiFi | `wlan_mt76x8_sdio` | `MT7668-WiFi/drv_wlan/MT6632/wlan` |
| Bluetooth | `bt_mt7668` | `MT7668-Bluetooth` |

The top-level build and Debian package select the **SDIO** drivers.

## Kernel compatibility and validation

Both modules passed complete ARM64 compilation and modpost against all **29 upstream base releases** listed below. Kernel API differences are handled by version macros in the driver.

| Kernel series | Releases with successful ARM64 builds |
| --- | --- |
| 5.x | 5.15, 5.16, 5.17, 5.18, 5.19 |
| 6.x | 6.0, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 6.12, 6.13, 6.14, 6.15, 6.16, 6.17, 6.18, 6.19 |
| 7.x | 7.0, 7.1, 7.2, 7.3 |

These checks cover each upstream `.0` release, rather than every stable patch release or distribution backport. GitHub Actions now tests a reduced matrix covering the main API branches; the table above records the earlier full-range validation. Both modules also passed a native AMD64 DKMS build against Debian's `6.1.0-54-amd64` headers (Linux 6.1.190). The TDLS API backport introduced in Linux 6.1.189 is accounted for.

On a TY1608 / S905X board, meson64 **6.18 and 7.3** were tested with concurrent dual-band WiFi and BLE scans, remain-on-channel operations, and unload/reload cycles. WiFi association/data transfer and Bluetooth pairing have not been validated. A successful build alone does not establish hardware support on another board.

The maintained kernel range is **5.15 through 7.3**. DKMS automatically skips kernels outside this range. Matching headers and suitable kernel configuration remain required.

## Debian / Ubuntu package compatibility

The same `Architecture: all` DKMS source package is checked for installation, DKMS registration, and complete removal on:

| Distribution | Package compatibility checks |
| --- | --- |
| Debian | 11 (Bullseye), 12 (Bookworm), 13 (Trixie) |
| Ubuntu LTS | 20.04 (Focal), 22.04 (Jammy), 24.04 (Noble), 26.04 (Resolute) |

These checks use each distribution's own `dpkg`, APT, and DKMS. GitHub Actions repeats this matrix for every build. The Bookworm build job additionally compiles and installs both modules against its distribution kernel headers before removing them.

The package uses **xz for both control and data archives**, debhelper compatibility level 12, and DKMS configuration understood by older DKMS releases. Its sources have no build-host libc dependency. Firmware, prebuilt modules, device-tree changes, module blacklists, and automatic module-loading configuration are not included.

Distribution compatibility and kernel compatibility are separate requirements. For example, the stock Linux 5.4 kernel in Ubuntu 20.04 and Linux 5.10 kernel in Debian 11 are outside the supported range: use a suitable newer kernel and its matching headers. A newer kernel may also require a newer compiler than the distribution's default compiler. Armbian systems need headers from the same Armbian kernel build.

### Install

Install the headers matching the **full target kernel release**, and provide the required firmware before installing the package:

```sh
sudo apt install ./mt7668-dkms_*.deb
dkms status
```

Header package names depend on your kernel provider. A custom kernel needs a prepared external-module build tree, including `.config`, generated headers, and `Module.symvers`. Enable module support, MMC/SDIO, CFG80211, wireless extensions, Bluetooth, GPIO, and firmware loading.

Once the SDIO functions have enumerated and the Bluetooth driver has been selected:

```sh
sudo modprobe bt_mt7668
sudo modprobe wlan_mt76x8_sdio
ip link
bluetoothctl list
sudo dmesg | tail -n 100
```

The in-tree `btmtksdio` driver and the vendor `bt_mt7668` driver match the same Bluetooth SDIO function. Select one in your system configuration before loading it. If the in-tree driver is already bound, configure the intended driver and reboot before testing; avoid switching Bluetooth drivers while WiFi is active. This package builds the vendor Bluetooth driver, so patches intended for in-tree `btmtksdio` are not needed for this configuration.

DKMS rebuilds the modules when a supported kernel and its headers are installed. Package management does not actively load or forcibly unload drivers.

### Remove

```sh
sudo apt purge mt7668-dkms
```

DKMS removes the installed module files. Already loaded modules can remain active until reboot.

## Firmware and board configuration

WiFi firmware and configuration files are in `MT7668-WiFi/7668_firmware/`. Install the files appropriate for the chip revision in the system firmware search path, normally `/lib/firmware/`, following the filenames reported in the driver log:

- WiFi requests files such as `WIFI_RAM_CODE_MT7668*` and `WIFI_RAM_CODE2_SDIO_MT7668*`.
- The vendor Bluetooth driver requests `mt7668_patch_e*_hdr.bin`, also present in that directory.
- The in-tree Bluetooth driver's `mediatek/mt7668pr2h.bin` naming belongs to that separate driver.

Firmware retains its original provenance and licensing and is supplied by the distribution or board image, separately from this DKMS deb.

The board device tree must configure the SDIO controller, pinmux, power supplies, and reset signals correctly. Installing the package does not modify the device tree or boot partition.

## Build the modules

Build both modules from the repository root:

```sh
make KDIR=/lib/modules/$(uname -r)/build -j2
make KDIR=/lib/modules/$(uname -r)/build clean
```

Use `KDIR` to select another prepared kernel build tree. For ARM64 cross-compilation:

```sh
make KDIR=/path/to/prepared/kernel/build ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2
```

Outputs:

- `MT7668-WiFi/drv_wlan/MT6632/wlan/wlan_mt76x8_sdio.ko`
- `MT7668-Bluetooth/bt_mt7668.ko`

## Build the Debian package

Install the packaging tools on Debian / Ubuntu:

```sh
sudo apt install build-essential debhelper dkms git
```

If `dh_dkms` is not installed, also install `dh-dkms`. Older releases include this helper in `dkms`; newer releases provide it as a separate package.

From a clean checkout with all intended changes committed:

```sh
./scripts/build-deb.sh
# Optional output directory:
./scripts/build-deb.sh /path/to/output
```

The script exports HEAD with `git archive` and generates its changelog in a temporary directory, leaving the checkout intact. Outputs are a `.deb`, `.buildinfo`, `.changes`, and `SHA256SUMS`, normally in the ignored `dist/` directory.

A direct `dpkg-buildpackage -us -uc -b` uses the static version in `debian/changelog`. Use `scripts/build-deb.sh` for normal snapshot builds and releases.

## Automatic kernel build matrix

Every push (including tags), pull request, and manual run starts an independent job for each entry in [`ci/kernels.json`](ci/kernels.json). All triggers use the same six-version matrix:

| Kernel | Main API coverage |
| --- | --- |
| 5.15 | Minimum supported kernel and older networking / SDIO interfaces |
| 6.1 | Link-aware cfg80211 key operations and newer SDIO reset interface |
| 6.6 | New class / TDLS interfaces and the intermediate channel-switch notification signature |
| 6.12 | New beacon-update, radar / CAC and channel-switch interfaces |
| 6.18 | Timer deletion, TX link and radio-index changes |
| 7.3 | Current interface-object, remain-on-channel address and cookie interfaces |

This samples the main API shapes rather than every transition or combination. Pushes, release tags and manual runs all use this list; there is no larger release-only matrix.

Each job uses Debian Trixie's ARM64 cross-compiler and:

1. Downloads the official kernel.org source archive and verifies the SHA256 pinned in the manifest. The verified source archive is cached separately from the kernel build directory.
2. Restores a kernel build cache keyed by source SHA256, configuration, architecture, source/output paths, build-script content and toolchain versions. The saved configuration, `vmlinux` and `Module.symvers` hashes are checked before reuse.
3. On a cache miss, applies [`ci/arm64.config`](ci/arm64.config) using `allnoconfig` and builds `vmlinux` and kernel modules to generate a complete `Module.symvers`. On a valid cache hit, reuses the configuration and runs the kernel targets incrementally. Invalid managed build caches are discarded and rebuilt. Build identity and timestamps are fixed to avoid unnecessary timestamp-only relinks.
4. Always copies fresh driver sources and rebuilds both SDIO drivers through the repository's top-level Makefile. Compilation, linking, or modpost failures fail the job. Missing symbols are not downgraded to warnings.
5. Verifies both `.ko` files are ARM64 modules with the expected names and kernel vermagic.

Actions displays one result per kernel and a combined **Kernel compatibility results** table. `result.json` records whether the kernel cache was reused. Completed kernel builds can be cached even when a later driver build fails; failed or incomplete kernel builds are not cached. Cache-service failures fall back to compilation without hiding build failures.

Each kernel uploads only `result.json` and logs as a `kernel-arm64-VERSION` artifact, retained for 7 days. Tag pushes and manual runs additionally save successfully validated drivers as a separate `modules-arm64-VERSION` artifact for 7 days. Normal pushes and pull requests do not upload driver modules or kernel binaries. Debian package artifacts remain available for installation checks and releases, also retained for 7 days.

A failure does not cancel the other kernel jobs. Missing results fail the combined report. Draft releases require the same six-version kernel matrix and the package checks to pass.

To extend the matrix, append a released kernel version and its archive SHA256 to `ci/kernels.json`. Obtain the checksum from kernel.org's `vMAJOR.x/sha256sums.asc`, selecting the exact `linux-VERSION.tar.xz` entry. The workflow expands the list automatically; no YAML matrix edits are needed. When extending the supported installation range, also update the kernel range in `dkms.conf` and the compatibility documentation after porting and validation.

Run the same build locally with the dependencies listed in the workflow:

```sh
python3 scripts/kernel-ci.py fetch 7.3 ci-cache ci-sources/7.3
python3 scripts/kernel-ci.py build 7.3 ci-sources/7.3 ci-results/7.3 --jobs 4 --keep-modules
python3 scripts/kernel-ci.py summary ci-results 7.3
```

For an existing local kernel source tree, run `build` directly with that source path. `--kernel-output /path/to/build` optionally uses a separate local kernel build directory. Repeating a build with the same inputs reuses a validated kernel build and recompiles the drivers. Omit `--keep-modules` when only results and logs are needed. Build results do not imply boot or hardware validation.

## Versions and GitHub releases

The package and DKMS version come from the source commit's UTC committer timestamp and 12-character SHA:

```text
YYYY.MM.DD.HHMMSS+git0123456789ab
```

```sh
./scripts/version.sh
./scripts/version.sh <commit-or-tag>
```

The same commit produces the same version. Keep release commit timestamps increasing: equal or decreasing timestamps do not guarantee Debian version ordering follows commit order.

`.github/workflows/build-deb.yml` handles:

- Pushes, pull requests, and manual runs: build all configured ARM64 kernels and both driver modules, build the deb, validate a native DKMS build and the distribution installation matrix, and upload artifacts.
- Numeric-leading tag pushes: require the tag to exactly match the generated version, pass the same checks, and create a **draft release** containing the deb and checksums.

After committing a release, create and push its tag:

```sh
version=$(./scripts/version.sh)
git tag "$version"
git push origin HEAD
git push origin "$version"
```

Review the Actions results and draft release on GitHub before publishing it. The workflow does not create tags or publish releases automatically.

## Provenance and licenses

Imported upstream repository: **https://github.com/CoreELEC/MT7668.git**.

The original MediaTek drivers and the PS4 / CoreELEC community ports retain their source-file copyright and license notices. WiFi files carry their original GPL-2.0 / BSD license choices; Bluetooth uses GPL-2.0, as documented in `MT7668-Bluetooth/LICENSE` and `COPYING`.

Thanks to novice4321, Reo Au In, [Khadas](https://github.com/khadas/android_hardware_wifi_mtk_drivers_mt7668/tree/Nougat), [noob404's PS4 port](https://github.com/noob404yt/mt7668-wifi-bt), and the CoreELEC community. Packaging was modeled on the `swt6621s` project.
