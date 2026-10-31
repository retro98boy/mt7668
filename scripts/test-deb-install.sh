#!/bin/bash
# Run only in a disposable Debian/Ubuntu container with DKMS installed and no headers.
set -euo pipefail

if [ "$#" -ne 2 ]; then
    printf 'Usage: %s dkms.deb firmware.deb\n' "$0" >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ] || { [ ! -e /.dockerenv ] && [ ! -e /run/.containerenv ]; }; then
    printf 'Run this installation test as root in a disposable container.\n' >&2
    exit 1
fi

package=$(realpath "$1")
firmware_package=$(realpath "$2")
test "$(dpkg-deb -f "$package" Package)" = mt7668-dkms
test "$(dpkg-deb -f "$package" Architecture)" = all
test "$(dpkg-deb -f "$firmware_package" Package)" = mt7668-firmware
test "$(dpkg-deb -f "$firmware_package" Architecture)" = all
version=$(dpkg-deb -f "$package" Version)
test "$(dpkg-deb -f "$firmware_package" Version)" = "$version"
for name in mt7668-dkms mt7668-firmware; do
    if dpkg-query -W -f='${Status}' "$name" 2>/dev/null | grep -q ' installed$'; then
        printf '%s is already installed; use a fresh container.\n' "$name" >&2
        exit 1
    fi
done

# Validate both archive members, including builds made with newer dpkg versions.
for archive in "$package" "$firmware_package"; do
    for field in Pre-Depends Depends Recommends; do
        case "$(dpkg-deb -f "$archive" "$field")" in
            *mt7668-dkms*|*mt7668-firmware*)
                printf 'Unexpected package relationship in %s: %s\n' "$archive" "$field" >&2
                exit 1
                ;;
        esac
    done
    members=$(ar t "$archive")
    printf '%s\n' "$members" | grep -Fx control.tar.xz
    printf '%s\n' "$members" | grep -Fx data.tar.xz
done

firmware_files=(
    /lib/firmware/WIFI_RAM_CODE_MT7668.bin
    /lib/firmware/WIFI_RAM_CODE2_SDIO_MT7668.bin
    /lib/firmware/mt7668_patch_e0_hdr.bin
    /lib/firmware/mt7668_patch_e1_hdr.bin
    /lib/firmware/mt7668_patch_e2_hdr.bin
    /lib/firmware/TxPwrLimit_MT76x8.dat
    /lib/firmware/wifi.cfg
)
override=/lib/firmware/updates/WIFI_RAM_CODE_MT7668.bin
test ! -e "$override"
mkdir -p "$(dirname "$override")"
printf 'local factory firmware override\n' > "$override"

export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends "$firmware_package"
test "$(dpkg-query -W -f='${Version}' mt7668-firmware)" = "$version"
for file in "${firmware_files[@]}"; do test -f "$file"; done
(
    cd /
    grep '  lib/firmware/' /var/lib/dpkg/info/mt7668-firmware.md5sums | md5sum -c
)
test -z "$(dkms status -m mt7668 -v "$version")"
test ! -e "/usr/src/mt7668-$version"
grep -Fx 'local factory firmware override' "$override"

apt-get install -y --no-install-recommends "$package"
test "$(dpkg-query -W -f='${Version}' mt7668-dkms)" = "$version"
test -f "/usr/src/mt7668-$version/MT7668-WiFi/drv_wlan/MT6632/wlan/Makefile"
test -f "/usr/src/mt7668-$version/MT7668-Bluetooth/Makefile"
grep -Fx "PACKAGE_VERSION=\"$version\"" "/usr/src/mt7668-$version/dkms.conf"
dkms status -m mt7668 -v "$version" | grep ': added$'

apt-get purge -y mt7668-dkms
test -z "$(dkms status -m mt7668 -v "$version")"
test ! -e "/usr/src/mt7668-$version"
test ! -e "/var/lib/dkms/mt7668/$version"
test "$(dpkg-query -W -f='${Version}' mt7668-firmware)" = "$version"
for file in "${firmware_files[@]}"; do test -f "$file"; done
apt-get purge -y mt7668-firmware
for file in "${firmware_files[@]}"; do test ! -e "$file"; done
grep -Fx 'local factory firmware override' "$override"
rm "$override"
printf 'PASS: both packages install and purge independently; local firmware override preserved (%s)\n' "$(dkms --version)"
