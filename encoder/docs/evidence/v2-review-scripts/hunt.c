#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#define ANG_MASK 0x1FFFFFUL
static const double F=2097152.0;
static int16_t sinq[66];
static void build(void){for(int i=0;i<=64;i++)sinq[i]=(int16_t)lround(sin((double)i/64.0*M_PI/2.0)*32767.0);sinq[65]=0;}
static int16_t sin_q15(uint16_t a){uint8_t q=a>>14;uint16_t x=a&0x3FFF;if(q&1)x=0x4000-x;
 uint8_t i=x>>8,f=x&0xFF;int16_t a0=sinq[i],a1=sinq[i+1];
 int16_t v=(int16_t)(a0+(int16_t)(((int32_t)(a1-a0)*f)>>8));return (q&2)?(int16_t)(-v):v;}
typedef struct{int16_t amp[5];uint16_t phase[5];}cal_t;
static uint32_t cf(uint32_t u,const cal_t*c){int32_t d=0;
 for(uint8_t k=1;k<=5;k++){uint32_t arg=((uint32_t)k*u)&ANG_MASK;
  uint16_t a=(uint16_t)((arg>>5)+c->phase[k-1]); d+=((int32_t)c->amp[k-1]*sin_q15(a))>>15;}
 return (uint32_t)(((int32_t)u-d)&(int32_t)ANG_MASK);}
static double cd(uint32_t u,const cal_t*c){double th=(double)u/F*2*M_PI,d=0;
 for(int k=1;k<=5;k++){d+=(double)c->amp[k-1]*sin(k*th+(double)c->phase[k-1]/65536.0*2*M_PI);}
 double r=fmod((double)u-d,F); if(r<0)r+=F; return r;}
static double sweep(const cal_t*c){double w=0;
 for(uint32_t i=0;i<32768;i++){uint32_t u=(i<<6)|(i>>9);double e=(double)cf(u,c)-cd(u,c);
  if(e>F/2)e-=F; if(e<-F/2)e+=F; e=fabs(e); if(e>w)w=e;} return w;}
int main(int c_,char**v_){
 build(); double L=360.0/F; double gbw=0; cal_t gb;
 for(int seed=1;seed<=8;seed++){
  srand(seed*7919);
  cal_t b; for(int k=0;k<5;k++){b.amp[k]=-32768;b.phase[k]=rand()%65536;}
  double bw=sweep(&b);
  for(int it=0;it<20000;it++){cal_t t=b;int k=rand()%5;int mode=rand()%3;
   if(mode==0){int a=t.amp[k]+((rand()%2)?1:-1)*(1+rand()%500);
     if(a>32767)a=32767;if(a<-32768)a=-32768;t.amp[k]=(int16_t)a;}
   else if(mode==1){t.phase[k]=(uint16_t)(t.phase[k]+((rand()%2)?1:-1)*(1+rand()%3000));}
   else {t.phase[k]=(uint16_t)(t.phase[k]+((rand()%2)?1:-1)*(1+rand()%40));}
   double w=sweep(&t); if(w>=bw){bw=w;b=t;}}
  if(bw>gbw){gbw=bw;gb=b;}
  printf("  seed %d -> %.3f LSB = %.6f deg\n",seed,bw,bw*L);
 }
 printf("\nGLOBAL WORST over 8 restarts x 20000 steps: %.3f LSB = %.6f deg  (budget 0.005) -> %s\n",
   gbw,gbw*L,gbw*L<=0.005?"still under":"**OVER BUDGET**");
 printf("  amps:"); for(int k=0;k<5;k++)printf(" %d",gb.amp[k]);
 printf("\n  phases:"); for(int k=0;k<5;k++)printf(" %u",gb.phase[k]); printf("\n");
 printf("  margin vs 0.005 budget: %.2fx  (spec claims 3.4x)\n",0.005/(gbw*L));
 return 0;}
