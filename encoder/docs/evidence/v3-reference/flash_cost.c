/* Flash cost of ker_compensate() on ATtiny1616: build twice, with and without -DWITH, and
 * subtract .text+.rodata. -ffunction-sections -Wl,--gc-sections so unused code is dropped. */
#include "ref_comp.h"
volatile uint32_t sink; volatile uint16_t in; ker_cal_t c;
int main(void){ for(;;){
#ifdef WITH
 sink=ker_compensate(in,&c);
#else
 sink=((uint32_t)in<<6)|(in>>9);
#endif
}}
