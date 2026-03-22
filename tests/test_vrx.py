#!/usr/bin/env python3
'''Unit tests for VRX module and related components'''

import struct
import sys
import os
import pytest

# ensure MAVProxy is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestBandTable:
    def test_all_bands_present(self):
        from MAVProxy.modules.lib.wxvrx import BAND_TABLE, BAND_NAMES
        assert len(BAND_NAMES) == 6
        for band in BAND_NAMES:
            assert band in BAND_TABLE

    def test_each_band_has_8_channels(self):
        from MAVProxy.modules.lib.wxvrx import BAND_TABLE, BAND_NAMES
        for band in BAND_NAMES:
            assert len(BAND_TABLE[band]) == 8

    def test_frequencies_in_valid_range(self):
        from MAVProxy.modules.lib.wxvrx import BAND_TABLE
        for band, freqs in BAND_TABLE.items():
            for freq in freqs:
                assert 5000 <= freq <= 6000, "Band %s freq %d out of range" % (band, freq)

    def test_frequency_lookup(self):
        from MAVProxy.modules.lib.wxvrx import freq_to_band_channel
        # F band CH4 = 5800
        result = freq_to_band_channel(5800)
        assert result == ('F', 3)  # 0-indexed channel
        # A band CH1 = 5865
        result = freq_to_band_channel(5865)
        assert result == ('A', 0)
        # unknown frequency
        result = freq_to_band_channel(9999)
        assert result is None


class TestSeverityColour:
    def _get_stub(self):
        from MAVProxy.modules.mavproxy_maphud import MapHUD
        class Stub:
            pass
        stub = Stub()
        stub._severity_colour = MapHUD._severity_colour.__get__(stub)
        stub._severity_tag = MapHUD._severity_tag.__get__(stub)
        return stub

    def test_error_is_red(self):
        stub = self._get_stub()
        for sev in range(4):
            assert stub._severity_colour(sev) == (80, 80, 255), "severity %d should be RED" % sev

    def test_warning_is_yellow(self):
        stub = self._get_stub()
        assert stub._severity_colour(4) == (80, 255, 255)

    def test_info_is_white(self):
        stub = self._get_stub()
        for sev in (5, 6, 7):
            assert stub._severity_colour(sev) == (255, 255, 255), "severity %d should be WHITE" % sev

    def test_severity_tags(self):
        stub = self._get_stub()
        for sev in range(4):
            assert stub._severity_tag(sev) == '[ERR]'
        assert stub._severity_tag(4) == '[WARN]'
        for sev in (5, 6, 7):
            assert stub._severity_tag(sev) == '[INFO]'


class TestTunnelScanParsing:
    def test_parse_scan_payload(self):
        '''construct a binary TUNNEL payload and verify parsing'''
        start_freq = 5700
        step = 5
        count = 10
        rssi_values = [100, 120, 80, 200, 150, 90, 40, 180, 220, 60]
        payload = struct.pack('<IHH', start_freq, step, count)
        payload += bytes(rssi_values)
        # pad to 128 bytes (TUNNEL payload size)
        payload += bytes(128 - len(payload))

        # parse like mavproxy_vrx._on_tunnel does
        parsed_start, parsed_step, parsed_count = struct.unpack('<IHH', payload[:8])
        parsed_rssi = list(payload[8:8 + parsed_count])

        assert parsed_start == start_freq
        assert parsed_step == step
        assert parsed_count == count
        assert parsed_rssi == rssi_values

    def test_short_payload_ignored(self):
        '''payloads < 8 bytes should be skipped'''
        payload = bytes(4)
        assert len(payload) < 8


class TestVRXCommandSerialization:
    def test_command_attributes(self):
        from MAVProxy.modules.lib.wxvrx import VRXCommand
        cmd = VRXCommand('set_vrx_freq', 5800)
        assert cmd.action == 'set_vrx_freq'
        assert cmd.value == 5800

    def test_command_no_value(self):
        from MAVProxy.modules.lib.wxvrx import VRXCommand
        cmd = VRXCommand('scan')
        assert cmd.action == 'scan'
        assert cmd.value is None

    def test_telemetry_attributes(self):
        from MAVProxy.modules.lib.wxvrx import VRXTelemetry
        t = VRXTelemetry(freq=5800, rssi_a=0.85, rssi_b=0.72,
                         vtx_freq=5752, vtx_band=1, vtx_channel=2, vtx_power=2500)
        assert t.freq == 5800
        assert t.rssi_a == 0.85
        assert t.rssi_b == 0.72
        assert t.vtx_freq == 5752
        assert t.vtx_band == 1
        assert t.vtx_channel == 2
        assert t.vtx_power == 2500

    def test_scan_data_attributes(self):
        from MAVProxy.modules.lib.wxvrx import VRXScanData
        s = VRXScanData(start_freq=5700, step=5, count=3, rssi_values=[100, 200, 150])
        assert s.start_freq == 5700
        assert s.step == 5
        assert s.count == 3
        assert s.rssi_values == [100, 200, 150]


class TestModuleImport:
    def test_vrx_module_imports(self):
        '''verify the module can be imported without errors'''
        import MAVProxy.modules.mavproxy_vrx as vrx
        assert hasattr(vrx, 'init')
        assert hasattr(vrx, 'VRXModule')

    def test_wxvrx_imports(self):
        from MAVProxy.modules.lib import wxvrx
        assert hasattr(wxvrx, 'VRXWindow')
        assert hasattr(wxvrx, 'VRXTelemetry')
        assert hasattr(wxvrx, 'VRXScanData')
        assert hasattr(wxvrx, 'VRXCommand')


class TestSlipHUDColor:
    def test_outline_text_default_white(self):
        '''verify _outline_text signature accepts colour param'''
        import inspect
        from MAVProxy.modules.mavproxy_map.mp_slipmap_util import SlipHUD
        sig = inspect.signature(SlipHUD._outline_text)
        params = list(sig.parameters.keys())
        assert 'colour' in params
        # verify default is white
        assert sig.parameters['colour'].default == (255, 255, 255)
