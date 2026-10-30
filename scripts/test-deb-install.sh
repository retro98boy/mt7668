#!/bin/bash
# Run only in a disposable Debian/Ubuntu container with DKMS installed and no headers.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    printf 'Usage: %s package.deb\n' "$0" >&2
    exit 2
fi
if [ "$(id -u)" -ne 0 ] || { [ ! -e /.dockerenv ] && [ ! -e /run/.containerenv ]; }; then
    printf 'Run this installation test as root in a disposable container.\n' >&2
    exit 1
fi

package=$(realpath "$1")
test "$(dpkg-deb -f "$package" Package)" = mt7668-dkms
test "$(dpkg-deb -f "$package" Architecture)" = all
version=$(dpkg-deb -f "$package" Version)
if dpkg-query -W -f='${Status}' mt7668-dkms 2>/dev/null | grep -q ' installed$'; then
    printf 'mt7668-dkms is already installed; use a fresh container.\n' >&2
    exit 1
fi

# Validate both archive members, including builds made with newer dpkg versions.
members=$(ar t "$package")
printf '%s\n' "$members" | grep -Fx control.tar.xz
printf '%s\n' "$members" | grep -Fx data.tar.xz

export DEBIAN_FRONTEND=noninteractive
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
printf 'PASS: package install, DKMS registration and purge (%s)\n' "$(dkms --version)"
