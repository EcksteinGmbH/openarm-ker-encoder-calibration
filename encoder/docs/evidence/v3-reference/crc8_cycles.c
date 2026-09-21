#include <stdint.h>
#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/sleep.h>
/* TLE5012B safety-word CRC: poly 0x1D, init 0xFF, final ~. Table-driven vs Infineon's bitwise. */
static uint8_t tab[256];
static uint8_t crc_bit(const uint8_t*d,uint8_t n){uint8_t c=0xFF;for(uint8_t i=0;i<n;i++){c^=d[i];for(uint8_t b=0;b<8;b++)c=(c&0x80)?(uint8_t)((c<<1)^0x1D):(uint8_t)(c<<1);}return (uint8_t)~c;}
static uint8_t crc_tab(const uint8_t*d,uint8_t n){uint8_t c=0xFF;for(uint8_t i=0;i<n;i++)c=tab[c^d[i]];return (uint8_t)~c;}
static void out_c(char c){ while(!(UCSR0A&(1<<UDRE0))); UDR0=c; }
static void out_u(uint16_t v){ char b[6]; int8_t i=0; do{ b[i++]='0'+v%10; v/=10; }while(v); while(i) out_c(b[--i]); }
volatile uint8_t sink;
int main(void){
  UBRR0=0; UCSR0B=(1<<TXEN0); TCCR1A=0; TCCR1B=(1<<CS10);
  for(uint16_t i=0;i<256;i++){uint8_t c=(uint8_t)i;for(uint8_t b=0;b<8;b++)c=(c&0x80)?(uint8_t)((c<<1)^0x1D):(uint8_t)(c<<1);tab[i]=c;}
  uint8_t buf[8]={0x80,0x05,0x12,0x34,0x56,0x78,0x9a,0xbc}; /* cmd + STAT + ACSTAT + AVAL = 8 bytes */
  uint16_t ovh; { uint16_t a=TCNT1, b=TCNT1; ovh=b-a; }
  uint16_t a=TCNT1; sink=crc_bit(buf,8); uint16_t tb=TCNT1-a-ovh;
  a=TCNT1; sink=crc_tab(buf,8); uint16_t tt=TCNT1-a-ovh;
  uint8_t ok=1; for(uint16_t s=0;s<2000;s++){ for(uint8_t i=0;i<8;i++) buf[i]=(uint8_t)(buf[i]*29+s+i); if(crc_bit(buf,8)!=crc_tab(buf,8)) ok=0; }
  out_c('b');out_u(tb);out_c(' ');out_c('t');out_u(tt);out_c(' ');out_c('e');out_u(ok);out_c('\n');
  cli(); sleep_enable(); sleep_cpu();
}
