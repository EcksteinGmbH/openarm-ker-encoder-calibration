#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "ref_comp.h"
static double ref(uint16_t r, const ker_cal_t *c){
  double u=(c->n ? (double)((uint32_t)r<<6) : (double)(((uint32_t)r<<6)|(r>>9))), th=r*2.0*M_PI/32768.0, d=0;
  for(int k=0;k<c->n;k++) d+=c->amp[k]*sin((k+1)*th+c->phase[k]*2.0*M_PI/65536.0);
  double o=fmod(u+d,2097152.0); if(o<0)o+=2097152.0; return o;
}
static double maxerr(const ker_cal_t *c,int *at){
  double w=0; for(uint32_t r=0;r<32768;r++){
    double e=fabs((double)ker_compensate((uint16_t)r,c)-ref((uint16_t)r,c)); if(e>1048576)e=2097152-e; if(e>w){w=e;*at=r;}}
  return w;
}
static double sd[65536]; static int si[65536];
#define LSB (360.0/2097152.0)
int main(void){
  for(int a=0;a<65536;a++){ sd[a]=sin(2*M_PI*a/65536.0); si[a]=ker_sin_q15(a); }
  /* for each N: pick per-term (amp,phase) that push the error negative, then fix the final rounding:
     choose among the top candidates of the per-term error so the fractional part is adverse. */
  /* collect candidates with term error < -2.40 LSB */
  static int ca[200000], cg[200000]; static double ce[200000]; int nc=0;
  for(int amp=-32768; amp<=32767; amp++) for(int a=0;a<65536;a++){
    double e=(double)(((int32_t)amp*si[a])>>8) - amp*sd[a]*128.0;
    if(e < -2.40*128 && nc<200000){ca[nc]=amp;cg[nc]=a;ce[nc]=e;nc++;}
  }
  printf("candidates: %d\n",nc);
  for(int N=1;N<=6;N++){
    double best=0; ker_cal_t bc; int bat=0;
    srand(N);
    for(int trial=0;trial<3000;trial++){
      ker_cal_t c; c.n=N; for(int k=0;k<6;k++){c.amp[k]=0;c.phase[k]=0;}
      for(int k=0;k<N;k++){ int i=rand()%nc; c.amp[k]=ca[i]; c.phase[k]=cg[i]; }
      /* quick eval at r=0 only */
      double e=fabs((double)ker_compensate(0,&c)-ref(0,&c)); if(e>1048576)e=2097152-e;
      if(e>best){best=e;bc=c;}
    }
    double full=maxerr(&bc,&bat);
    printf("N=%d constructed worst: %.3f LSB = %.6f deg (full sweep max %.3f LSB at r=%d)  amps:",N,best,best*LSB,full,bat);
    for(int k=0;k<N;k++) printf(" %d/%u",bc.amp[k],bc.phase[k]); printf("\n");
  }
}
