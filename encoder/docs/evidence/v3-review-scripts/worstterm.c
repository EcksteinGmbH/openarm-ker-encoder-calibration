#include <stdio.h>
#include <math.h>
#include "ref_comp.h"
/* per-term error in Q7 (1/128 LSB): ((amp*s)>>8) - amp*sin(arg)*128, exhaustive over amp, arg */
static double sd[65536]; static int si[65536];
int main(void){
  for(int a=0;a<65536;a++){ sd[a]=sin(2*M_PI*a/65536.0); si[a]=ker_sin_q15(a); }
  double mx=-1e9,mn=1e9; int amx=0,gmx=0,amn=0,gmn=0;
  for(int amp=-32768; amp<=32767; amp++){
    for(int a=0;a<65536;a++){
      double e=(double)(((int32_t)amp*si[a])>>8) - amp*sd[a]*128.0;
      if(e>mx){mx=e;amx=amp;gmx=a;} if(e<mn){mn=e;amn=amp;gmn=a;}
    }
  }
  printf("max term err %+.4f LSB at amp=%d arg=%d ; min %+.4f LSB at amp=%d arg=%d\n",mx/128,amx,gmx,mn/128,amn,gmn);
}
