#!/usr/bin/env python3
'''
Telemetry HUD overlay for MAVProxy map

Displays flight mode, ALT, AS, GS, Thr, battery voltage,
wind, and distance to home in the top-left corner of the map.

Load with: module load maphud
Toggle with: maphud on|off
'''

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util


class MapHUD(mp_module.MPModule):
    def __init__(self, mpstate):
        super(MapHUD, self).__init__(mpstate, "maphud", "telemetry HUD overlay")
        self.add_command('maphud', self.cmd_maphud, "telemetry HUD overlay", ['on', 'off'])
        self.enabled = True
        self.alt = 0
        self.airspeed = 0
        self.groundspeed = 0
        self.throttle = 0
        self.bat_voltage = 0
        self.wind_dir = None
        self.wind_speed = 0
        self.amsl_alt = None
        self.lat = None
        self.lon = None
        self._add_hud()

    def cmd_maphud(self, args):
        if len(args) == 0 or args[0] not in ('on', 'off'):
            print("Usage: maphud <on|off>")
            return
        self.enabled = (args[0] == 'on')
        if self.enabled:
            self._add_hud()
            print("HUD enabled")
        else:
            self._remove_hud()
            print("HUD disabled")

    def _home_dist(self):
        '''compute distance to home, or None if unavailable'''
        if self.lat is None:
            return None
        wp = self.module('wp')
        if wp is None:
            return None
        home = wp.get_home()
        if home is None:
            return None
        return mp_util.gps_distance(self.lat, self.lon, home.x, home.y)

    def _add_hud(self):
        from MAVProxy.modules.mavproxy_map import mp_slipmap
        flightmode = self.master.flightmode if self.master else ''
        armed = self.mpstate.status.armed
        for mp in self.module_matching('map*'):
            mp.map.add_object(mp_slipmap.SlipHUD(
                'telemetry_hud', layer=4,
                alt=self.alt, amsl_alt=self.amsl_alt, airspeed=self.airspeed,
                groundspeed=self.groundspeed, throttle=self.throttle,
                bat_voltage=self.bat_voltage, flightmode=flightmode,
                armed=armed, wind_dir=self.wind_dir,
                wind_speed=self.wind_speed,
                home_dist=self._home_dist()))

    def _remove_hud(self):
        for mp in self.module_matching('map*'):
            mp.map.remove_object('telemetry_hud')

    def mavlink_packet(self, m):
        if not self.enabled:
            return
        mtype = m.get_type()
        if mtype == 'VFR_HUD':
            self.alt = m.alt
            self.airspeed = m.airspeed
            self.groundspeed = m.groundspeed
            self.throttle = m.throttle
            self._add_hud()
        elif mtype == 'SYS_STATUS':
            self.bat_voltage = m.voltage_battery * 0.001
            self._add_hud()
        elif mtype == 'WIND':
            self.wind_dir = m.direction
            self.wind_speed = m.speed
            self._add_hud()
        elif mtype == 'GLOBAL_POSITION_INT':
            self.amsl_alt = m.alt * 1.0e-3
            self.lat = m.lat * 1.0e-7
            self.lon = m.lon * 1.0e-7
            self._add_hud()
        elif mtype == 'HEARTBEAT':
            self._add_hud()


def init(mpstate):
    return MapHUD(mpstate)
