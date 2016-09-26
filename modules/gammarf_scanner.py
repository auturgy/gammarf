#!/usr/bin/env python2
# gammarf scanner module v0.1
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


from __future__ import division

import abc
import json
import os
import socket
import threading
import time
from collections import OrderedDict
from hashlib import md5
from multiprocessing import Pipe, Process
from subprocess import Popen, PIPE, STDOUT
from sys import builtin_module_names
from uuid import uuid4

from gammarf_base import GrfModuleBase

AVG_SAMPLES = 150  # how many samples to avg before looking for hits
CROP = 15  # %
DEFAULT_GAIN = 8.7
ERROR_SLEEP = 3
DEFAULT_HIT_DB = 9.0
INTEGRATION_INTERVAL = 5  # group time into chunks of this many seconds
MODULE_DESCRIPTION = "scanner module"
REPORTER_SLEEP = 50/1000  # limit activity reporting so as not to saturate the server
THREAD_TIMEOUT = 3

procs = list()


def start(config):
    return GrfModuleScanner(config)


class Reporter(Process):
    def __init__(self, reporter_opts, in_pipe, settings):
        self.station_id = reporter_opts['station_id']
        self.station_pass = reporter_opts['station_pass']
        self.server_host = reporter_opts['server_host']
        self.server_port = reporter_opts['server_port']
        self.agf = reporter_opts['agf']
        self.freqmap = dict()
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.in_pipe = in_pipe

        self.settings = dict()
        for setting, default in settings.items():
            self.settings[setting] = default

        super(Reporter, self).__init__()

    def run(self):
        while self.running:
            (op, args) = self.in_pipe.recv()

            if op == "stop":
                self.running = False
                continue

            if op == "toggle":
                self.settings[args[0]] = args[1]
                continue

            freq, pwr, step, gain, loc, jobid, ct = args
            try:
                avg, count = self.freqmap[freq]
            except KeyError:
                self.freqmap[freq] = (pwr, 1)
                continue

            threshold = avg + self.settings['hit_db']

            if self.settings['print_all']:
                print("[scanner] Freq: {}, Power: {}, Threshold: {}, Step: {}, Loc: {}, Count: {}, JobId: {}".format(freq, pwr, threshold, step, loc, count, jobid))

            if pwr > threshold and (count > AVG_SAMPLES or count == "done"):
                if self.settings['print_hits']:
                    print("[scanner] Hit on {} ({} > {})".format(freq, pwr, threshold))

                if self.settings['alert_on'] and \
                        (freq > self.settings['alert_center'] - self.settings['alert_bw'] and freq < self.settings['alert_center'] + self.settings['alert_bw']):
                            print("[scanner] ALERT: {} {} at {}".format(freq, pwr, time.strftime("%c")))

                overpct = "{:.3f}".format(abs( ( (pwr - avg)/avg )*100 ))
                self.send_hit(freq, pwr, overpct, step, gain, loc, jobid, ct)
                time.sleep(REPORTER_SLEEP)

            avg -= avg/AVG_SAMPLES
            avg += pwr/AVG_SAMPLES
            self.freqmap[freq] = (avg, count + 1 if (count != "done" and count < AVG_SAMPLES) else "done")

        return

    def send_hit(self, freq, pwr, overpct, step, gain, loc, jobid, ct):
        data = OrderedDict()
        data['stationid'] = self.station_id
        data['lat'] = loc['lat']
        data['lng'] = loc['lng']
        data['agf'] = str(self.agf)
        data['freq'] = str(freq)
        data['pwr'] = str(pwr)
        data['overpct'] = str(overpct)
        data['step'] = str(step)
        data['gain'] = str(gain)
        data['module'] = 'scanner'
        data['jobid'] = jobid
        data['ct'] = ct

        # just basic sanity
        data['time'] = str(int(time.time()))
        m = md5()
        m.update(self.station_pass + str(data['pwr']) + data['time'])
        data['sign'] = m.hexdigest()

        self.socket.sendto(json.dumps(data), (self.server_host, self.server_port))


class Scanner(threading.Thread):
    def __init__(self, scanner_opts, reporter, reporter_pipe, gpsp, devmod):
        global procs

        self.devnum = scanner_opts['devnum']
        self.reporter = reporter
        self.reporter_pipe = reporter_pipe
        self.gpsp = gpsp
        self.devmod = devmod
        self.gain = scanner_opts['gain']
        self.uuid = scanner_opts['uuid']

        cmd = scanner_opts['cmd']
        freqs = scanner_opts['freqs']
        integration = scanner_opts['integration']
        ppm = scanner_opts['ppm']

        try:
            outfreqs = []
            lowfreq, highfreq, width = freqs.split(':')
            for f in [lowfreq, highfreq]:
                if f[len(f)-1] == 'M':
                    f = int(float(f[:len(f)-1])*1e6)
                elif f[len(f)-1] == 'k':
                    f = int(float(f[:len(f)-1])*1e3)
                else:
                    f = int(f)
                outfreqs.append(f)
        except Exception:
            print("Error parsing frequency string")
            return

        fstr = "{}:{}:{}".format(str(outfreqs[0]), str(outfreqs[1]), width)
        ON_POSIX = 'posix' in builtin_module_names 
        self.cmdpipe = Popen([cmd, "-d {}".format(self.devnum), "-f {}".format(fstr),   #freqs
                "-i {}".format(integration), "-p {}".format(ppm), "-g {}".format(self.gain),
                "-c {}%".format(CROP)],
                stdout=PIPE, stderr=STDOUT, close_fds=ON_POSIX)

        procs.append(self.cmdpipe)

        self.stoprequest = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        while not self.stoprequest.isSet():
            data = self.cmdpipe.stdout.readline()

            if len(data) == 0:
                try:
                    continue
                except Exception:
                    return

            # look for gps here to avoid flooding the reporter in the case of no lock
            loc = self.gpsp.get_current()
            if (loc == None) or (loc['lat'] == "0.0" and loc['lng'] == "0.0") or (loc['lat'] == "NaN"):
                print("[scanner] No GPS loc, waiting...")
                time.sleep(ERROR_SLEEP)
                continue

            for raw in data.split('\n'):
                if len(raw) == 0:
                    continue

                if len(raw.split(' ')[0].split('-')) != 3:  # line irrelevant, or from stderr
                    if raw == "Error: dropped samples.":
                        print("[scanner] Error with device {}, exiting task".format(self.devnum))
                        self.devmod.removedev(self.devnum)
                        return
                    continue

                try:
                    _, _, freq_low, freq_high, step, _samples, raw_readings = raw.split(', ', 6)
                    freq_low = float(freq_low)
                    step = float(step)

                    readings = [x.strip() for x in raw_readings.split(',')]

                except:
                    print("[scanner] Thread exiting on exception")
                    return

                ct = int(round(time.time() * 1000))
                for i in range(len(readings)):
                    freq = int(round(freq_low + (step * i)))
                    pwr = float(readings[i])
                    self.reporter_pipe.send( ("data", (freq, pwr, step, self.gain, loc, self.uuid, ct) ) )

        self.cmdpipe.stdout.close()
        self.cmdpipe.kill()
        os.kill(self.cmdpipe.pid, 9)
        os.wait()
        
        procs.remove(self.cmdpipe)

        return

    def join(self, timeout=None):
        self.stoprequest.set()
        super(Scanner, self).join(timeout)


class GrfModuleScanner(GrfModuleBase):
    def __init__(self, config):
        rtl_path = config.scanner.rtl_path
        if not isinstance(rtl_path, str) or not rtl_path:
            raise Exception("param 'rtl_path' not appropriately defined in config")

        command = rtl_path + '/' + 'rtl_power'
        if not os.path.isfile(command) or not os.access(command, os.X_OK):
            raise Exception("executable rtl_power not found in specified path")

        self.config = config
        self.cmd = command
        self.integration = INTEGRATION_INTERVAL
        self.agf = None
        self.scanners = list()
        self.reporter = None
        self.reporter_pipe = None

        self.settings = {'print_all': False,
                'print_hits': False,
                'hit_db': DEFAULT_HIT_DB,
                'alert_on': False,
                'alert_center': 0.0,
                'alert_bw': 5000.0}

        print("Loading {}".format(MODULE_DESCRIPTION))

    def help(self):
        print("Scanner: Report deviations in average power to the backend")
        print("")
        print("Usage: scanner rtl_devnum freqs")
        print("\tWhere freqs is a frequency range in rtl_power format.")
        print("\tExample: > run scanner 0 200M:300M:15k")
        print("")
        print("\tSettings:")
        print("\t\talert_x: Print an alert when there's a hit in a limited bandwidth around a specific frequency")
        print("\t\tprint_all: Print all readings")
        print("\t\tprint_hits: Print hits")
        print("\t\thit_db: Power is required to be this high above the average (dB) to be considered a hit")
        return True

    def run(self, devnum, freqs, system_params, loadedmods, remotetask=False):
        self.remotetask = remotetask

        devmod = loadedmods['devices']

        if not self.agf:
            self.agf = devmod.get_agf()

        # these things are done only once
        if not self.reporter:  # don't do in init -- what if the module's never used?
            reporter_opts = {'station_id': system_params['station_id'],
                    'server_host': system_params['server_host'],
                    'server_port': system_params['server_port'],
                    'station_pass': system_params['station_pass'],
                    'agf': self.agf}

            self.gpsworker = loadedmods['location'].gps_worker
            self.reporter_pipe, child_pipe = Pipe()
            reporter = Reporter(reporter_opts, child_pipe, self.settings)
            reporter.start()
            self.reporter = reporter


        if not freqs:
            print("Must include a frequency specification")
            return
        freqs = freqs.strip()
        if len(freqs.split(':')) != 3:
            print("Bad frequency specification")
            return

        stickgain = eval("self.config.scanner.gain{}".format(devnum))
        if isinstance(stickgain, str):
            gain = float(stickgain)
        else:
            gain = DEFAULT_GAIN

        scanner_opts = {'cmd': self.cmd,
                'devnum': devnum,
                'freqs': freqs,
                'integration': self.integration,
                'ppm': devmod.get_ppm(devnum),
                'gain': gain,
                'uuid': str(uuid4())}

        scanner = Scanner(scanner_opts, self.reporter, self.reporter_pipe, self.gpsworker, devmod)
        scanner.daemon = True
        scanner.start()
        self.scanners.append( (devnum, scanner) )

        print("Scanner added on device {}".format(devnum))
        print("NOTE: It takes awhile to gather samples to form an average, for new frequency ranges")

        return True

    def report(self):
        return

    def info(self):
        return

    def shutdown(self):
        global procs

        print("Shutting down scanner module(s)")
        try:  # if no module is running, this will cause an error
            self.reporter_pipe.send( ("stop", (None) ) )
            self.reporter.join()
        except:
            pass

        for scanner in self.scanners:
            devnum, thread = scanner
            thread.join(THREAD_TIMEOUT)

        for proc in procs:  # done b/c rtl_power keeps running in certain circumstances (low step sz)
            try:
                proc.stdout.close()
                proc.kill()
                os.kill(proc.pid, 9)
                os.wait()
            except:
                pass

        return

    def showconfig(self):
        return

    def setting(self, setting, arg=None):
        if not self.reporter_pipe:
            print("Module not ready")
            return True

        if setting == None:
            for setting, state in self.settings.items():
                print("{}: {} ({})".format(setting, state, type(state)))
            return True

        if setting == 0:
            return self.settings.keys()

        if setting not in self.settings.keys():
            return False

        if isinstance(self.settings[setting], bool):
            new = not self.settings[setting]
        elif not arg:
            print("Non-boolean setting requires an argument")
            return True
        else:
            if isinstance(self.settings[setting], int):
                new = int(arg)
            elif isinstance(self.settings[setting], float):
                new = float(arg)
            else:
                new = arg

        self.settings[setting] = new
        self.reporter_pipe.send( ("toggle", (setting, new) ) )

        return True

    def stop(self, devnum, devmod):
        for scanner in self.scanners:
            scanner_devnum, thread = scanner
            if scanner_devnum == devnum:
                thread.join(THREAD_TIMEOUT)

                if not self.remotetask:
                    devmod.freedev(devnum)

                self.scanners.remove( (scanner_devnum, thread) )
                return True

        return False

    def ispseudo(self):
        return False
