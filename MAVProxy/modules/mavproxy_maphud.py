#!/usr/bin/env python3
'''
Telemetry HUD overlay for MAVProxy map

Displays flight mode, ALT, AS, GS, Thr, battery voltage,
wind, and distance to home in the top-left corner of the map.

Load with: module load maphud
Toggle with: maphud on|off
'''

import time
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
        self.last_status_text = None
        self.last_status_time = 0
        self.last_status_severity = 6
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

    def _tracker_lines(self):
        '''return bearing from home to aircraft for manual antenna tracking'''
        if self.lat is None:
            return []
        wp = self.module('wp')
        if wp is None:
            return []
        home = wp.get_home()
        if home is None:
            return []
        bearing = mp_util.gps_bearing(home.x, home.y, self.lat, self.lon)
        return [('AntBrg', '%5.0f deg' % bearing)]

    def _rf_horizon_lines(self):
        '''return RF horizon min altitude HUD line based on distance from home.
        Uses 4/3 effective Earth radius model: h_min = (d_km / 4.12)^2'''
        dist = self._home_dist()
        if dist is None or dist < 1:
            return []
        d_km = dist / 1000.0
        h_min = (d_km / 4.12) ** 2
        return [('AntHoriz', '%5.1fm min' % h_min)]

    def _severity_colour(self, severity):
        '''map MAVLink severity to BGR colour for SlipHUD.
        Uses bright saturated colours readable over dark satellite imagery.'''
        # 0-3: EMERGENCY/ALERT/CRITICAL/ERROR → bright red
        if severity <= 3:
            return (80, 80, 255)
        # 4: WARNING → bright yellow
        if severity == 4:
            return (80, 255, 255)
        # 5-7: NOTICE/INFO/DEBUG → WHITE
        return (255, 255, 255)

    def _severity_tag(self, severity):
        '''text tag for severity level (dual coding per MIL-STD-1472H 5.17.25.11)'''
        if severity <= 3:
            return '[ERR]'
        if severity == 4:
            return '[WARN]'
        return '[INFO]'

    def _status_text_lines(self):
        '''return last AP status message with age'''
        if self.last_status_text is None:
            return []
        age = int(time.time() - self.last_status_time)
        colour = self._severity_colour(self.last_status_severity)
        tag = self._severity_tag(self.last_status_severity)
        return [('MSG', '%s %s (%ds ago)' % (tag, self.last_status_text, age), colour)]

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
                home_dist=self._home_dist(),
                extra_lines=self._status_text_lines() + self._tracker_lines() + self._rf_horizon_lines()))

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
        elif mtype == 'STATUSTEXT':
            self.last_status_text = m.text
            self.last_status_time = time.time()
            self.last_status_severity = m.severity
            self._add_hud()
        elif mtype == 'HEARTBEAT':
            self._add_hud()


def init(mpstate):
    return MapHUD(mpstate)
