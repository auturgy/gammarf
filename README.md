GammaRF
=======

![GRF](grf.png)

 GammaRF is an original, cooperative, open-source project designed to bring together
   the radio enthusiast community in pursuit of ambitious goals.

 - Cooperate with users around the world to monitor the airwaves on a grand scale
 - Track aircraft, space objects, weather, public service vehicles, and so on
 - Participate in distributed HF Direction Finding (HF-DF) projects
 - ... and more.  The possibilities are endless.
  
See http://gammarf.io - for more information.
  
Installation
============

 - Use multi-core hardware.
  
0) Make sure you have Python 2.7 installed.  Install python-devel and/or libpython-all-dev,
    depending on your system.  Install the rtl-sdr applications (eg. apt-get install rtl-sdr),
    gpsd and gpsd-clients (package names may vary)

1) Make sure these Python modules (for Python 2.7+) are installed:
    iniparse 0.4, pyrtlsdr 0.2.3, python-gps 3.1.5,
    pyModeS for the adsb module,
    matplotlib and numpy for the freqwatch module

2) Get your GPS working and gpsd started.  For me, I had to disable gpsd on boot and
     start it manually for GammaRF:

        # gpsctl -f -n /dev/ttyUSB0
        # stty -F /dev/ttyUSB0 ispeed 4800
        # gpsd -b /dev/ttyUSB0

 
  http://www.catb.org/gpsd/installation.html is helpful.

  You can also hard-code your coordinates in the config, if you won't be moving around
    and you're sure you know them.

3) Register at http://gammarf.io.  Registration is required; don't worry; only
    a few pieces of non-private information are needed.  (If your node isn't registered,
    your data doesn't make it to the DB.)  Afterward, edit gammarf.conf to reflect the
    station ID and password you registered with

4) Change permissions on gammarf.conf so your password isn't visible to others

5) Run, and watch your data help at http://gammarf.io!  Additional modules and
    tools will show up on the website as they're developed

Tips
====

  * If you use a pi, compile rtl-sdr from source, instead of using the one installed by your package manager
