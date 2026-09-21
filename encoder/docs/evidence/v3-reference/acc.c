#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "ref_comp.h"
/* double reference of the SAME model, same argument definition (theta from raw15) */
static double ref(uint16_t r, const ker_cal_t *c){
  double u=(c->n ? (double)((uint32_t)r<<6) : (double)(((uint32_t)r<<6)|(r>>9))), th=r*2.0*M_PI/32768.0, d=0;
  for(int k=0;k<c->n;k++) d+=c->amp[k]*sin((k+1)*th+c->phase[k]*2.0*M_PI/65536.0);
  double o=fmod(u+d,2097152.0); if(o<0)o+=2097152.0; return o;
}
static double maxerr(const ker_cal_t *c){
  double w=0; for(uint32_t r=0;r<32768;r++){
    double e=fabs((double)ker_compensate((uint16_t)r,c)-ref((uint16_t)r,c)); if(e>1048576)e=2097152-e; if(e>w)w=e;}
  return w;
}
#define LSB (360.0/2097152.0)
int main(void){
  ker_cal_t c; c.n=6;
  /* realistic: H1<=1.5deg, geometric decay, random phases */
  double wr=0; srand(1);
  for(int t=0;t<300;t++){ double a=(rand()%8738); for(int k=0;k<6;k++){c.amp[k]=(int16_t)((rand()&1?1:-1)*a); a/=1.7; c.phase[k]=rand()&0xFFFF;}
    double e=maxerr(&c); if(e>wr)wr=e; }
  printf("realistic, 300 sets        : %6.3f LSB = %.6f deg\n",wr,wr*LSB);
  /* adversarial hill-climb, all amps at layout limit, same method as the review's hunt.c */
  double gw=0;
  for(int seed=1;seed<=8;seed++){ srand(seed*7919); ker_cal_t b; b.n=6;
    for(int k=0;k<6;k++){b.amp[k]=-32768;b.phase[k]=rand()&0xFFFF;}
    double bw=maxerr(&b);
    for(int it=0;it<4000;it++){ ker_cal_t t=b; int k=rand()%6, m=rand()%3;
      if(m==0){int a=t.amp[k]+((rand()&1)?1:-1)*(1+rand()%500); if(a>32767)a=32767; if(a<-32768)a=-32768; t.amp[k]=(int16_t)a;}
      else t.phase[k]=(uint16_t)(t.phase[k]+((rand()&1)?1:-1)*(1+rand()%(m==1?3000:40)));
      double e=maxerr(&t); if(e>=bw){bw=e;b=t;} }
    printf("  seed %d -> %6.3f LSB = %.6f deg\n",seed,bw,bw*LSB); if(bw>gw)gw=bw; }
  printf("hill-climb search best (N=6): %6.3f LSB = %.6f deg  -- a search result, NOT the worst case;\n"
         "  the constructed worst case is in accuracy_constructed_worst.txt (spec 7.5)\n",gw,gw*LSB);
  return 0;
}
