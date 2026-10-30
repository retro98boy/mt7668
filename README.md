# MT7668 SDIO WiFi / Bluetooth

MediaTek MT7668 的 Linux 树外 SDIO 驱动，包含两个模块：

| 功能 | 模块 | 源码 |
| --- | --- | --- |
| WiFi | `wlan_mt76x8_sdio` | `MT7668-WiFi/drv_wlan/MT6632/wlan` |
| Bluetooth | `bt_mt7668` | `MT7668-Bluetooth` |

当前维护范围是 Linux **5.15–7.3**，内核 API 差异通过驱动内的版本宏处理。
已完成该范围内全部 29 个主次版本基础发行版的 ARM64 编译检查，WiFi 和蓝牙均通过编译及 modpost；这不等同于所有版本的实机验证。
TY1608 / S905X 已在 meson64 6.18、7.3 上进行实机调试。其他板卡仍需配置 SDIO、供电、GPIO 和固件。

此打包入口选择 SDIO，不包含 USB 驱动构建。

## 安装 deb

先安装与**目标内核完整版本**匹配的 headers，以及所需固件，再安装生成的包：

```sh
sudo apt install ./mt7668-dkms_*.deb
dkms status
```

Debian / Ubuntu / Armbian 的 headers 包名取决于使用的内核来源。自编译内核必须提供完整的外部模块构建环境，包括 `.config`、生成的头文件和 `Module.symvers`。

`mt7668-dkms` 是 `Architecture: all` 的**源码包**。DKMS 在目标机器上构建并安装两个模块，升级内核时自动重新构建。它不携带预编译 `.ko`，也不安装固件、DTS、模块黑名单或开机加载配置，不主动加载或强制卸载模块。
DKMS 配置限制自动构建范围为 5.15–7.3；内核仍需启用模块、MMC/SDIO、CFG80211、无线扩展、Bluetooth、GPIO 和固件加载支持。

确认 SDIO 功能已经枚举、固件齐全，并选择好蓝牙驱动后，可手动加载：

```sh
sudo modprobe bt_mt7668
sudo modprobe wlan_mt76x8_sdio
ip link
bluetoothctl list
sudo dmesg | tail -n 100
```

树内 `btmtksdio` 和这里的 `bt_mt7668` 会匹配相同的蓝牙 SDIO 功能，只能选一个。若系统已绑定树内驱动，应先在系统配置中选定驱动，再重启验证；不要在 WiFi 工作时直接强制切换或卸载蓝牙驱动。
本包使用树外蓝牙，不需要为了它再叠加树内 `btmtksdio` 的 MT7668 补丁。

卸载包：

```sh
sudo apt purge mt7668-dkms
```

DKMS 会删除安装的模块文件。已经加载的模块可在重启后退出；包管理脚本不会强制卸载正在工作的驱动。

## 固件与板级配置

仓库中的 WiFi 固件和配置位于 `MT7668-WiFi/7668_firmware/`。请按芯片修订版本和驱动日志安装所需文件到系统固件搜索路径，一般为 `/lib/firmware/`。
WiFi 会请求 `WIFI_RAM_CODE_MT7668*`、`WIFI_RAM_CODE2_SDIO_MT7668*` 等文件；树外蓝牙会请求 `mt7668_patch_e*_hdr.bin`，同样可在该目录找到。
树内 `btmtksdio` 使用的 `mediatek/mt7668pr2h.bin` 是另一套驱动的文件命名，不要与这里的请求名称混淆。

固件保持原有来源和授权，由板级镜像或系统提供，不随 `mt7668-dkms` deb 分发。
设备树中还需要正确启用 SDIO 控制器、pinmux、供电及复位配置。安装驱动包不会修改启动分区或设备树。

## 从源码编译

在仓库根目录直接构建两个模块：

```sh
make KDIR=/lib/modules/$(uname -r)/build -j2
make KDIR=/lib/modules/$(uname -r)/build clean
```

指定 `KDIR` 可以为尚未启动的内核编译。ARM64 交叉编译示例：

```sh
make KDIR=/path/to/prepared/kernel/build ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j2
```

产物分别为：

- `MT7668-WiFi/drv_wlan/MT6632/wlan/wlan_mt76x8_sdio.ko`
- `MT7668-Bluetooth/bt_mt7668.ko`

## 构建 Debian 包

在 Debian / Ubuntu 环境安装打包依赖：

```sh
sudo apt install build-essential debhelper dkms dh-dkms git
bash scripts/build-deb.sh
```

脚本要求工作区干净，所有需要打包的修改已提交；默认输出到被 Git 忽略的 `dist/`，也可传入输出目录：

```sh
bash scripts/build-deb.sh /path/to/output
```

脚本通过 `git archive` 导出 HEAD，在临时目录生成 changelog 并构建，保留原工作区。输出 `.deb`、`.buildinfo`、`.changes` 和 `SHA256SUMS`。
直接运行 `dpkg-buildpackage -us -uc -b` 也能打包，但会使用 `debian/changelog` 的静态版本；日常构建和发布使用上述脚本。

## 版本与发布

统一版本来自提交的 UTC 时间和 12 位 Git SHA：

```text
YYYY.MM.DD.HHMMSS+git0123456789ab
```

```sh
bash scripts/version.sh          # HEAD
bash scripts/version.sh <commit> # 指定提交或 tag
```

同一提交生成相同版本，deb 版本和 DKMS 版本一致，无须手动维护第二份驱动版本变量。
时间取自提交的 committer timestamp；发布提交需要时间递增，同一秒或回退时间的提交不能保证 Debian 版本排序与提交顺序一致。

GitHub Actions 配置位于 `.github/workflows/build-deb.yml`：

- 分支 push、PR 和手动运行：构建 deb，在 Debian Bookworm 容器内用发行版 headers 验证两个模块的 DKMS 构建、安装及卸载，上传 artifact。
- 数字开头的 tag push：先要求 tag 精确等于生成版本，通过同样检查后创建带 deb 和校验文件的 **draft release**。
- 工作流不自动打 tag，不发布正式 release。

准备发布时，先提交修改，再给该提交打版本 tag 并推送：

```sh
version=$(bash scripts/version.sh)
git tag "$version"
git push origin HEAD
git push origin "$version"
```

到 GitHub 检查 Actions 和 draft release，确认后手动发布。

## 来源与许可

基于 MediaTek 驱动及 PS4 / CoreELEC 社区移植工作。WiFi 各文件保留原有 GPL-2.0 / BSD 双许可声明；Bluetooth 使用 GPL-2.0，见 `MT7668-Bluetooth/LICENSE` 和 `COPYING`。

感谢 novice4321、Reo Au In、[Khadas](https://github.com/khadas/android_hardware_wifi_mtk_drivers_mt7668/tree/Nougat)、[noob404 的 PS4 移植](https://github.com/noob404yt/mt7668-wifi-bt)以及 CoreELEC 社区。打包方式参考本地 `swt6621s` 项目。
