#!/usr/bin/env python3
'''VRX control window, child process wrapper following wxconsole pattern'''

import threading
from MAVProxy.modules.lib import multiproc

# 5.8GHz FPV band table
BAND_NAMES = ['A', 'B', 'E', 'F', 'R', 'L']
BAND_TABLE = {
    'A': [5865, 5845, 5825, 5805, 5785, 5765, 5745, 5725],
    'B': [5733, 5752, 5771, 5790, 5809, 5828, 5847, 5866],
    'E': [5705, 5685, 5665, 5645, 5885, 5905, 5925, 5945],
    'F': [5740, 5760, 5780, 5800, 5820, 5840, 5860, 5880],
    'R': [5658, 5695, 5732, 5769, 5806, 5843, 5880, 5917],
    'L': [5362, 5399, 5436, 5473, 5510, 5547, 5584, 5621],
}
NUM_CHANNELS = 8

# reverse lookup: freq → (band, channel_index)
FREQ_TO_BANDCH = {}
for _band, _freqs in BAND_TABLE.items():
    for _ch_idx, _f in enumerate(_freqs):
        FREQ_TO_BANDCH[_f] = (_band, _ch_idx)


def freq_to_band_channel(freq):
    '''find band+channel for a frequency, or None'''
    return FREQ_TO_BANDCH.get(freq)


# VTX params we track from the vehicle
VTX_PARAM_NAMES = [
    'VTX_ENABLE', 'VTX_BAND', 'VTX_CHANNEL', 'VTX_FREQ',
    'VTX_POWER', 'VTX_MAX_POWER', 'VTX_OPTIONS',
]


class VRXTelemetry:
    '''current VRX/VTX telemetry state'''
    def __init__(self, freq=0, rssi_a=0.0, rssi_b=0.0,
                 vtx_freq=0, vtx_band=0, vtx_channel=0, vtx_power=0,
                 vtx_params=None):
        self.freq = freq
        self.rssi_a = rssi_a
        self.rssi_b = rssi_b
        self.vtx_freq = vtx_freq
        self.vtx_band = vtx_band
        self.vtx_channel = vtx_channel
        self.vtx_power = vtx_power
        self.vtx_params = vtx_params or {}


class VRXScanData:
    '''scan results from VRX'''
    def __init__(self, start_freq, step, count, rssi_values):
        self.start_freq = start_freq
        self.step = step
        self.count = count
        self.rssi_values = rssi_values  # list of int RSSI per frequency step


class VRXStatus:
    '''status message from module to GUI'''
    def __init__(self, text):
        self.text = text


class VRXCommand:
    '''command from GUI back to module'''
    def __init__(self, action, value=None):
        self.action = action  # 'set_vrx_freq', 'set_vtx_freq', 'set_vtx_band_ch', 'set_vtx_power', 'scan'
        self.value = value


class VRXWindow:
    '''VRX control window running in a child process'''
    def __init__(self):
        self.parent_pipe_recv, self.child_pipe_send = multiproc.Pipe(duplex=False)
        self.child_pipe_recv, self.parent_pipe_send = multiproc.Pipe(duplex=False)
        self.close_event = multiproc.Event()
        self.close_event.clear()
        self.child = multiproc.Process(target=self._child_task)
        self.child.start()
        self.child_pipe_send.close()
        self.child_pipe_recv.close()

    def _child_task(self):
        '''child process — holds all wx GUI elements'''
        self.parent_pipe_send.close()
        self.parent_pipe_recv.close()
        from MAVProxy.modules.lib import wx_processguard
        from MAVProxy.modules.lib.wx_loader import wx
        from MAVProxy.modules.lib.wxvrx_ui import VRXFrame
        app = wx.App(False)
        app.frame = VRXFrame(state=self)
        app.frame.Show()
        app.MainLoop()

    def set_telemetry(self, telem):
        '''send telemetry update to GUI'''
        try:
            self.parent_pipe_send.send(telem)
        except Exception:
            pass

    def set_scan_data(self, scan):
        '''send scan results to GUI'''
        try:
            self.parent_pipe_send.send(scan)
        except Exception:
            pass

    def set_status(self, text):
        '''send status message to GUI status bar'''
        try:
            self.parent_pipe_send.send(VRXStatus(text))
        except Exception:
            pass

    def get_command(self):
        '''non-blocking poll for a command from GUI'''
        if self.parent_pipe_recv.poll():
            try:
                return self.parent_pipe_recv.recv()
            except EOFError:
                return None
        return None

    def close(self):
        '''close the window'''
        self.close_event.set()
        if self.is_alive():
            self.child.join(2)

    def is_alive(self):
        return self.child.is_alive()
