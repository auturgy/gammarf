#!/usr/bin/env python
# gammarf location module v0.1
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
import threading
from gps import *
from time import sleep

from gammarf_base import GrfModuleBase

ERROR_SLEEP = 5
MODULE_DESCRIPTION = "location module"


def start(config):
    return GrfModuleLocation(config)


class StaticGpsWorker():
    def __init__(self, gpslat, gpslng):
        self.lat = gpslat
        self.lng = gpslng

    def get_current(self):
        return {'lat': self.lat, 'lng': self.lng}


class GpsWorker(threading.Thread):
    def __init__(self):
        self.gpsd = gps(mode=WATCH_ENABLE)
        self.current = None
        self.loc = dict()

        self.running = True
        threading.Thread.__init__(self)

    def get_current(self):
        return self.loc

    def run(self):
        while self.running:
            try:
                self.gpsd.next()
                self.loc['lat'] = str(self.gpsd.fix.latitude)
                self.loc['lng'] = str(self.gpsd.fix.longitude)
                time.sleep(ERROR_SLEEP)

            except StopIteration:
                print("GPS error, sleeping...")
                sleep(ERROR_SLEEP)

            except Exception:
                print("GPS error, sleeping...")
                sleep(ERROR_SLEEP)

    def stop(self):
        self.running = False


class GrfModuleLocation(GrfModuleBase):
    def __init__(self, config):
        print("Loading {}".format(MODULE_DESCRIPTION))

        gps_params = dict()
        gps_params['staticloc_lat'] = config.location.lat
        gps_params['staticloc_lng'] = config.location.lng
        gps_params['usegps'] = config.location.usegps

        if not isinstance(gps_params['usegps'], str):
            raise Exception("param 'usegps' not appropriately defined in config")

        gps_params['usegps'] = int(gps_params['usegps'])

        if gps_params['usegps'] == 0:
            if not isinstance(gps_params['staticloc_lat'], str) or not gps_params['staticloc_lat'] or \
                    not isinstance(gps_params['staticloc_lng'], str) or not gps_params['staticloc_lng']:
                        raise Exception("GPS off, but static location not defined in config")

            gps_worker = StaticGpsWorker(gps_params['staticloc_lat'], gps_params['staticloc_lng'])
            print("-- Using static location")
        else:
            gps_worker = GpsWorker()
            gps_worker.daemon = True
            gps_worker.start()
            print("-- Using GPS")

        self.gps_params = gps_params
        self.gps_worker = gps_worker

    def help(self):
        return

    def run(self, cmdline, system_params, loadedmods):
        return

    def report(self):
        return self.gps_worker.get_current()

    def info(self):
        coords = self.gps_worker.get_current()
        lat = coords['lat']
        lon = coords['lng']
        print("Currently at Lat: {}, Long: {}".format(lat, lon))

    def shutdown(self):
        if self.gps_params['usegps'] != 0:
            print("Shutting down GPS")
            self.gps_worker.stop()

    def showconfig(self):
        if self.gps_params['usegps'] == 0:
            lat = self.gps_params['staticloc_lat']
            lon = self.gps_params['staticloc_lng']
            print("Using static location, Lat: {} Long: {}".format(lat, lon))
        else:
            fix = self.gps_worker.get_current()
            lat = fix['lat']
            lon = fix['lng']
            print("Using GPS, Lat: {} Long: {}".format(lat, lon))

    def setting(self, setting):
        return

    def stop(self, devnum, devmod):
        return

    def ispseudo(self):
        return False
