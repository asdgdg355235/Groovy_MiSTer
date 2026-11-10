#ifndef GROOVY_H
#define GROOVY_H

void groovy_poll();
void groovy_stop();
void groovy_user_io_file_gmc(const char* name);
void groovy_send_joystick(unsigned char joystick, uint32_t map);
void groovy_send_analog(unsigned char joystick, unsigned char analog, char valueX, char valueY);
// A value of -1 uses the corresponding digital button as a 0/255 fallback.
void groovy_set_triggers(unsigned joystick, int16_t left, int16_t right);
void groovy_send_keyboard(uint16_t key, int press);
void groovy_send_mouse(unsigned char ps2, unsigned char x, unsigned char y, unsigned char z);

#endif
