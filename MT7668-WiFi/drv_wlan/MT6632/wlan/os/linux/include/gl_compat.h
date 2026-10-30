/* SPDX-License-Identifier: GPL-2.0 OR BSD-2-Clause */
#ifndef _GL_COMPAT_H
#define _GL_COMPAT_H

#include <linux/version.h>
#include <linux/sched/clock.h>

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 15, 0)
#define kalTimerDeleteSync(timer) timer_delete_sync(timer)
#else
#define kalTimerDeleteSync(timer) del_timer_sync(timer)
#endif

#if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 18, 0)
#define kalNetifRx(skb) netif_rx(skb)
#else
#define kalNetifRx(skb) (in_interrupt() ? netif_rx(skb) : netif_rx_ni(skb))
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 1, 0)
#define MTK_CFG_KEY_LINK_PARAM int link_id,
#else
#define MTK_CFG_KEY_LINK_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 0, 0)
#define MTK_CFG_STOP_LINK_PARAM , unsigned int link_id
#define MTK_CFG_BITRATE_LINK_PARAM unsigned int link_id,
#else
#define MTK_CFG_STOP_LINK_PARAM
#define MTK_CFG_BITRATE_LINK_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 5, 0)
#define MTK_CFG_TDLS_LINK_PARAM int link_id,
#else
#define MTK_CFG_TDLS_LINK_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 7, 0)
#define MTK_CFG_BEACON_UPDATE_TYPE cfg80211_ap_update
#define MTK_CFG_BEACON_DATA(update) (&(update)->beacon)
#define kalCfg80211ScanWidth(request) NL80211_BSS_CHAN_WIDTH_20
#else
#define MTK_CFG_BEACON_UPDATE_TYPE cfg80211_beacon_data
#define MTK_CFG_BEACON_DATA(update) (update)
#define kalCfg80211ScanWidth(request) ((request)->scan_width)
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 12, 0)
#define MTK_CFG_RADAR_LINK_PARAM , int link_id
#define kalCfg80211CacStarted(wdev) ((wdev)->links[0].cac_started)
#define kalCfg80211CacEvent(dev, chandef, event, gfp) \
	cfg80211_cac_event(dev, chandef, event, gfp, 0)
#else
#define MTK_CFG_RADAR_LINK_PARAM
#define kalCfg80211CacStarted(wdev) ((wdev)->cac_started)
#define kalCfg80211CacEvent(dev, chandef, event, gfp) \
	cfg80211_cac_event(dev, chandef, event, gfp)
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 14, 0)
#define MTK_CFG_TX_LINK_PARAM unsigned int link_id,
#else
#define MTK_CFG_TX_LINK_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 17, 0)
#define MTK_CFG_RADIO_PARAM int radio_idx,
#else
#define MTK_CFG_RADIO_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 9, 0)
#define kalCfg80211ChSwitchNotify(dev, chandef) \
	cfg80211_ch_switch_notify(dev, chandef, 0)
#elif CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 3, 0)
#define kalCfg80211ChSwitchNotify(dev, chandef) \
	cfg80211_ch_switch_notify(dev, chandef, 0, 0)
#elif CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 0, 0)
#define kalCfg80211ChSwitchNotify(dev, chandef) \
	cfg80211_ch_switch_notify(dev, chandef, 0)
#else
#define kalCfg80211ChSwitchNotify(dev, chandef) \
	cfg80211_ch_switch_notify(dev, chandef)
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(6, 0, 0)
#define kalCfg80211StationLink(params) (&(params)->link_sta_params)
#define kalCfg80211RoamLink(info) (&(info)->links[0])
#else
#define kalCfg80211StationLink(params) (params)
#define kalCfg80211RoamLink(info) (info)
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(7, 1, 0)
#define MTK_CFG_IFACE_TYPE wireless_dev
#define kalCfg80211Iface(dev) ((dev)->ieee80211_ptr)
#define kalCfg80211Netdev(iface) ((iface) ? (iface)->netdev : NULL)
#else
#define MTK_CFG_IFACE_TYPE net_device
#define kalCfg80211Iface(dev) (dev)
#define kalCfg80211Netdev(iface) (iface)
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(7, 2, 0)
#define MTK_CFG_ROC_ADDR_PARAM , const u8 *rx_addr
#else
#define MTK_CFG_ROC_ADDR_PARAM
#endif

#if CFG80211_VERSION_CODE >= KERNEL_VERSION(7, 3, 0)
#define MTK_CFG_COOKIE_PARAM u64 cookie
#define kalCfg80211CookieValid(cookie) true
#define kalCfg80211NextCookie(cookie, counter) (cookie)
#else
#define MTK_CFG_COOKIE_PARAM u64 *cookie
#define kalCfg80211CookieValid(cookie) ((cookie) != NULL)
#define kalCfg80211NextCookie(cookie, counter) (*(cookie) = (counter)++)
#endif

#endif
