#!/usr/bin/env python3
"""Run production input/mapping code on a host with mocked evdev/SPI/files.

Pass an unmodified psakhis/Main_MiSTer checkout at commit
0272823a66cb7c601256406a2e80e8c6b2e93e13 for the headers omitted by this
repository's HPS source overlay. No FPGA or input device is required.
"""
import argparse
import os
import re
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def function(path, signature):
    source = (ROOT / path).read_text()
    start = source.index(signature)
    return source[start:source.index('\n}', start) + 2] + '\n'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('framework', type=Path)
    parser.add_argument('--mutation-check', action='store_true', help='verify old defects fail assertions')
    args = parser.parse_args()
    framework = args.framework.resolve()
    sv = (ROOT / 'Groovy.sv').read_text()
    config = sv[sv.index('localparam CONF_STR'):sv.index('// HPS is the module')]
    entries = re.findall(r'"([^"\n]*)"', config)
    assert sum(map(len, entries)) < 10 * 1024
    assert max(map(len, entries)) <= 2048
    assert sum(entry.startswith('J') for entry in entries) == 1
    for entry in entries:
        if entry.startswith(('J1,', 'jn,')):
            names = entry.rstrip(';').split(',')[1:]
            assert len(names) == 12 and max(map(len, names)) < 32
    hps = (ROOT / 'sys/hps_io.sv').read_text()
    for command, player in (('02', 0), ('03', 1)):
        assert re.search(r"'h" + command + r": if\(byte_cnt==1\) joystick_" + str(player) + r"\[15:0\] <= io_din", hps)
    qip = (ROOT / 'files.qip').read_text()
    for module in ('jtframe_hsize', 'jtframe_linebuf', 'jtframe_rpwp_ram'):
        path = 'rtl/JTFRAME/' + module + '.v'
        assert path in qip and (ROOT / path).is_file()
    print('PASS: configuration limits, FPGA joystick word widths and JTFRAME dependencies')
    with tempfile.TemporaryDirectory(prefix='groovy-controller-') as tmp:
        tmp = Path(tmp)
        code = function('hps_linux/src/user_io.cpp', 'void user_io_digital_joystick(')
        code += function('hps_linux/src/user_io.cpp', 'int substrcpy(')
        for signature in ('static bool groovy_trigger_registration(',
                          'static bool groovy_register_udp_inputs()',
                          'static void groovy_send_joysticks()', 'void groovy_send_joystick(',
                          'void groovy_send_analog(', 'void groovy_set_triggers('):
            code += function('hps_linux/src/support/groovy/groovy.cpp', signature)
        (tmp / 'production_functions.h').write_text(code)
        flags = ['-std=gnu++14', '-funsigned-char', '-g', '-O1',
                 '-ffunction-sections', '-fdata-sections',
                 '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                 '-I' + str(ROOT / 'hps_linux/src'), '-I' + str(framework),
                 '-I' + str(framework / 'lib/libchdr/include'), '-I' + str(tmp)]
        executable = tmp / 'controller-test'
        subprocess.run(['g++', *flags, str(ROOT / 'tests/controller_input_test.cpp'),
                        '-Wl,--gc-sections', '-o', str(executable)], check=True)
        environment = os.environ.copy()
        # LeakSanitizer cannot run under the Work runtime's ptrace sandbox.
        # AddressSanitizer and UndefinedBehaviorSanitizer remain enabled.
        environment.setdefault('ASAN_OPTIONS', 'detect_leaks=0')
        subprocess.run([str(executable), str(ROOT / 'Groovy.sv')], check=True, env=environment)
        if args.mutation_check:
            database = (ROOT / 'hps_linux/src/gamecontroller_db.cpp').read_text()
            mutations = {
                'database-keycode-union': ('gamecontroller_db.cpp', database.replace(
                    'memset(fill_map, 0, sizeof(uint32_t) * NUMSYSTEMBUTTONS);', '').replace(
                    '(fill_map[m_button_num] & 0xFFFF0000)', 'fill_map[m_button_num]')),
                'old-system-mapper-limit': ('input.cpp', (ROOT / 'hps_linux/src/input.cpp').read_text().replace(
                    'system_map_button_position(mapping_button, mapping_type)', '(mapping_button < SYS_BTN_CNT_ESC + 1)')),
                'missing-stick-click-mapping': ('joymapping.cpp', (ROOT / 'hps_linux/src/joymapping.cpp').read_text().replace(
                    'else if(!strcasecmp(btn_name, "L3")) map[idx] = mmap[SYS_BTN_L3];', '').replace(
                    'else if(!strcasecmp(btn_name, "R3")) map[idx] = mmap[SYS_BTN_R3];', '')),
            }
            original_test = (ROOT / 'tests/controller_input_test.cpp').read_text()
            for name, (unit, source) in mutations.items():
                mutant = tmp / unit
                mutant.write_text(source)
                harness = original_test
                for included in ('input.cpp', 'joymapping.cpp', 'gamecontroller_db.cpp'):
                    path = mutant if included == unit else ROOT / 'hps_linux/src' / included
                    harness = harness.replace('../hps_linux/src/' + included, str(path))
                test_file = tmp / 'mutant-test.cpp'
                test_file.write_text(harness)
                subprocess.run(['g++', *flags, str(test_file), '-Wl,--gc-sections', '-o', str(executable)], check=True)
                result = subprocess.run([str(executable), str(ROOT / 'Groovy.sv')],
                                        env=environment, capture_output=True, text=True)
                assert result.returncode != 0 and 'Assertion' in result.stderr, result.stderr
                print('PASS: regression test rejects restored defect:', name)

        # Compile the complete changed units, including menu code excluded from
        # the host harness. Match ARM's default unsigned-char ABI.
        for unit in ('input.cpp', 'menu.cpp', 'joymapping.cpp', 'gamecontroller_db.cpp'):
            subprocess.run(['g++', *flags, '-I' + str(framework / 'lib/bluetooth'),
                            '-fsyntax-only', str(ROOT / 'hps_linux/src' / unit)], check=True)
        print('PASS: full changed HPS translation units compile (host syntax check)')

if __name__ == '__main__':
    main()
