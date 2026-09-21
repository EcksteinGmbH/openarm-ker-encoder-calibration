#include <stdint.h>
#include <avr/io.h>
/* mirror of main.cpp's bit-bang: CLK=16, DATA=14, CS=13 on ATtiny1616.
   megaTinyCore digitalWriteFast on a constant pin compiles to a single sbi/cbi. */
#define CLK_bm (1<<2)   /* placeholder port bits */
#define DAT_bm (1<<1)
static inline void clkHigh(void){ VPORTA.OUT |= CLK_bm; }
static inline void clkLow(void) { VPORTA.OUT &= ~CLK_bm; }
static inline void dataWrite(uint8_t v){ if(v) VPORTA.OUT |= DAT_bm; else VPORTA.OUT &= ~DAT_bm; }
static inline uint8_t dataRead(void){ return (VPORTA.IN & DAT_bm)?1:0; }
void sscWrite16(uint16_t v){ for(int8_t i=15;i>=0;--i){ dataWrite((v>>i)&1); clkHigh(); clkLow(); } }
uint16_t sscRead16(void){ uint16_t v=0; for(int8_t i=15;i>=0;--i){ v<<=1; clkHigh(); clkLow(); v|=dataRead(); } return v; }
