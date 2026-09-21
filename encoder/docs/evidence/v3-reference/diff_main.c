/* Differential test: identical source built for host and for AVR. Each prints one FNV-1a
 * hash per coefficient set over ker_compensate() for all 32768 sensor codes. Equal hashes
 * => the AVR build is bit-identical to the host build, so host accuracy results transfer. */
#include <stdint.h>
#include "ref_comp.h"
#ifdef __AVR__
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
static void out_c(char c){ while(!(UCSR0A&(1<<UDRE0))); UDR0=c; }
static void out_init(void){ UBRR0=0; UCSR0B=(1<<TXEN0); }
#else
#include <stdio.h>
static void out_c(char c){ putchar(c); }
static void out_init(void){}
#endif
static void out_hex32(uint32_t v){ for(int8_t i=28;i>=0;i-=4) out_c("0123456789abcdef"[(v>>i)&15]); }
static uint32_t lcg=0x12345678u;
static uint16_t rnd(void){ lcg=lcg*1664525u+1013904223u; return (uint16_t)(lcg>>16); }
int main(void){
  out_init();
  ker_cal_t c;
  /* sets 0-13: N=6 except 13 (N=3); sets 14-20: N = 0,1,2,3,4,5,6 with random coefficients,
   * so the uncalibrated path and every loop count are exercised on both targets */
  for(uint8_t set=0; set<21; set++){
    c.n = (set >= 14) ? (uint8_t)(set - 14) : 6;
    for(uint8_t k=0;k<6;k++){
      if(set==0){ c.amp[k]=(int16_t)(k==0?8738:k==1?5243:k==2?1748:k==3?173:k==4?69:15); c.phase[k]=(uint16_t)(k*9000u); }
      else if(set==1){ c.amp[k]=32767;  c.phase[k]=(uint16_t)(k*11111u); }   /* max positive */
      else if(set==2){ c.amp[k]=-32768; c.phase[k]=(uint16_t)(k*7777u);  }   /* max negative */
      else if(set==3){ c.amp[k]=(k&1)?-32768:32767; c.phase[k]=0; }         /* alternating */
      else { c.amp[k]=(int16_t)rnd(); c.phase[k]=rnd(); }                    /* random */
    }
    if(set==13) c.n=3;                                                        /* short N */
    uint32_t h=2166136261u;
    for(uint16_t r=0;r<32768;r++){
      uint32_t o=ker_compensate(r,&c);
      for(uint8_t b=0;b<3;b++){ h^=(uint8_t)(o>>(8*b)); h*=16777619u; }
    }
    out_hex32(h); out_c('\n');
  }
#ifdef __AVR__
  cli(); sleep_enable(); sleep_cpu();
#endif
  return 0;
}
