# Groovy controller mapping

## Diagnosis / objective

The HPS framework can merge Linux keycodes when parsing database assignments.
`parse_mapping_string()` ORs the incoming code into the existing word. Reloading
`0x130` over `0x131` therefore leaves `0x131`. If Button 3 uses `0x131`, both
buttons then respond to that control. The host harness reproduces this with
stale state & with repeated fields in one database entry. Parsing now clears
stale state & replaces the selected halfword.

This defect predates the label-only commit `04ea15e57499ef331f9b4fce5fb208d54952ce1a`.
That commit changed only `Groovy.sv`. The user's saved mappings, controller model
& event trace weren't supplied, so the harness establishes a software cause of
aliasing; it doesn't prove that this was the source of the reported physical
controller incident. Existing intentional overlaps remain valid. A shared
Button 2/3 keycode in a loaded core map now produces a diagnostic, identifying
the keycode & primary/alternate sets. An old file containing a shared assignment
can't reveal whether that assignment was intentional; redefine core buttons if
it wasn't.

The previous L3/R3 labels expose core slots 14/15 to the manual core mapper,
which already has enough state bits. They don't add system slots, database
names or default name translations. The old system layout has mouse directions
at slots 12..15, so reusing those slots for extra gamepad controls would corrupt
mouse mappings. The old default translator also recognizes only Button 1..4;
its substring matching treats Button 10 as Button 1.

## Reference basis

- Target baseline: `asdgdg355235/Groovy_MiSTer`, `682f435498e6c89f0bc2f4c9b0b9fd6f06469b2f`.
- `psakhis/Main_MiSTer`, `0272823a66cb7c601256406a2e80e8c6b2e93e13`:
  `input.h` system slot layout; `joymapping.cpp::read_buttons`, `map_joystick`;
  `gamecontroller_db.cpp::parse_mapping_string`, `gcdb_map_for_controller`;
  `file_io.cpp::FileLoadConfig`, `FileReadAdv`. These supply the HPS overlay's
  missing framework files. The three added source files derive from this pinned
  revision, with controller changes described here.
- `psakhis/Groovy_MiSTer`, `Groovy.sv::CONF_STR`: inherited ten-button declarations.
- Target `input.cpp::input_poll`, `input_cb`, `joy_digital`, `joy_analog`:
  evdev events, device quirks, player assignment, mapping & held state.
- Target `menu.cpp::HandleUI`: system & core mapper prompts, counts & stages.
- Target `user_io.cpp::user_io_get_confstr`, `user_io_digital_joystick`:
  configuration parsing, `J1` keyboard-emulation flag, primary/alternate folding
  & SPI forwarding. The function naming for core name parsing is
  `user_io_get_core_name`; button names are read by `input.cpp::get_btn`.
- Target `sys/hps_io.sv`: commands `0x02`/`0x03` store independent 32-bit
  joystick words; `confstr_rom` returns the configuration bytes.
  `sys/sys_top.v` connects the HPS bus to `emu`; `Groovy.sv::hps_io` connects
  `joy0`/`joy1`. These FPGA words don't feed the UDP sender.
- Target `support/groovy/groovy.cpp::groovy_send_joystick`,
  `groovy_send_analog`, `groovy_send_joysticks`: two independent 16-bit masks
  in the existing 9/17-byte packets. Target
  `api/groovymister.cpp::PollInputs`, `setFpgaJoystick` copies both 16-bit words.
- Current `MiSTer-devel/Main_MiSTer::joymapping.cpp` was also inspected as a
  comparison: extended controls are translated by name. The implementation here
  uses the pinned Groovy-era framework & preserves its existing slot prefix.

## Change

`input.h` keeps 32 core slots & appends system L2/R2/L3/R3 at 32..35.
`input.cpp::input_cb` uses those slots in the Menu mapper, accepts stick clicks
for player assignment & keeps state iteration bounded to 32 core slots.
`menu.cpp::HandleUI` appends four prompts after the existing analog stages;
button events can't consume those analog stages.

`joymapping.cpp::map_joystick` translates L2/R2/L3/R3 from system to core slots.
`gamecontroller_db.cpp` accepts `lefttrigger`, `righttrigger`, `leftstick` &
`rightstick`. Trigger axes use the existing positive-edge digital event path.
`Groovy.sv` uses one `J1` list for all players & an explicit `jn` name map.
`J2` never selected player 2: `get_btn()` takes the first `J` declaration.
The new `jn` entry supplies these defaults:

| Core input | Mask | System input |
|---|---:|---|
| Button 1 | 0x0010 | A |
| Button 2 | 0x0020 | B |
| Button 3 | 0x0040 | X |
| Button 4 | 0x0080 | Y |
| Button 5 | 0x0100 | L |
| Button 6 | 0x0200 | R |
| Button 7 | 0x0400 | L2 |
| Button 8 | 0x0800 | R2 |
| Button 9 | 0x1000 | Select |
| Button 10 | 0x2000 | Start |
| L3 | 0x4000 | L3 |
| R3 | 0x8000 | R3 |

Existing explicit core assignments take precedence over these defaults.

System `_v4.map` files contain 144 bytes; the first 128 bytes retain the v3
layout. `load_system_map()` falls back to v3, clears the appended slots & logs
that the extra controls need definition. Groovy core `_v4.map` files remain
128 bytes. `load_core_map()` falls back to v3, preserves nonzero assignments &
fills empty slots 14/15 from the system click mapping. Legacy files remain
untouched until explicit deletion. An explicit v4 core save preserves deliberate
unmapping, including zero L3/R3 slots. Deleting a mapping removes both versions
so a legacy file can't restore the deleted configuration.

The new storage extension & migration are new HPS behavior. evdev events,
primary/alternate state, analog processing, player routing, SPI & UDP packet
formats retain the inherited behavior. No video/audio or JTFRAME files changed.

## Validation

Run from the repository root:

```sh
git clone https://github.com/psakhis/Main_MiSTer.git ../Main_MiSTer
git -C ../Main_MiSTer checkout 0272823a66cb7c601256406a2e80e8c6b2e93e13
python3 tests/run_controller_tests.py ../Main_MiSTer --mutation-check
```

The harness compiles production `input.cpp`, `joymapping.cpp` &
`gamecontroller_db.cpp`, plus functions extracted directly from `user_io.cpp`
& `groovy.cpp`. Only evdev capability discovery, storage, OSD, SPI & network
boundaries are mocked. ASan & UBSan check the execution; leak detection is
turned off because the Work runtime uses ptrace. No physical controller or FPGA
is part of this test.

Coverage includes independent Buttons 1..10; Button 2/3 mapping & held state;
L3/R3 press/release; combined holds & partial release; both players; alternate
sets; analog events & packet bytes; system mapper slots; the 28-button parser
limit; v3/v4 loading, modification & saving. Restoring the old keycode union or
removing click translation or restoring the old mapper limit makes the regression assertions fail.

The complete changed HPS units also receive host compiler checks. The host
compiler reports an inherited pointer-size warning in `menu.cpp::getNet`.
The ARM cross compiler & Quartus aren't installed here. Running
`quartus_sh --flow compile Groovy` returned `command not found`; no new
`output_files/Groovy.rbf` was produced. Existing `.rbf` files are unchanged.

## Build & hardware check

This repository stores an HPS source overlay. Copy its `hps_linux/src/` contents
onto the pinned `psakhis/Main_MiSTer` checkout, then build with the project's
ARM toolchain & Makefile. Use `_AF_XDP=0` for the UDP binary. XDP additionally
needs the project's cross libraries. The existing prebuilt HPS binaries in this
repository do not contain these source changes.

Rebuild & install both the HPS program & core. Building the `.rbf` alone can't
change HPS input handling. Quartus Prime Lite 17.0 should run:

```sh
quartus_sh --flow compile Groovy
```

The fresh core must come from `output_files/Groovy.rbf`. Keep the repaired
JTFRAME entries in `files.qip`.

Define the twelve core inputs in Groovy's controller mapper; this accepts
physical stick clicks directly even with an old system mapping. To use the
extended system mapper, the rebuilt HPS program must also be running in the
Menu core. A stock Menu binary doesn't expose the four appended prompts.

On each player, check Button 2 alone = `0x0020`, Button 3 alone = `0x0040`, both
= `0x0060`, L3 alone = `0x4000`, R3 alone = `0x8000` & both clicks = `0xc000`.
Hold the other player's control while testing releases. Check directions,
triggers, Start/Select, both analog sticks, menu navigation & persistence after
restart. If Button 2/3 still alias, retain the loaded-map diagnostic & evdev
press/release trace to distinguish an existing overlapping map from duplicate
physical events.
