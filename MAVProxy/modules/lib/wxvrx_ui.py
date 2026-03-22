#!/usr/bin/env python3
'''VRX control window wx GUI frame'''

from MAVProxy.modules.lib.wx_loader import wx
import wx.grid
from MAVProxy.modules.lib.wxvrx import (
    VRXTelemetry, VRXScanData, VRXCommand, VRXStatus,
    BAND_NAMES, BAND_TABLE, NUM_CHANNELS,
)


class VRXFrame(wx.Frame):
    def __init__(self, state):
        self.state = state
        wx.Frame.__init__(self, None, title='MAVProxy: VRX Control', size=(750, 580))
        self.panel = wx.Panel(self)

        self.vrx_freq = 0
        self.vtx_freq = 0
        self.vtx_band = 0
        self.vtx_channel = 0
        self.rssi_a = 0.0
        self.rssi_b = 0.0
        self.vtx_power = 0
        self.scan_data = {}  # freq -> rssi
        self._selected_from_table = False

        header_font = wx.Font(16, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        status_font = wx.Font(15, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        grid_font = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        vbox = wx.BoxSizer(wx.VERTICAL)

        # status section
        lbl = wx.StaticText(self.panel, label='Status')
        lbl.SetFont(header_font)
        vbox.Add(lbl, 0, wx.LEFT | wx.TOP, 6)
        self.vrx_label = wx.StaticText(self.panel, label='VRX Freq: ----')
        self.vrx_label.SetFont(status_font)
        self.vrx_label.SetBackgroundColour(wx.Colour(180, 210, 255))
        vbox.Add(self.vrx_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        # RSSI bars
        bar_font = wx.Font(12, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        rssi_row = wx.BoxSizer(wx.HORIZONTAL)
        self.rssi_lbl_a = wx.StaticText(self.panel, label='A: ---')
        self.rssi_lbl_a.SetFont(bar_font)
        rssi_row.Add(self.rssi_lbl_a, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.rssi_bar_a = wx.Gauge(self.panel, range=100, size=(120, 18), style=wx.GA_HORIZONTAL)
        rssi_row.Add(self.rssi_bar_a, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.rssi_lbl_b = wx.StaticText(self.panel, label='B: ---')
        self.rssi_lbl_b.SetFont(bar_font)
        rssi_row.Add(self.rssi_lbl_b, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.rssi_bar_b = wx.Gauge(self.panel, range=100, size=(120, 18), style=wx.GA_HORIZONTAL)
        rssi_row.Add(self.rssi_bar_b, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.rssi_indicator = wx.StaticText(self.panel, label=' NO SIGNAL ', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self.rssi_indicator.SetFont(wx.Font(13, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.rssi_indicator.SetBackgroundColour(wx.Colour(180, 180, 180))
        self.rssi_indicator.SetForegroundColour(wx.WHITE)
        rssi_row.Add(self.rssi_indicator, 0, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(rssi_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.vtx_label = wx.StaticText(self.panel, label='VTX Freq: ----  Band: -  Ch: -  Power: ---- mW')
        self.vtx_label.SetFont(status_font)
        self.vtx_label.SetBackgroundColour(wx.Colour(255, 220, 180))
        vbox.Add(self.vtx_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 8)

        # separator
        vbox.Add(wx.StaticLine(self.panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        # band table
        lbl2 = wx.StaticText(self.panel, label='Band / Channel')
        lbl2.SetFont(header_font)
        vbox.Add(lbl2, 0, wx.LEFT | wx.TOP, 6)

        self.grid = wx.grid.Grid(self.panel)
        self.grid.CreateGrid(len(BAND_NAMES), NUM_CHANNELS)
        self.grid.SetDefaultCellFont(grid_font)
        for i, band in enumerate(BAND_NAMES):
            self.grid.SetRowLabelValue(i, band)
        for j in range(NUM_CHANNELS):
            self.grid.SetColLabelValue(j, 'CH%d' % (j + 1))
            self.grid.SetColSize(j, 74)
        for i, band in enumerate(BAND_NAMES):
            for j in range(NUM_CHANNELS):
                self.grid.SetCellValue(i, j, str(BAND_TABLE[band][j]))
                self.grid.SetReadOnly(i, j, True)
                self.grid.SetCellAlignment(i, j, wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        self.grid.SetRowLabelSize(40)
        self.grid.DisableDragRowSize()
        self.grid.DisableDragColSize()
        self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.on_grid_click)
        # grid doesn't report best size on macOS — set it explicitly
        grid_w = self.grid.GetRowLabelSize() + NUM_CHANNELS * 74 + 2
        grid_h = self.grid.GetColLabelSize() + len(BAND_NAMES) * self.grid.GetDefaultRowSize() + 2
        self.grid.SetMinSize(wx.Size(grid_w, grid_h))
        vbox.Add(self.grid, 1, wx.EXPAND | wx.ALL, 4)

        # separator
        vbox.Add(wx.StaticLine(self.panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        # controls
        lbl3 = wx.StaticText(self.panel, label='Controls')
        lbl3.SetFont(header_font)
        vbox.Add(lbl3, 0, wx.LEFT | wx.TOP, 6)

        row0 = wx.BoxSizer(wx.HORIZONTAL)
        row0.Add(wx.StaticText(self.panel, label='VRX target:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.target_radio = wx.RadioBox(self.panel, choices=['Tracker', 'Main'],
                                        style=wx.RA_HORIZONTAL)
        self.target_radio.Bind(wx.EVT_RADIOBOX, self.on_target_change)
        row0.Add(self.target_radio, 0, wx.RIGHT, 8)
        vbox.Add(row0, 0, wx.LEFT | wx.TOP, 4)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(wx.StaticText(self.panel, label='Freq:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.freq_input = wx.TextCtrl(self.panel, size=(80, -1))
        row1.Add(self.freq_input, 0, wx.RIGHT, 4)
        row1.Add(wx.StaticText(self.panel, label='MHz'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.btn_set_vrx = wx.Button(self.panel, label='Set VRX')
        self.btn_set_vtx = wx.Button(self.panel, label='Set VTX')
        self.btn_scan = wx.Button(self.panel, label='Scan')
        row1.Add(self.btn_set_vrx, 0, wx.RIGHT, 4)
        row1.Add(self.btn_set_vtx, 0, wx.RIGHT, 4)
        row1.Add(self.btn_scan, 0)
        vbox.Add(row1, 0, wx.ALL, 4)

        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(wx.StaticText(self.panel, label='Power:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.power_input = wx.TextCtrl(self.panel, size=(80, -1))
        row2.Add(self.power_input, 0, wx.RIGHT, 4)
        row2.Add(wx.StaticText(self.panel, label='mW'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.btn_set_power = wx.Button(self.panel, label='Set Power')
        row2.Add(self.btn_set_power, 0, wx.RIGHT, 4)
        self.btn_max_power = wx.Button(self.panel, label='MaxPower')
        row2.Add(self.btn_max_power, 0)
        vbox.Add(row2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        # status bar for action feedback
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText('Ready')

        self.panel.SetSizer(vbox)
        vbox.Fit(self.panel)
        self.panel.Layout()

        # bind buttons
        self.btn_set_vrx.Bind(wx.EVT_BUTTON, self.on_set_vrx)
        self.btn_set_vtx.Bind(wx.EVT_BUTTON, self.on_set_vtx)
        self.btn_scan.Bind(wx.EVT_BUTTON, self.on_scan)
        self.btn_set_power.Bind(wx.EVT_BUTTON, self.on_set_power)
        self.btn_max_power.Bind(wx.EVT_BUTTON, self.on_max_power)

        # bold font for highlighted grid cells
        self._bold_font = wx.Font(14, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self._normal_font = grid_font

        # poll timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(100)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_target_change(self, event):
        target = 'tracker' if self.target_radio.GetSelection() == 0 else 'main'
        self.state.child_pipe_send.send(VRXCommand('set_target', target))
        self.statusbar.SetStatusText('VRX target: %s' % target)

    def on_grid_click(self, event):
        row = event.GetRow()
        col = event.GetCol()
        band = BAND_NAMES[row]
        freq = BAND_TABLE[band][col]
        self.freq_input.SetValue(str(freq))
        self._selected_from_table = True
        self._selected_band = band
        self._selected_channel = col + 1  # 1-indexed for user display
        self.statusbar.SetStatusText('Selected %s CH%d: %d MHz' % (band, col + 1, freq))
        event.Skip()

    def on_set_vrx(self, event):
        try:
            freq = int(self.freq_input.GetValue())
        except ValueError:
            return
        self.state.child_pipe_send.send(VRXCommand('set_vrx_freq', freq))
        self.statusbar.SetStatusText('VRX freq sent: %d MHz' % freq)

    def on_set_vtx(self, event):
        try:
            freq = int(self.freq_input.GetValue())
        except ValueError:
            return
        if self._selected_from_table:
            band_idx = BAND_NAMES.index(self._selected_band)
            self.state.child_pipe_send.send(VRXCommand('set_vtx_band_ch', {
                'band': band_idx,
                'channel': self._selected_channel - 1,
                'freq': freq,
            }))
            self.statusbar.SetStatusText('VTX sent: %s CH%d %d MHz' % (
                self._selected_band, self._selected_channel, freq))
        else:
            self.state.child_pipe_send.send(VRXCommand('set_vtx_freq', freq))
            self.statusbar.SetStatusText('VTX freq sent: %d MHz' % freq)
        self._selected_from_table = False

    def on_scan(self, event):
        self.state.child_pipe_send.send(VRXCommand('scan'))
        self.statusbar.SetStatusText('Scan started')

    def on_set_power(self, event):
        try:
            power = int(self.power_input.GetValue())
        except ValueError:
            return
        self.state.child_pipe_send.send(VRXCommand('set_vtx_power', power))
        self.statusbar.SetStatusText('VTX power sent: %d mW' % power)

    def on_max_power(self, event):
        dlg = wx.MessageDialog(self,
                               'Set VTX to maximum power (2512 mW)?',
                               'Confirm MaxPower',
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
        if dlg.ShowModal() == wx.ID_YES:
            self.state.child_pipe_send.send(VRXCommand('set_vtx_power', 2512))
            self.statusbar.SetStatusText('VTX MaxPower sent: 2512 mW')
        dlg.Destroy()

    def on_timer(self, event):
        '''poll pipe for updates from module'''
        state = self.state
        if state.close_event.wait(0.001):
            self.timer.Stop()
            self.Destroy()
            return
        while state.child_pipe_recv.poll():
            try:
                msg = state.child_pipe_recv.recv()
            except EOFError:
                return
            if isinstance(msg, VRXTelemetry):
                self._update_telemetry(msg)
            elif isinstance(msg, VRXScanData):
                self._update_scan(msg)
            elif isinstance(msg, VRXStatus):
                self.statusbar.SetStatusText(msg.text)

    def _update_telemetry(self, t):
        self.vrx_freq = t.freq
        self.rssi_a = t.rssi_a
        self.rssi_b = t.rssi_b
        self.vtx_freq = t.vtx_freq
        self.vtx_band = t.vtx_band
        self.vtx_channel = t.vtx_channel
        self.vtx_power = t.vtx_power

        # RSSI bars + labels (0.0-1.0 → 0-100%)
        self.rssi_lbl_a.SetLabel('A: %.2f' % t.rssi_a)
        self.rssi_bar_a.SetValue(min(int(t.rssi_a * 100), 100))
        self.rssi_lbl_b.SetLabel('B: %.2f' % t.rssi_b)
        self.rssi_bar_b.SetValue(min(int(t.rssi_b * 100), 100))

        # RSSI indicator label
        rssi_max = max(t.rssi_a, t.rssi_b)
        if rssi_max >= 0.5:
            self.rssi_indicator.SetLabel(' GOOD ')
            self.rssi_indicator.SetBackgroundColour(wx.Colour(0, 160, 0))
        elif rssi_max >= 0.2:
            self.rssi_indicator.SetLabel(' WEAK ')
            self.rssi_indicator.SetBackgroundColour(wx.Colour(200, 180, 0))
        elif rssi_max > 0:
            self.rssi_indicator.SetLabel(' LOW ')
            self.rssi_indicator.SetBackgroundColour(wx.Colour(200, 0, 0))
        else:
            self.rssi_indicator.SetLabel(' NO SIGNAL ')
            self.rssi_indicator.SetBackgroundColour(wx.Colour(180, 180, 180))

        vrx_text = 'VRX Freq: %d MHz' % t.freq
        self.vrx_label.SetLabel(vrx_text)

        band_letter = BAND_NAMES[t.vtx_band] if 0 <= t.vtx_band < len(BAND_NAMES) else '?'
        vtx_text = 'VTX Freq: %d MHz  Band: %s  Ch: %d  Power: %d mW' % (
            t.vtx_freq, band_letter, t.vtx_channel + 1, t.vtx_power)
        self.vtx_label.SetLabel(vtx_text)

        self._highlight_cells()

    def _update_scan(self, s):
        self.scan_data = {}
        for i in range(s.count):
            freq = s.start_freq + i * s.step
            if i < len(s.rssi_values):
                self.scan_data[freq] = s.rssi_values[i]
        self._color_scan_cells()
        matched = sum(1 for f in self.scan_data if f in
                      {BAND_TABLE[b][c] for b in BAND_NAMES for c in range(NUM_CHANNELS)})
        self.statusbar.SetStatusText('Scan complete: %d freqs, %d in band table' % (s.count, matched))

    def _highlight_cells(self):
        '''highlight current VRX and VTX frequency cells with background + bold (dual coding)'''
        vrx_bg = wx.Colour(180, 210, 255)   # light blue background
        vtx_bg = wx.Colour(255, 220, 180)   # light orange background
        both_bg = wx.Colour(180, 230, 180)  # light green when VRX+VTX match
        for i, band in enumerate(BAND_NAMES):
            for j in range(NUM_CHANNELS):
                freq = BAND_TABLE[band][j]
                is_vrx = (freq == self.vrx_freq and self.vrx_freq > 0)
                is_vtx = (freq == self.vtx_freq and self.vtx_freq > 0)
                if is_vrx and is_vtx:
                    self.grid.SetCellBackgroundColour(i, j, both_bg)
                elif is_vrx:
                    self.grid.SetCellBackgroundColour(i, j, vrx_bg)
                elif is_vtx:
                    self.grid.SetCellBackgroundColour(i, j, vtx_bg)
                elif freq not in self.scan_data:
                    self.grid.SetCellBackgroundColour(i, j, wx.WHITE)
                # bold font for active frequencies
                if is_vrx or is_vtx:
                    self.grid.SetCellFont(i, j, self._bold_font)
                else:
                    self.grid.SetCellFont(i, j, self._normal_font)
                # text stays black for readability
                self.grid.SetCellTextColour(i, j, wx.BLACK)
        self.grid.ForceRefresh()

    def _color_scan_cells(self):
        '''color cells by scan RSSI: GREEN >180, YELLOW 80-180, RED <80'''
        for i, band in enumerate(BAND_NAMES):
            for j in range(NUM_CHANNELS):
                freq = BAND_TABLE[band][j]
                rssi = self.scan_data.get(freq)
                if rssi is None:
                    self.grid.SetCellBackgroundColour(i, j, wx.WHITE)
                elif rssi > 180:
                    self.grid.SetCellBackgroundColour(i, j, wx.Colour(144, 238, 144))  # light green
                elif rssi >= 80:
                    self.grid.SetCellBackgroundColour(i, j, wx.Colour(255, 255, 150))  # light yellow
                else:
                    self.grid.SetCellBackgroundColour(i, j, wx.Colour(255, 180, 180))  # light red
        self.grid.ForceRefresh()

    def on_close(self, event):
        self.timer.Stop()
        self.Destroy()
