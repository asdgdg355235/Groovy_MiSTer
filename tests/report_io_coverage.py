#!/usr/bin/env python3
"""Classify every remaining unconstrained port without fabricating delays."""
from pathlib import Path
import argparse
import json
import re


def classify(port):
    if port == 'LED[2]':
        return ('status LED, PIN_V16', 'exception_not_effective', 'Display-only exception is in sys/sys_top.sdc; if still listed, inspect ignored constraints.')
    if port in ('IO_SCL', 'IO_SDA'):
        return ('MCP23009 I2C, PIN_U14/PIN_AG9', 'blocked', 'sys/mcp23009.sv requests 500 kHz; sys/i2c.v samples SDA directly on CLK-qualified edges. Need verified bus mode/device limits and board rise/fall/skew; do not treat as synchronized GPIO.')
    if port.startswith('HDMI_I2C_'):
        return ('HPS I2C to onboard ADV7513', 'blocked', 'HPS peripheral drives open-drain pins. Need actual HPS bus clock/configuration, device timing and board rise/fall/skew.')
    if port.startswith('HDMI_TX_'):
        return ('ADV7513/direct-video interface', 'blocked', 'NOHDMI removes ascal/HDMI PLL, not direct-video data outputs. Need enabled interface/clock mode, receiver setup/hold and board skew; no blanket exception.')
    if port in ('HDMI_I2S','HDMI_MCLK','HDMI_SCLK','HDMI_LRCLK') or re.fullmatch(r'USER_IO\[[245]\]', port):
        return ('I2S audio or runtime USER_IO mux', 'blocked', 'Audio remains active in NOHDMI. Need receiver/adapter identity, sample edges, setup/hold and trace skew. USER_IO also has a GPIO mode.')
    if port == 'SDCD_SPDIF':
        return ('SD detect input / open-drain SPDIF output, PIN_AH7', 'blocked', 'Runtime mcp_en selects role; direct input affects SD_CD/output mux with no entry synchronizer. Need board mode and receiver timing/CDC review; no false path justified.')
    if port.startswith(('SDIO_', 'SD_SPI_')):
        return ('Runtime SD/SPI / analog low-bit or sync mux', 'blocked', 'Need actual board/switch mode, card timing or analog receiver requirements, board delays and input CDC review.')
    return ('unclassified active-or-mode-dependent port', 'blocked', 'New unmatched port requires source and hardware review.')


def report(path):
    ports = {}; direction = None
    for line in Path(path).read_text(errors='replace').splitlines():
        if not line.startswith(';'):
            continue
        fields = [f.strip() for f in line.strip(';').split(';')]
        if len(fields) == 1:
            direction = {'Unconstrained Input Ports': 'input', 'Unconstrained Output Ports': 'output'}.get(fields[0])
        elif direction and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*(?:\[\d+\])?', fields[0]):
            ports[(direction, fields[0])] = fields[1:]
    pins = {}
    for candidate in (Path(path).parent/'project_calls_before_fit.json', Path(path).parent.parent/'project_calls_before_fit.json'):
        if candidate.is_file():
            for row in json.loads(candidate.read_text())['events']:
                if row[0]=='location' and '-to' in row:
                    pins[row[row.index('-to')+1]]=row[1]
    rows = []
    for direction, port in sorted(ports):
        interface, status, reason = classify(port)
        rows.append(dict(direction=direction, port=port, interface=interface, status=status, reason=reason,
                         pin=pins.get(port), vendor_constraint_detail=ports[(direction,port)]))
    if not rows and 'Unconstrained Paths Summary' not in Path(path).read_text(errors='replace'):
        raise ValueError('Invalid or absent unconstrained-path report')
    return {'release_qualified': not rows, 'remaining_port_direction_entries': len(rows), 'ports': rows,
            'source': 'sys/sys_top.v, sys/mcp23009.sv, sys/i2c.v, sys/sys.tcl, sys/sys_analog.tcl',
            'known_device_limits_not_complete_board_constraints': {'ADV7513_video_setup_ns':1.8,'ADV7513_video_hold_ns':1.3,'ADV7513_audio_setup_ns':2,'ADV7513_audio_hold_ns':2,'ADV7513_I2C_SDA_setup_ns':100,'ADV7513_I2C_SDA_hold_ns':100,'MCP23009_400kHz_SDA_setup_ns':100,'MCP23009_400kHz_max_output_valid_ns':900},
            'hardware_references': ['https://www.analog.com/media/en/technical-documentation/data-sheets/ADV7513.pdf','https://developer.analog.com/docs/system-level/solutions/reference-designs/adv7513/user-guide.html',
                                    'https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/20002121C.pdf']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('unconstrained', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); a.output.write_text(json.dumps(report(a.unconstrained), indent=2)+'\n')
