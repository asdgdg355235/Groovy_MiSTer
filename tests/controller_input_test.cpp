#include <cassert>
#include <vector>
#include <string>
#include <map>
#include <fstream>
#include <sstream>
#include <sys/socket.h>
#include <netinet/in.h>
#include <cstdarg>
#undef AF_MAX
#include "../hps_linux/src/input.cpp"
#include "../hps_linux/src/joymapping.cpp"
#include "../hps_linux/src/gamecontroller_db.cpp"

// Replace only external hardware, OSD, file storage and network boundaries.
static bool menu_core;
static std::vector<unsigned> key_codes;
static std::map<std::string, std::vector<uint8_t>> files;
static std::string db_line;
static bool db_read;
static std::vector<uint16_t> spi_words;
static std::vector<uint8_t> packet;
static std::vector<char> queuedRegistration;
static uint16_t registrationPort;
static int joyswap, joy_transl;
static int doXDPServer, doJoyInputs = 2, isConnectedInputs = 1, sockfdInputs;
static sockaddr_in clientaddrInputs;
static socklen_t clilen = sizeof(clientaddrInputs);
static uint8_t sendbufInputs[128];
static bool triggerExtension;
static int16_t triggerPositions[2][2] = {{-1, -1}, {-1, -1}};
static std::map<std::pair<int, unsigned>, input_absinfo> fixtureAxes;
struct TestPoc {
    uint32_t PoC_frame_ddr = 12, PoC_joystick_keep_alive = 0;
    uint8_t PoC_joystick_order = 0;
    uint32_t PoC_joystick_map1 = 0, PoC_joystick_map2 = 0;
    char PoC_joystick_l_analog_X1 = 0, PoC_joystick_l_analog_Y1 = 0;
    char PoC_joystick_r_analog_X1 = 0, PoC_joystick_r_analog_Y1 = 0;
    char PoC_joystick_l_analog_X2 = 0, PoC_joystick_l_analog_Y2 = 0;
    char PoC_joystick_r_analog_X2 = 0, PoC_joystick_r_analog_Y2 = 0;
} test_poc, *poc = &test_poc;
#define LOG(...) ((void)0)
#include "production_functions.h"

cfg_t cfg = {};
char is_menu() { return menu_core; }
char is_psx() { return 0; }
char is_n64() { return 0; }
char is_groovy() { return 1; }
char is_minimig() { return 0; }
int hasAPI1_5() { return 1; }
char user_io_osd_is_visible() { return 0; }
int video_fb_state() { return 0; }
int menu_allow_cfg_switch() { return 0; }
void menu_key_set(unsigned int) {}
void user_io_set_ini(int) {}
void user_io_check_reset(unsigned short, char) {}
int user_io_get_kbdemu() { return 0; }
void user_io_kbd(unsigned short, int) {}
void Info(const char*, int, int, int, int) {}
void InfoMessage(const char*, int, const char*) {}
void n64_joy_emu(int, int, int*, int*, int, float) { assert(false); }
void stick_swap(int num, int stick, int* num2, int* stick2) { *num2 = num; *stick2 = stick; }
unsigned long GetTimer(unsigned long offset) { return 10 + offset; }
unsigned long CheckTimer(unsigned long) { return 0; }
uint16_t spi_uio_cmd(uint16_t) { return 0; }
uint16_t spi_uio_cmd_cont(uint16_t cmd) { spi_words.clear(); return cmd; }
uint16_t fpga_spi(uint16_t word) { spi_words.push_back(word); return 0; }
void DisableIO() {}
void user_io_l_analog_joystick(unsigned char n, char x, char y) { groovy_send_analog(n, 0, x, y); }
void user_io_r_analog_joystick(unsigned char n, char x, char y) { groovy_send_analog(n, 1, x, y); }
char* user_io_get_core_name(int) { static char name[] = "Groovy"; return name; }
static std::string conf_buttons, conf_names;
void user_io_read_confstr() {}
char* user_io_get_confstr(int n) {
    return n == 2 ? &conf_buttons[0] : n == 3 ? &conf_names[0] : nullptr;
}
int FileLoadConfig(const char* name, void* data, int size) {
    auto it = files.find(name);
    if (it == files.end()) return 0;
    int count = std::min(size, int(it->second.size()));
    if (data) memcpy(data, it->second.data(), count);
    return data ? count : it->second.size();
}
int FileSaveConfig(const char* name, void* data, int size) {
    files[name] = std::vector<uint8_t>((uint8_t*)data, (uint8_t*)data + size);
    return size;
}
int FileDeleteConfig(const char* name) { return files.erase(name); }
fileTextReader::fileTextReader() {}
fileTextReader::~fileTextReader() {}
bool FileOpenTextReader(fileTextReader*, const char*) { db_read = false; return !db_line.empty(); }
const char* FileReadLine(fileTextReader*) {
    if (db_read) return nullptr;
    db_read = true;
    return db_line.c_str();
}
extern "C" int ioctl(int fd, unsigned long request, ...) noexcept {
    va_list ap; va_start(ap, request); auto dst = va_arg(ap, uint8_t*); va_end(ap);
    auto size = _IOC_SIZE(request);
    memset(dst, 0, size);
    if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(EV_KEY, 0))) {
        for (auto key : key_codes) dst[key / 8] |= 1 << (key % 8);
    } else if (_IOC_NR(request) == _IOC_NR(EVIOCGBIT(EV_ABS, 0))) {
        for (auto key : {ABS_X, ABS_Y, ABS_RX, ABS_RY, ABS_Z, ABS_RZ})
            dst[key / 8] |= 1 << (key % 8);
        for (auto& item : fixtureAxes) {
            const auto axis = item.first.second;
            if (item.first.first == fd) dst[axis / 8] |= 1 << (axis % 8);
        }
    } else if (_IOC_NR(request) >= _IOC_NR(EVIOCGABS(0)) &&
               _IOC_NR(request) <= _IOC_NR(EVIOCGABS(ABS_MAX))) {
        const auto it = fixtureAxes.find({fd, _IOC_NR(request) - _IOC_NR(EVIOCGABS(0))});
        if (it == fixtureAxes.end()) return -1;
        memcpy(dst, &it->second, sizeof(input_absinfo));
    } else { assert(false); }
    return size;
}
extern "C" ssize_t sendto(int, const void* data, size_t size, int,
                           const sockaddr*, socklen_t) {
    packet.assign((const uint8_t*)data, (const uint8_t*)data + size);
    return size;
}

static void reset_device(int dev, int player) {
    memset(&input[dev], 0, sizeof(input[dev]));
    input[dev].bind = -1;
    input[dev].num = player;
    input[dev].has_map = input[dev].has_mmap = input[dev].has_jkmap = 1;
    joy[player - 1] = 0;
}
static void event(int dev, unsigned code, int value) {
    input_event ev = {}; ev.type = EV_KEY; ev.code = code; ev.value = value;
    input_cb(&ev, nullptr, dev);
}
static uint16_t wire_mask(int player) {
    assert(packet.size() == 9 || packet.size() == 17 || packet.size() == 21);
    return packet[5 + player * 2] | (packet[6 + player * 2] << 8);
}
static void publish(int dev) {
    user_io_digital_joystick(dev, joy[dev], 0);
    assert(spi_words[0] == wire_mask(dev));
}
static void db_parse(const char* text, uint32_t* map, int fd = 0) {
    std::string line(text); char guid[] = "test";
    assert(parse_mapping_string(&line[0], guid, fd, map));
}

extern "C" ssize_t recvfrom(int fd, void* data, size_t size, int flags, sockaddr* addr, socklen_t* addrlen)
{
    assert(fd == sockfdInputs && flags == MSG_TRUNC && *addrlen == sizeof(sockaddr_in));
    if (queuedRegistration.empty()) return -1;
    auto* endpoint = reinterpret_cast<sockaddr_in*>(addr);
    endpoint->sin_family = AF_INET;
    endpoint->sin_port = htons(registrationPort);
    const auto length = queuedRegistration.size();
    memcpy(data, queuedRegistration.data(), std::min(size, length));
    queuedRegistration.clear();
    return length;
}

static void trigger_tests()
{
    constexpr char registration[] = "GMTR\x01";
    assert(!groovy_trigger_registration("\0", 1));
    assert(!groovy_trigger_registration(registration, 4));
    assert(!groovy_trigger_registration(registration, 6));
    assert(!groovy_trigger_registration("GMTR\x02", 5));
    assert(groovy_trigger_registration(registration, 5));

    reset_device(0, 1);
    reset_device(1, 2);
    pool[0].fd = 40;
    pool[1].fd = 41;
    fixtureAxes[{40, ABS_THROTTLE}] = {100, -100, 1100, 0, 0, 0};
    fixtureAxes[{40, ABS_RUDDER}] = {900, -100, 1100, 0, 0, 0};
    fixtureAxes[{41, ABS_GAS}] = {0, 0, 1023, 0, 0, 0};
    fixtureAxes[{41, ABS_BRAKE}] = {0, 0, 1023, 0, 0, 0};
    remember_trigger_rest(0);
    remember_trigger_rest(1);
    db_parse("a:b0,lefttrigger:a8,righttrigger:a99,", input[0].mmap, 40);
    assert(!input[0].mmap[SYS_BTN_L2] && !input[0].mmap[SYS_BTN_R2]);
    db_parse("lefttrigger:a6,righttrigger:a7~,", input[0].mmap, 40);
    assert(input[0].mmap[SYS_BTN_L2] == KEY_EMU + 2 * ABS_THROTTLE + 1);
    assert(input[0].mmap[SYS_BTN_R2] == KEY_EMU + 2 * ABS_RUDDER);
    map_joystick(input[0].map, input[0].mmap);
    // Primary digital binding with an alternate mapped physical axis.
    input[1].map[12] = BTN_TL2 | ((KEY_EMU + 2 * ABS_GAS + 1) << 16);
    input[1].map[13] = BTN_TR2;
    input[1].db_trigger_keys[1] = KEY_EMU + 2 * ABS_BRAKE + 1;
    auto axisEvent = [](int dev, unsigned code, int value) {
        input_absinfo info{};
        assert(ioctl(pool[dev].fd, EVIOCGABS(code), &info) >= 0);
        input_event ev{};
        ev.type = EV_ABS;
        ev.code = code;
        ev.value = value;
        input_cb(&ev, &info, dev);
    };
    auto values = [](uint8_t l1, uint8_t r1, uint8_t l2, uint8_t r2) {
        assert(packet.size() == 21);
        assert(packet[17] == l1 && packet[18] == r1 && packet[19] == l2 && packet[20] == r2);
    };

    registrationPort = 34567;
    queuedRegistration = {0};
    assert(groovy_register_udp_inputs() && !triggerExtension);
    assert(ntohs(clientaddrInputs.sin_port) == registrationPort);
    doJoyInputs = 1;
    publish(0);
    assert(packet.size() == 9);
    doJoyInputs = 2;
    publish(1);
    assert(packet.size() == 17);
    groovy_send_analog(0, 0, 1, -2);
    groovy_send_analog(0, 1, 3, -4);
    groovy_send_analog(1, 0, 5, -6);
    groovy_send_analog(1, 1, 7, -8);
    const auto legacy = packet;
    assert(std::vector<uint8_t>(legacy.begin() + 9, legacy.end()) ==
        (std::vector<uint8_t>{1, 254, 3, 252, 5, 250, 7, 248}));
    axisEvent(0, ABS_THROTTLE, 300);
    assert(packet == legacy); // Legacy clients get no trigger-only snapshots.
    queuedRegistration.assign(registration, registration + 5);
    ++registrationPort;
    assert(groovy_register_udp_inputs() && triggerExtension);
    assert(ntohs(clientaddrInputs.sin_port) == registrationPort);
    assert(!groovy_register_udp_inputs() && triggerExtension);
    groovy_send_joysticks();
    assert(std::equal(legacy.begin(), legacy.end(), packet.begin()));
    values(51, 0, 0, 0);
    axisEvent(0, ABS_RUDDER, 400);
    axisEvent(1, ABS_GAS, 700);
    axisEvent(1, ABS_BRAKE, 900);
    values(51, 128, 174, 224);
    const auto heldOrder = packet[4];
    axisEvent(1, ABS_BRAKE, 900);
    assert(packet[4] == heldOrder);
    for (int value = 100, last = 0; value <= 1100; value += 10) {
        axisEvent(0, ABS_THROTTLE, value);
        assert(packet[17] >= last && packet[18] == 128 && packet[19] == 174 && packet[20] == 224);
        last = packet[17];
    }
    values(255, 128, 174, 224);
    axisEvent(0, ABS_RUDDER, -100);
    values(255, 255, 174, 224);
    axisEvent(0, ABS_RUDDER, 900);
    axisEvent(0, ABS_THROTTLE, 100);
    values(0, 0, 174, 224);

    // Physical analog and digital sources retain independent values.
    event(1, BTN_TL2, 1);
    event(1, BTN_TR2, 1);
    publish(1);
    assert(wire_mask(1) == (JOY_L2 | JOY_R2));
    values(0, 0, 174, 224);
    axisEvent(0, ABS_THROTTLE, 300);
    clear_groovy_device_triggers(1); // Same reset used on evdev loss.
    publish(1);
    assert(wire_mask(1) == 0);
    values(51, 0, 0, 0);
    assign_player(0, 3);
    values(0, 0, 0, 0);

    input[1].map[12] = BTN_TL2;
    input[1].db_trigger_keys[1] = 0;
    event(1, BTN_TL2, 1);
    publish(1);
    values(0, 0, 255, 0);
    event(1, BTN_TL2, 0);
    publish(1);
    values(0, 0, 0, 0);

    doJoyInputs = 1;
    groovy_send_joysticks();
    assert(packet.size() == 9);
    doJoyInputs = 2;
    queuedRegistration.assign(registration, registration + 6);
    assert(groovy_register_udp_inputs() && !triggerExtension);
    groovy_send_joysticks();
    assert(packet.size() == 17);
    puts("PASS: trigger calibration, polarity, both slots, digital fallback, reset, registration and packet lengths");
}

int main(int argc, char** argv) {
    assert(argc == 2);
    std::ifstream file(argv[1]); std::stringstream ss; ss << file.rdbuf();
    auto sv = ss.str(); auto start = sv.find("\"J1,"); assert(start != std::string::npos);
    conf_buttons = sv.substr(start + 1, sv.find(';', start) - start - 1);
    start = sv.find("\"jn,"); assert(start != std::string::npos);
    conf_names = sv.substr(start + 1, sv.find(';', start) - start - 1);
    parse_buttons(); assert(joy_bcount == 12);
    assert(!strcmp(joy_bnames[10], "L3") && !strcmp(joy_bnames[11], "R3"));
    static_assert(NUMBUTTONS == 32, "64-bit state holds exactly two 32-bit sets");
    static_assert(SYS_BTN_L3 != SYS_MS_DOWN, "stick clicks cannot overwrite mouse slots");
    key_codes = {BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST, BTN_TL, BTN_TR,
                 BTN_TL2, BTN_TR2, BTN_SELECT, BTN_START, BTN_THUMBL, BTN_THUMBR};
    reset_device(0, 1); reset_device(1, 2);
    const int slots[] = {SYS_BTN_A, SYS_BTN_B, SYS_BTN_X, SYS_BTN_Y, SYS_BTN_L,
        SYS_BTN_R, SYS_BTN_L2, SYS_BTN_R2, SYS_BTN_SELECT, SYS_BTN_START, SYS_BTN_L3, SYS_BTN_R3};
    // b-indexes enumerate actual supported evdev codes in increasing order.
    const char* database = "b:b0,a:b1,y:b2,x:b3,leftshoulder:b4,rightshoulder:b5,lefttrigger:b6,righttrigger:b7,back:b8,start:b9,leftstick:b10,rightstick:b11,";
    db_parse(database, input[0].mmap);
    for (int i = 0; i < 12; ++i) assert(input[0].mmap[slots[i]] == key_codes[i]);
    // Regression: reloading changed DB assignments used to OR old/new keycodes.
    // 0x131 | 0x130 == 0x131, aliasing Button 2 with Button 3.
    input[0].mmap[SYS_BTN_B] = 0x131;
    db_parse("a:b0,y:b1,", input[0].mmap);
    assert(input[0].mmap[SYS_BTN_B] == 0x130);
    assert(input[0].mmap[SYS_BTN_X] == 0x131);
    db_parse("a:b1,a:b0,y:b1,", input[0].mmap);
    assert(input[0].mmap[SYS_BTN_B] == 0x130 && input[0].mmap[SYS_BTN_X] == 0x131);
    db_parse(database, input[0].mmap);
    for (int dev = 0; dev < 2; ++dev) {
        if (dev) memcpy(input[dev].mmap, input[0].mmap, sizeof(input[0].mmap));
        map_joystick(input[dev].map, input[dev].mmap);
        for (int i = 0; i < 12; ++i) {
            assert(input[dev].map[4 + i] == key_codes[i]);
            event(dev, key_codes[i], 1);
            assert(joy[dev] == (uint64_t(1) << (4 + i)));
            publish(dev); assert(wire_mask(dev) == (1 << (4 + i)));
            event(dev, key_codes[i], 0); publish(dev); assert(wire_mask(dev) == 0);
        }
    }
    event(0, BTN_EAST, 1); assert(joy[0] == JOY_BTN2 && joy[1] == 0);
    event(0, BTN_NORTH, 1); assert(joy[0] == (JOY_BTN2 | JOY_BTN3));
    event(0, BTN_EAST, 0); assert(joy[0] == JOY_BTN3);
    event(0, BTN_NORTH, 0);
    event(0, BTN_THUMBL, 1); event(0, BTN_THUMBR, 1);
    event(1, BTN_THUMBR, 1); assert(joy[0] == 0xc000 && joy[1] == JOY_R3);
    event(0, BTN_THUMBL, 0); publish(0); assert(wire_mask(0) == JOY_R3 && wire_mask(1) == 0);
    publish(1); assert(wire_mask(1) == JOY_R3);
    event(0, BTN_THUMBR, 0); event(1, BTN_THUMBR, 0);
    // Both directions and analog processing still traverse the real handler.
    input[0].map[0] = KEY_EMU + 1;
    event(0, KEY_EMU + 1, 1); assert(joy[0] == JOY_RIGHT);
    event(0, KEY_EMU + 1, 0); assert(!joy[0]);
    input[0].mmap[SYS_AXIS1_X] = 0x20000 | ABS_X;
    input[0].stick_l[0] = SYS_AXIS1_X;
    input_absinfo axis = {}; axis.minimum = -32768; axis.maximum = 32767;
    input_event analog = {}; analog.type = EV_ABS; analog.code = ABS_X; analog.value = 16384;
    input_cb(&analog, &axis, 0); assert(poc->PoC_joystick_l_analog_X1 != 0);
    assert(packet.size() == 17 && packet[9] == uint8_t(poc->PoC_joystick_l_analog_X1));
    // Core mapper writes and releases successive slots independently.
    start_map_setting(16);
    for (int i = 0; i < 16; ++i) { event(0, 0x200 + i, 1); event(0, 0x200 + i, 0); }
    assert(input[0].map[5] == 0x205 && input[0].map[6] == 0x206);
    finish_map_setting(0);
    assert(files["inputs/Groovy_input__v4.map"].size() == 128);
    uint32_t saved[NUMSYSTEMBUTTONS] = {};
    assert(load_map(get_map_name(0, 0), saved, 128) == 128);
    assert(saved[5] == 0x205 && saved[6] == 0x206);
    saved[5] = 0x250; save_map(get_map_name(0, 0), saved, 128);
    memset(saved, 0, sizeof(saved)); load_map(get_map_name(0, 0), saved, 128);
    assert(saved[5] == 0x250 && saved[6] == 0x206);
    // Primary + alternate state: release one while another is held.
    reset_device(0, 1); input[0].map[5] = BTN_EAST | (BTN_NORTH << 16);
    event(0, BTN_EAST, 1); event(0, BTN_NORTH, 1);
    event(0, BTN_EAST, 0); publish(0); assert(wire_mask(0) == JOY_BTN2);
    event(0, BTN_NORTH, 0); publish(0); assert(!wire_mask(0));
    // Core v3 adds only empty click slots; v4 preserves deliberate unmapping.
    memset(saved, 0, sizeof(saved)); saved[5] = BTN_EAST; saved[6] = BTN_NORTH;
    FileDeleteConfig("inputs/Groovy_input__v4.map");
    FileSaveConfig("inputs/Groovy_input__v3.map", saved, 128);
    input[0].mmap[SYS_BTN_L3] = BTN_THUMBL; input[0].mmap[SYS_BTN_R3] = BTN_THUMBR;
    assert(load_core_map(0)); assert(input[0].map[5] == BTN_EAST && input[0].map[6] == BTN_NORTH);
    assert(input[0].map[14] == BTN_THUMBL && input[0].map[15] == BTN_THUMBR);
    saved[14] = 0x280; FileSaveConfig("inputs/Groovy_input__v3.map", saved, 128);
    assert(load_core_map(0)); assert(input[0].map[14] == 0x280);
    FileSaveConfig("inputs/Groovy_input__v4.map", saved, 128);
    assert(load_core_map(0)); assert(input[0].map[15] == 0);
    // v3 migration preserves every mouse/menu/axis word; v4 adds new slots.
    menu_core = true;
    for (int i = 0; i < NUMBUTTONS; ++i) saved[i] = 0x10000 + i;
    FileSaveConfig("inputs/input__v3.map", saved, 128);
    assert(load_system_map(0));
    assert(!memcmp(saved, input[0].mmap, 128));
    for (int i = SYS_BTN_L2; i < NUMSYSTEMBUTTONS; ++i) assert(input[0].mmap[i] == 0);
    // Keyboard button events must not consume the two analog mapper stages.
    start_map_setting(SYS_MAP_COUNT); mapping_dev = 0; mapping_type = 1;
    mapping_button = 23; input[0].map[SYS_BTN_MENU_FUNC] = 0x1300131;
    event(0, 0x260, 1); event(0, 0x260, 0);
    assert(mapping_button == 23 && input[0].map[SYS_BTN_MENU_FUNC] == 0x1300131);
    assert(!system_map_button_position(24, 1));
    assert(system_map_button_position(25, 1) && system_map_slot(28) == SYS_BTN_R3);
    // Actual Menu mapper extension, after the unchanged analog stages.
    start_map_setting(SYS_MAP_COUNT); mapping_dev = 0; mapping_type = 1;
    mapping_button = SYS_MAP_EXT_FIRST;
    for (int i = 0; i < 4; ++i) {
        event(0, 0x260 + i, 1); event(0, 0x260 + i, 0);
        assert(input[0].map[SYS_BTN_L2 + i] == unsigned(0x260 + i));
    }
    assert(mapping_button == SYS_MAP_COUNT);
    finish_map_setting(0); assert(files["inputs/input__v4.map"].size() == 144);
    assert(load_system_map(0)); assert(input[0].mmap[SYS_BTN_L3] == 0x262);
    menu_core = false;
    trigger_tests();
    // Config parser accepts its full 28-button limit without touching system slots.
    menu_core = false; conf_buttons = "J1";
    for (int i = 0; i < 28; ++i) conf_buttons += ",B" + std::to_string(i);
    parse_buttons(); assert(joy_bcount == 28);
    puts("PASS: database reload, Buttons 1..10, Button 2/3 independence, L3/R3 press/release, both ports, combined holds, alternate sets, analog, mapper slots, v3/v4 save/load, 28-button limit");
}
