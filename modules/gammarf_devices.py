#!/usr/bin/env python
# gammarf devices module v0.1
#
# Joshua Davis (gammarf -*- covert.codes)
# http://gammarf.io
# Copyright(C) 2016
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import abc
import rtlsdr
from ctypes import c_ubyte, string_at
from time import sleep, strftime

from gammarf_base import GrfModuleBase

MODULE_DESCRIPTION = "devices module"


def start(config):
    return GrfModuleDevices(config)


class RtlDev(object):
    def __init__(self):
        self.devnum = 0
        self.name = None
        self.ppm = 0
        self.job = None
        self.usable = True
        self.serial = None
        self.reserved = False


class GrfModuleDevices(GrfModuleBase):
    def __init__(self, config):
        print("Loading {}".format(MODULE_DESCRIPTION))

        agf = config.devices.agf
        if not isinstance(agf, str) or not agf:
            agf = 0
        else:
            agf = int(agf)

        devs = dict()
        devnums = dict()
        self.devcount = rtlsdr.librtlsdr.rtlsdr_get_device_count()
        if self.devcount == 0:
            print("-- Found no usable devices")
            exit()

        for devnum in range(0, self.devcount):
            rtldev = RtlDev()
            rtldev.devnum = devnum

            buffer1 = (c_ubyte * 256)()
            buffer2 = (c_ubyte * 256)()
            serial = (c_ubyte * 256)()
            rtlsdr.librtlsdr.rtlsdr_get_device_usb_strings(devnum, buffer1, buffer2, serial)
            serial = string_at(serial)
            devname = "{} {} {}".format(devnum,
                    rtlsdr.librtlsdr.rtlsdr_get_device_name(devnum),
                    serial)
           
            rtldev.name = devname
            rtldev.serial = serial
            print devname

            stickppm = eval("config.devices.ppm{}".format(devnum))
            if isinstance(stickppm, str):
                rtldev.ppm = int(stickppm)

            devs[devnum] = rtldev

        self.agf = agf
        self.devs = devs

    def get_ppm(self, devnum):
        dev = self.devs[devnum]
        return dev.ppm

    def get_agf(self):
        return self.agf

    def isdev(self, devnum):
        if not self.devs.has_key(devnum):
            return False
        return True
        
    def get_devs(self):
        return [dtup[1].name for dtup in self.devs.items()]

    def occupied(self, devnum):
        if not self.devs.has_key(devnum):
            return False

        dev = self.devs[devnum]
        if dev.job:
            return True
        return False

    def occupy(self, devnum, module, cmdline=None, pseudo=False):
        if pseudo:
            if not self.devs.has_key(devnum):
                rtldev = RtlDev()
                rtldev.devnum = devnum
                rtldev.name = "{} Pseudo device".format(devnum)
                self.devs[devnum] = rtldev

        dev = self.devs[devnum]
        if dev.job or not dev.usable:
            return False
        dev.job = (module, cmdline, strftime("%c"))
        return True

    def devnum_to_module(self, devnum):
        if not self.occupied(devnum):
            return

        dev = self.devs[devnum]
        
        if not dev.usable:
            return

        module, _, _ = dev.job
        return module

    def freedev(self, devnum):
        dev = self.devs[devnum]
        dev.job = None
        return

    def removedev(self, devnum):
        dev = self.devs[devnum]
        dev.job = "*** Out of commission"
        dev.usable = False
        return

    def reserve(self, devnum):
        if devnum in self.devs:
            dev = self.devs[devnum]
            dev.reserved = True
            dev.job = "*** Reserved"
        return

    def unreserve(self, devnum):
        dev = self.devs[devnum]
        dev.reserved = False
        dev.job = None
        return

    def reserved(self, devnum):
        dev = self.devs[devnum]
        return dev.reserved

    # ABC functions
    def help(self):
        return

    def run(self, cmdline, system_params):
        return

    def report(self):
        return

    def info(self):
        for devtuple in self.devs.items():
            dev = devtuple[1]
            print("{} - {}".format(dev.name, dev.job if dev.job else "Unoccupied"))

    def shutdown(self):
        return

    def showconfig(self):
        print("AGF: {}".format(self.agf))

    def setting(self, setting):
        return

    def stop(self, devnum, devmod):
        return

    def ispseudo(self):
        return False
