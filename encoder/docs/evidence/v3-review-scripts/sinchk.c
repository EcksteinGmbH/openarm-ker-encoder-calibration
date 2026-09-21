#include <stdio.h>
#include <math.h>
#include "ref_comp.h"
extern const int16_t ker_sinq[];
int main(void){
  long maxp=0; double maxe=0; int amaxe=0; int minv=99999,maxv=-99999; int asym=0;
  for(long a=0;a<65536;a++){
    unsigned x=a&0x3FFF; if((a>>14)&1) x=0x4000-x;
    unsigned idx=x>>7, frac=x&127;
    long p=(long)(ker_sinq[idx+1]-ker_sinq[idx])*frac+64; if(p>maxp)maxp=p;
    if(ker_sinq[idx+1]-ker_sinq[idx]<0) printf("neg step at %u\n",idx);
    int s=ker_sin_q15((uint16_t)a); if(s<minv)minv=s; if(s>maxv)maxv=s;
    if(ker_sin_q15((uint16_t)(65536-a)) != -s) asym++;
    double e=fabs(s-32767.0*sin(2*M_PI*a/65536.0)); if(e>maxe){maxe=e;amaxe=a;}
  }
  printf("max interp product %ld, sin range [%d,%d], antisymmetry violations %d, max |s-32767 sin| = %.3f Q15 at a=%d\n",maxp,minv,maxv,asym,maxe,amaxe);
  double me2=0; for(long a=0;a<65536;a++){double e=fabs(ker_sin_q15(a)-32768.0*sin(2*M_PI*a/65536.0)); if(e>me2)me2=e;}
  printf("max |s-32768 sin| (the scale ker_compensate assumes, >>15) = %.3f Q15\n",me2);
}
