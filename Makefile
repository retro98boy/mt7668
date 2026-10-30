ifneq ($(KERNELRELEASE),)
obj-m += MT7668-WiFi/drv_wlan/MT6632/wlan/
obj-m += MT7668-Bluetooth/
else
KDIR ?= /lib/modules/$(shell uname -r)/build

.PHONY: all modules clean
all: modules

modules:
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" modules

clean:
	$(MAKE) -C "$(KDIR)" M="$(CURDIR)" clean
endif
