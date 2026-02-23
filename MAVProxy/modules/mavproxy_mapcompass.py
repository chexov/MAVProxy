#!/usr/bin/env python3
'''
Compass Rose overlay for MAVProxy map

Adds a compass rose with azimuth labels and a heading indicator line.

Load with: module load mapcompass
Toggle with: mapcompass on|off
'''

from MAVProxy.modules.lib import mp_module


class MapCompass(mp_module.MPModule):
    def __init__(self, mpstate):
        super(MapCompass, self).__init__(mpstate, "mapcompass", "compass rose overlay")
        self.add_command('mapcompass', self.cmd_mapcompass, "compass rose overlay", ['on', 'off'])
        self.enabled = True
        self.heading = None
        self.wind_dir = None
        self._add_compass()

    def cmd_mapcompass(self, args):
        if len(args) == 0 or args[0] not in ('on', 'off'):
            print("Usage: mapcompass <on|off>")
            return
        self.enabled = (args[0] == 'on')
        if self.enabled:
            self._add_compass()
            print("Compass rose enabled")
        else:
            self._remove_compass()
            print("Compass rose disabled")

    def _add_compass(self):
        from MAVProxy.modules.mavproxy_map import mp_slipmap
        for mp in self.module_matching('map*'):
            mp.map.add_object(mp_slipmap.SlipCompassRose(
                'compass_rose', layer=4, heading=self.heading,
                wind_dir=self.wind_dir))

    def _remove_compass(self):
        from MAVProxy.modules.mavproxy_map import mp_slipmap
        for mp in self.module_matching('map*'):
            mp.map.remove_object('compass_rose')

    def mavlink_packet(self, m):
        if not self.enabled:
            return
        mtype = m.get_type()
        if mtype == 'VFR_HUD':
            new_heading = m.heading
            if self.heading is None or abs(new_heading - self.heading) > 1:
                self.heading = new_heading
                self._add_compass()
        elif mtype == 'WIND':
            self.wind_dir = m.direction
            self._add_compass()


def init(mpstate):
    return MapCompass(mpstate)
