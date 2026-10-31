# MT7668 SDIO WiFi and Bluetooth

Linux SDIO WiFi and Bluetooth drivers for MediaTek MT7668, imported from [CoreELEC/MT7668](https://github.com/CoreELEC/MT7668.git), with kernel compatibility updates and DKMS packaging.

See the [CI matrix](ci/kernels.json) for tested kernel versions.

## Install

Install the headers matching your running kernel, then install both packages:

```sh
sudo apt install ./mt7668-dkms_*.deb ./mt7668-firmware_*.deb
```

DKMS rebuilds both modules when a supported kernel and its headers are installed.
The two packages can be installed independently; neither depends on or recommends the other.

Disable the kernel's `btmtksdio` driver as described below, then load the drivers:

```sh
sudo modprobe bt_mt7668
sudo modprobe wlan_mt76x8_sdio
```

To remove:

```sh
sudo apt purge mt7668-dkms mt7668-firmware
```

## Disable the kernel Bluetooth driver

`bt_mt7668` and the kernel's `btmtksdio` driver match the same SDIO Bluetooth function. Select the driver before loading it; reboot after changing this configuration.

For `CONFIG_BT_MTKSDIO=m`, block automatic loading and rebuild the initramfs:

```sh
echo 'blacklist btmtksdio' | sudo tee /etc/modprobe.d/mt7668.conf
sudo update-initramfs -u
sudo reboot
```

For `CONFIG_BT_MTKSDIO=y`, a module blacklist has no effect. Rebuild the kernel with `CONFIG_BT_MTKSDIO=n`, or add `initcall_blacklist=btmtksdio_driver_init` to the kernel command line and reboot. The boot parameter requires `CONFIG_KALLSYMS=y`.

## Firmware

The `mt7668-firmware` package installs this repository's SDIO WiFi and Bluetooth firmware and default configuration from [`MT7668-WiFi/7668_firmware/`](MT7668-WiFi/7668_firmware/) under `/lib/firmware/`.

Testing on a **Tianyi TY1608** with an **MT7668RSN** module found WiFi and Bluetooth signal quality acceptable. Compatible firmware optimized by your own device's manufacturer may give better results. Place local overrides under `/lib/firmware/updates/` using the filenames requested by the drivers.

## Build

With matching kernel headers installed:

```sh
make KDIR=/lib/modules/$(uname -r)/build -j2
```

For ARM64 cross-compilation, specify a prepared kernel build directory:

```sh
make KDIR=/path/to/kernel/build ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2
```

## Debian package

Install `build-essential`, `debhelper`, `dkms`, and `git`. Install `dh-dkms` separately if your system does not provide `dh_dkms` through `dkms`.

Build from a clean checkout with your changes committed:

```sh
./scripts/build-deb.sh
```

The `mt7668-dkms` and `mt7668-firmware` packages and their checksums are written to `dist/`.

## Versions and releases

Versions use the commit's UTC timestamp and short SHA: `YYYY.MM.DD.HHMMSS+git0123456789ab`. Print the current version with `./scripts/version.sh`.

Pushing a tag matching that version creates a draft GitHub release after the checks pass.

## License

The imported source retains its original copyright and license notices. See the individual source files and license files for details.
