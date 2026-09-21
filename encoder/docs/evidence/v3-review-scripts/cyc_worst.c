/* Cycle measurement of ker_compensate() on an AVR core under simavr, Timer1 at prescaler 1.
 * Reports min/max cycles over a stride through all sensor codes, for several N_HARM. */
#include <stdint.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
#include "ref_comp.h"
static void out_c(char c){ while(!(UCSR0A&(1<<UDRE0))); UDR0=c; }
static void out_u(uint16_t v){ char b[6]; int8_t i=0; do{ b[i++]='0'+v%10; v/=10; }while(v); while(i) out_c(b[--i]); }
static void out_s(const char*s){ while(*s) out_c(*s++); }
volatile uint32_t sink;
int main(void){
  UBRR0=0; UCSR0B=(1<<TXEN0); TCCR1A=0; TCCR1B=(1<<CS10);
  /* measure empty-bracket overhead */
  uint16_t t0=TCNT1; uint16_t t1=TCNT1; uint16_t ovh=t1-t0;
  ker_cal_t c;
  const int16_t amp[6]={-8738,-5243,-1748,-173,-69,-15};
  for(uint8_t n=0;n<=6;n++){
    c.n=n; for(uint8_t k=0;k<6;k++){ c.amp[k]=amp[k]; c.phase[k]=0xE000u; }
    uint16_t mn=0xFFFF,mx=0;
    for(uint16_t r=0;r<32768;r+=13){
      uint16_t a=TCNT1; sink=ker_compensate(r,&c); uint16_t b=TCNT1;
      uint16_t d=(uint16_t)(b-a-ovh); if(d<mn)mn=d; if(d>mx)mx=d;
    }
    out_s("N="); out_u(n); out_s(" min="); out_u(mn); out_s(" max="); out_u(mx); out_c('\n');
  }
  cli(); sleep_enable(); sleep_cpu();
}
