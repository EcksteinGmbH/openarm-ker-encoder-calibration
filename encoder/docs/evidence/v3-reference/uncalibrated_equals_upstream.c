#include <stdio.h>
#include "ref_comp.h"
int main(void){ ker_cal_t c={.n=0}; unsigned bad=0;
  for(unsigned r=0;r<32768;r++){ unsigned up=((unsigned)r<<6)|(r>>9); if(ker_compensate((uint16_t)r,&c)!=up) bad++; }
  printf("n=0 vs upstream main.cpp:367-368 mapping, all 32768 codes: %u mismatches\n",bad); return bad!=0; }
