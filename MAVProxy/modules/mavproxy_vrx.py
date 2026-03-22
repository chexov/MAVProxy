#!/usr/bin/env python3
'''
VRX/VTX control module for MAVProxy

Controls 5.8GHz video receivers (VRX on antenna tracker) and
transmitters (VTX on UAV). Provides a wx GUI for frequency
selection, RSSI monitoring, and spectrum scanning.

Load with: module load vrx
Commands: vrx <close|scan|freq|status|set|fetch>
'''

import struct
from MAVProxy.modules.lib import mp_module


class VRXModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(VRXModule, self).__init__(mpstate, "vrx", "VRX/VTX control")
        self.add_command('vrx', self.cmd_vrx, "VRX/VTX control",
                         ['<close|scan|status|fetch>', 'freq (FREQ)', 'set (PARAM) (VALUE)'])
        self.gui = None
        self.vrx_target = 'tracker'  # 'tracker' or 'main'
        self.vrx_freq = 0
        self.rssi_a = 0.0
        self.rssi_b = 0.0
        self.vtx_freq = 0
        self.vtx_band = 0
        self.vtx_channel = 0
        self.vtx_power = 0
        self.vtx_params = {}  # all VTX_* param values from vehicle
        self._params_seeded = False
        self._tunnel_registered = False
        self._register_tunnel_callback()
        # open GUI immediately on module load
        self._open_gui()

    def _register_tunnel_callback(self):
        '''register tunnel callback on tracker module (retried until success)'''
        if self._tunnel_registered:
            return
        tracker = self.module('tracker')
        if tracker is not None and hasattr(tracker, 'tunnel_callbacks'):
            tracker.tunnel_callbacks.append(self._on_tunnel)
            self._tunnel_registered = True

    def _fetch_vtx_params(self):
        '''request all VTX_* params from the vehicle'''
        from MAVProxy.modules.lib.wxvrx import VTX_PARAM_NAMES
        for pname in VTX_PARAM_NAMES:
            self.master.param_fetch_one(pname)

    def _seed_vtx_params(self):
        '''read existing VTX_* params from the param cache'''
        from MAVProxy.modules.lib.wxvrx import VTX_PARAM_NAMES
        found = 0
        for pname in VTX_PARAM_NAMES:
            val = self.get_mav_param(pname)
            if val is not None:
                found += 1
                self.vtx_params[pname] = int(val)
                if pname == 'VTX_FREQ':
                    self.vtx_freq = int(val)
                elif pname == 'VTX_BAND':
                    self.vtx_band = int(val)
                elif pname == 'VTX_CHANNEL':
                    self.vtx_channel = int(val)
                elif pname == 'VTX_POWER':
                    self.vtx_power = int(val)
        if found > 0:
            self._params_seeded = True

    def cmd_vrx(self, args):
        if len(args) == 0:
            print("Usage: vrx <close|scan|freq|status|set|fetch>")
            return
        cmd = args[0]
        if cmd == 'close':
            self._close_gui()
        elif cmd == 'scan':
            self._start_scan()
        elif cmd == 'freq':
            if len(args) < 2:
                print("Usage: vrx freq <MHz>")
                return
            try:
                self._set_vrx_freq(int(args[1]))
            except ValueError:
                print("Invalid frequency")
        elif cmd == 'status':
            self._print_status()
        elif cmd == 'set':
            if len(args) < 3:
                print("Usage: vrx set <param> <value>")
                return
            self._set_param(args[1], args[2])
        elif cmd == 'fetch':
            self._fetch_vtx_params()
        else:
            print("Unknown command: %s" % cmd)

    def _open_gui(self):
        if self.gui is not None and self.gui.is_alive():
            print("VRX window already open")
            return
        from MAVProxy.modules.lib.wxvrx import VRXWindow
        self.gui = VRXWindow()
        print("VRX window opened")

    def _close_gui(self):
        if self.gui is not None:
            self.gui.close()
            self.gui = None
            print("VRX window closed")

    def _print_status(self):
        conn = self._get_tracker_conn()
        conn_status = 'connected' if conn is not None else 'NOT connected'
        print("VRX target: %s (%s)" % (self.vrx_target, conn_status))
        print("VRX Freq: %d MHz  RSSI A: %.2f  B: %.2f" % (self.vrx_freq, self.rssi_a, self.rssi_b))
        print("VTX Freq: %d MHz  Band: %d  Ch: %d  Power: %d mW" % (
            self.vtx_freq, self.vtx_band, self.vtx_channel, self.vtx_power))

    def _get_tracker_conn(self):
        '''get tracker mavlink connection based on target setting'''
        if self.vrx_target == 'main':
            return self.master
        tracker = self.module('tracker')
        if tracker is not None:
            conn = tracker.find_connection()
            if conn is not None:
                return conn
        # no tracker module or no tracker connection — fall back to main
        return self.master

    def _gui_status(self, text):
        '''send status text to GUI status bar'''
        if self.gui is not None and self.gui.is_alive():
            self.gui.set_status(text)

    def _set_vrx_freq(self, freq):
        '''set VRX frequency on tracker'''
        conn = self._get_tracker_conn()
        conn.param_set_send('VRX_FREQ', freq)
        self._gui_status("VRX freq sent: %d MHz" % freq)
        print("VRX freq → %d MHz" % freq)

    def _set_vtx_freq(self, freq):
        '''set VTX frequency on UAV'''
        self.param_set('VTX_FREQ', freq)
        print("VTX freq → %d MHz" % freq)

    def _set_vtx_band_ch(self, band, channel, freq):
        '''set VTX band+channel+freq on UAV'''
        self.param_set('VTX_BAND', band)
        self.param_set('VTX_CHANNEL', channel)
        self.param_set('VTX_FREQ', freq)
        print("VTX → band %d ch %d freq %d MHz" % (band, channel, freq))

    def _set_vtx_power(self, power):
        '''set VTX power on UAV'''
        self.param_set('VTX_POWER', power)
        print("VTX power → %d mW" % power)

    def _start_scan(self):
        '''trigger VRX scan on tracker'''
        conn = self._get_tracker_conn()
        conn.param_set_send('VRX_SCAN', 1)
        self._gui_status("Scan started")
        print("VRX scan started")

    def _set_param(self, name, value):
        '''set a VTX parameter on UAV'''
        name = name.upper()
        if not name.startswith('VTX_'):
            name = 'VTX_' + name
        try:
            val = int(value)
        except ValueError:
            try:
                val = float(value)
            except ValueError:
                print("Invalid value: %s" % value)
                return
        self.param_set(name, val)
        print("%s → %s" % (name, value))

    def _on_tunnel(self, m):
        '''callback for TUNNEL messages from tracker (scan data)'''
        # payload_type 60100: VRX scan results
        # format: uint32 start_freq, uint16 step, uint16 count, uint8[] rssi
        payload = bytes(m.payload[:m.payload_length])
        if len(payload) < 8:
            return
        start_freq, step, count = struct.unpack('<IHH', payload[:8])
        rssi_values = list(payload[8:8 + count])
        print("VRX scan: %d-%d MHz, %d freqs" % (start_freq, start_freq + step * count, count))
        if self.gui is not None and self.gui.is_alive():
            from MAVProxy.modules.lib.wxvrx import VRXScanData
            self.gui.set_scan_data(VRXScanData(start_freq, step, count, rssi_values))

    def mavlink_packet(self, m):
        mtype = m.get_type()
        if mtype == 'NAMED_VALUE_FLOAT':
            name = m.name
            if name == 'VRXF':
                self.vrx_freq = int(m.value)
            elif name == 'VRXA':
                self.rssi_a = m.value
            elif name == 'VRXB':
                self.rssi_b = m.value
        elif mtype == 'TUNNEL' and m.payload_type == 60100:
            # scan results arriving via main mavlink stream (direct USB mode)
            self._on_tunnel(m)
        elif mtype == 'PARAM_VALUE':
            pname = m.param_id
            if 'VTX' in pname:
                self.vtx_params[pname] = int(m.param_value)
                if pname == 'VTX_FREQ':
                    self.vtx_freq = int(m.param_value)
                elif pname == 'VTX_BAND':
                    self.vtx_band = int(m.param_value)
                elif pname == 'VTX_CHANNEL':
                    self.vtx_channel = int(m.param_value)
                elif pname == 'VTX_POWER':
                    self.vtx_power = int(m.param_value)

    def idle_task(self):
        '''poll GUI for commands'''
        self._register_tunnel_callback()
        if not self._params_seeded:
            self._seed_vtx_params()
        if self.gui is None or not self.gui.is_alive():
            return
        # send current telemetry
        from MAVProxy.modules.lib.wxvrx import VRXTelemetry
        self.gui.set_telemetry(VRXTelemetry(
            freq=self.vrx_freq, rssi_a=self.rssi_a, rssi_b=self.rssi_b,
            vtx_freq=self.vtx_freq, vtx_band=self.vtx_band,
            vtx_channel=self.vtx_channel, vtx_power=self.vtx_power))
        # poll commands
        cmd = self.gui.get_command()
        if cmd is None:
            return
        print("vrx: %s %s" % (cmd.action, cmd.value))
        if cmd.action == 'set_vrx_freq':
            self._set_vrx_freq(cmd.value)
        elif cmd.action == 'set_vtx_freq':
            self._set_vtx_freq(cmd.value)
        elif cmd.action == 'set_vtx_band_ch':
            v = cmd.value
            self._set_vtx_band_ch(v['band'], v['channel'], v['freq'])
        elif cmd.action == 'set_vtx_power':
            self._set_vtx_power(cmd.value)
        elif cmd.action == 'scan':
            self._start_scan()
        elif cmd.action == 'set_target':
            self.vrx_target = cmd.value
            print("vrx target: %s" % cmd.value)

    def unload(self):
        '''called when module is unloaded'''
        if self._tunnel_registered:
            tracker = self.module('tracker')
            if tracker is not None and hasattr(tracker, 'tunnel_callbacks'):
                if self._on_tunnel in tracker.tunnel_callbacks:
                    tracker.tunnel_callbacks.remove(self._on_tunnel)
        self._close_gui()


def init(mpstate):
    return VRXModule(mpstate)
