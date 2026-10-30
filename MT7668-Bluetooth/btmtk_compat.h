/* SPDX-License-Identifier: GPL-2.0 */
#ifndef _BTMTK_COMPAT_H
#define _BTMTK_COMPAT_H

#include <linux/version.h>
#include <linux/device.h>
#include <linux/module.h>
#include <linux/mmc/core.h>

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 4, 0)
#define btmtk_class_create(name) class_create(name)
#else
#define btmtk_class_create(name) class_create(THIS_MODULE, name)
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 19, 0)
#define btmtk_reset_card(card) mmc_sw_reset(card)
#else
#define btmtk_reset_card(card) mmc_sw_reset((card)->host)
#endif

#endif
