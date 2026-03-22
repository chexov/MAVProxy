#!/usr/bin/env python3
'''
Antenna tracker control module
This module catches MAVLINK_MSG_ID_GLOBAL_POSITION_INT
and sends them to a MAVlink connected antenna tracker running
ardupilot AntennaTracker
Mike McCauley, based on earlier work by Andrew Tridgell
June 2012
'''

import sys, os, time, math
from MAVProxy.modules.lib import mp_settings
from MAVProxy.modules import mavproxy_map
from pymavlink import mavutil

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.mavproxy_param import ParamState

# this should be in mavutil.py
mode_mapping_antenna = {
    'MANUAL' : 0,
    'AUTO' : 10,
    'INITIALISING' : 16
    }

class TrackerModule(mp_module.MPModule):
    def __init__(self, mpstate):
        from pymavlink import mavparm
        super(TrackerModule, self).__init__(mpstate, "tracker", "antenna tracker control module", public=True)
        self.connection = None
        self.heading = 0
        self.tracker_param = mavparm.MAVParmDict()
        sysid = 2
        self.pstate = ParamState(self.tracker_param, self.logdir, self.vehicle_name, 'tracker.parm', mpstate, sysid)
        self.tracker_settings = mp_settings.MPSettings(
            [ ('port', str, "/dev/ttyUSB0"),
              ('baudrate', int, 57600),
              ('debug', int, 0),
              ('hfov', int, 15),
              ('vfov', int, 15),
              ('range', int, 0),
              ('lat', float, 0),
              ('lon', float, 0),
              ('heading', float, 0),
              ]
            )
        self.tunnel_callbacks = []
        self.add_command('tracker', self.cmd_tracker,
                         "antenna tracker control module",
                         ['<start|arm|disarm|level|mode|position|calpress|mode>',
                          'set (TRACKERSETTING)',
                          'param <set|show|fetch|help> (TRACKERPARAMETER)',
                          'param (TRACKERSETTING)'])
        self.add_completion_function('(TRACKERSETTING)', self.tracker_settings.completion)
        self.add_completion_function('(TRACKERPARAMETER)', self.complete_parameter)

    def complete_parameter(self, text):
        '''complete a tracker parameter'''
        return self.tracker_param.keys()

    def find_connection(self):
        '''find an antenna tracker connection if possible'''
        if self.connection is not None:
            return self.connection
        for m in self.mpstate.mav_master:
            if 'HEARTBEAT' in m.messages:
                if m.messages['HEARTBEAT'].type == mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER:
                    return m
        return None

    def cmd_tracker(self, args):
        '''tracker command parser'''
        usage = "usage: tracker <start|set|arm|disarm|level|param|mode|position> [options]"
        if len(args) == 0:
            print(usage)
            return
        if args[0] == "start":
            self.cmd_tracker_start()
        elif args[0] == "set":
            self.tracker_settings.command(args[1:])
        elif args[0] == 'arm':
            self.cmd_tracker_arm()
        elif args[0] == 'disarm':
            self.cmd_tracker_disarm()
        elif args[0] == 'level':
            self.cmd_tracker_level()
        elif args[0] == 'param':
            self.cmd_tracker_param(args[1:])
        elif args[0] == 'mode':
            self.cmd_tracker_mode(args[1:])
        elif args[0] == 'position':
            self.cmd_tracker_position(args[1:])
        elif args[0] == 'calpress':
            self.cmd_tracker_calpress(args[1:])
        else:
            print(usage)

    def cmd_tracker_position(self, args):
        '''tracker manual positioning commands'''
        connection = self.find_connection()
        if not connection:
            print("No antenna tracker found")
            return
        positions = [0, 0, 0, 0, 0] # x, y, z, r, buttons. only position[0] (yaw) and position[1] (pitch) are currently used
        for i in range(0, 4):
            if len(args) > i:
                positions[i] = int(args[i]) # default values are 0
        connection.mav.manual_control_send(connection.target_system,
                                           positions[0], positions[1],
                                           positions[2], positions[3],
                                           positions[4])

    def cmd_tracker_calpress(self, args):
        '''calibrate barometer on tracker'''
        connection = self.find_connection()
        if not connection:
            print("No antenna tracker found")
            return
        connection.calibrate_pressure()

    def cmd_tracker_mode(self, args):
        '''set arbitrary mode'''
        connection = self.find_connection()
        if not connection:
            print("No antenna tracker found")
            return
        mode_mapping = connection.mode_mapping()
        if mode_mapping is None:
            print('No mode mapping available')
            return
        if len(args) != 1:
            print('Available modes: ', mode_mapping.keys())
            return
        mode = args[0].upper()
        if mode not in mode_mapping:
            print('Unknown mode %s: ' % mode)
            return
        connection.set_mode(mode_mapping[mode])

    def mavlink_packet(self, m):
        '''handle an incoming mavlink packet from the master vehicle. Relay it to the tracker
        if it is a GLOBAL_POSITION_INT'''
        if m.get_type() in ['GLOBAL_POSITION_INT', 'SCALED_PRESSURE']:
            connection = self.find_connection()
            if not connection:
                return
            if m.get_srcSystem() != connection.target_system:
                connection.mav.send(m)

    def update_map(self, lat, lon, heading, color):
        '''update tracker icon and beam on the map'''
        if self.module('map') is None:
            return
        if lat == 0 and lon == 0:
            return
        self.module('map').create_vehicle_icon('AntennaTracker', 'red', follow=False, vehicle_type='antenna')
        self.mpstate.map.set_position('AntennaTracker', (lat, lon), rotation=heading)
        if self.tracker_settings.range > 0:
            from MAVProxy.modules.mavproxy_map import mp_slipmap
            self.mpstate.map.add_object(mp_slipmap.SlipCircle(
                'AntennaBeam', 3, (lat, lon),
                self.tracker_settings.range,
                color,
                linewidth=1,
                start_angle=-self.tracker_settings.hfov / 2,
                end_angle=self.tracker_settings.hfov / 2,
                rotation=(-90 + heading) % 360,
                add_radii=True,
                fill_alpha=0.15,
            ))

    def idle_task(self):
        '''called in idle time'''
        if not self.connection:
            # pseudo tracker mode: draw from settings, fall back to home position
            lat = self.tracker_settings.lat
            lon = self.tracker_settings.lon
            if lat == 0 and lon == 0 and 'HOME_POSITION' in self.master.messages:
                home = self.master.messages['HOME_POSITION']
                lat = home.latitude * 1.0e-7
                lon = home.longitude * 1.0e-7
            self.update_map(lat, lon, self.tracker_settings.heading, (200, 200, 200))
            return

        # check for a mavlink message from the tracker
        m = self.connection.recv_msg()
        if m is None:
            return

        if self.tracker_settings.debug:
            print(m)

        self.pstate.handle_mavlink_packet(self.connection, m)
        self.pstate.fetch_check(self.connection)

        # forward VRX telemetry into main mavlink stream
        if m.get_type() == 'NAMED_VALUE_FLOAT' and m.name in ('VRXF', 'VRXA', 'VRXB'):
            self.send_named_float(m.name, m.value)
        elif m.get_type() == 'TUNNEL' and m.payload_type == 60100:
            for cb in self.tunnel_callbacks:
                cb(m)

        if m.get_type() == 'GLOBAL_POSITION_INT':
            (self.lat, self.lon) = (m.lat*1.0e-7, m.lon*1.0e-7)
        elif m.get_type() == 'ATTITUDE':
            self.heading = math.degrees(m.yaw) % 360

        if hasattr(self, 'lat') and (self.lat != 0 or self.lon != 0):
            self.update_map(self.lat, self.lon, self.heading, (0, 200, 0))
        else:
            # connected but no GPS fix — yellow
            lat = self.tracker_settings.lat
            lon = self.tracker_settings.lon
            if lat == 0 and lon == 0 and 'HOME_POSITION' in self.master.messages:
                home = self.master.messages['HOME_POSITION']
                lat = home.latitude * 1.0e-7
                lon = home.longitude * 1.0e-7
            self.update_map(lat, lon, self.heading, (0, 200, 200))


    def cmd_tracker_start(self):
        if self.tracker_settings.port is None:
            print("tracker port not set")
            return
        if self.connection is not None:
            self.connection.close()
            self.connection = None
            print("Closed old connection")
        print("connecting to tracker %s at %d" % (self.tracker_settings.port,
                                                  self.tracker_settings.baudrate))
        m = mavutil.mavlink_connection(self.tracker_settings.port,
                                       autoreconnect=True,
                                       source_system=self.settings.source_system,
                                       baud=self.tracker_settings.baudrate)
        m.mav.srcComponent = self.settings.source_component
        if self.logdir:
            m.setup_logfile(os.path.join(self.logdir, 'tracker.tlog'))
        self.connection = m

    def cmd_tracker_arm(self):
        '''Enable the servos in the tracker so the antenna will move'''
        if not self.connection:
            print("tracker not connected")
            return
        self.connection.arducopter_arm()

    def cmd_tracker_disarm(self):
        '''Disable the servos in the tracker so the antenna will not move'''
        if not self.connection:
            print("tracker not connected")
            return
        self.connection.arducopter_disarm()

    def cmd_tracker_level(self):
        '''Calibrate the accelerometers. Disarm and move the antenna level first'''
        if not self.connection:
            print("tracker not connected")
            return
        self.connection.calibrate_level()

    def cmd_tracker_param(self, args):
        '''Parameter commands'''
        if not self.connection:
            print("tracker not connected")
            return
        self.pstate.handle_command(self.connection, self.mpstate, args)

def init(mpstate):
    '''initialise module'''
    return TrackerModule(mpstate)
