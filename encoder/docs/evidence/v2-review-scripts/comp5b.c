#include <stdint.h>
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#define ANG_BITS 21
#define ANG_FULL (1UL<<ANG_BITS)
#define ANG_MASK (ANG_FULL-1UL)
static int16_t sinq[66];
static int v_min=32767, v_max=-32768;
static void build(void){for(int i=0;i<=64;i++)sinq[i]=(int16_t)lround(sin((double)i/64.0*M_PI/2.0)*32767.0);sinq[65]=0x7777;}
static int16_t sin_q15(uint16_t a){
    uint8_t quad=a>>14; uint16_t x=a&0x3FFF; if(quad&1)x=0x4000-x;
    uint8_t idx=x>>8, frac=x&0xFF;
    int16_t a0=sinq[idx],a1=sinq[idx+1];
    int32_t vv=(int32_t)a0+(int32_t)(int16_t)(((int32_t)(a1-a0)*frac)>>8);
    if(vv<v_min)v_min=vv; if(vv>v_max)v_max=vv;
    int16_t v=(int16_t)vv;
    return (quad&2)?(int16_t)(-v):v;
}
typedef struct{int16_t amp[5];uint16_t phase[5];int n;}cal_t;
static uint32_t cf(uint32_t u,const cal_t*c){int32_t d=0;
    for(uint8_t k=1;k<=c->n;k++){uint32_t arg=((uint32_t)k*u)&ANG_MASK;
        uint16_t a16=(uint16_t)((arg>>(ANG_BITS-16))+c->phase[k-1]);
        d+=((int32_t)c->amp[k-1]*sin_q15(a16))>>15;}
    return (uint32_t)(((int32_t)u-d)&(int32_t)ANG_MASK);}
static double cd(uint32_t u,const cal_t*c){double th=(double)u/(double)ANG_FULL*2*M_PI,d=0;
    for(int k=1;k<=c->n;k++){double ph=(double)c->phase[k-1]/65536.0*2*M_PI;
        d+=(double)c->amp[k-1]*sin(k*th+ph);}
    double r=fmod((double)u-d,(double)ANG_FULL); if(r<0)r+=ANG_FULL; return r;}
static double sgn_err(uint32_t u,const cal_t*c){
    double e=(double)cf(u,c)-cd(u,c);
    const double F=2097152.0; if(e> F/2.0) e-=F; if(e< -F/2.0) e+=F; return e;}
static double sweep(const cal_t*c,double*mean){double w=0,s=0;
    for(uint32_t i=0;i<32768;i++){uint32_t u=(i<<6)|(i>>9);double e=sgn_err(u,c);s+=e;if(fabs(e)>w)w=fabs(e);}
    if(mean)*mean=s/32768.0; return w;}
int main(void){
    build(); double L=360.0/ANG_FULL;
    printf("=== 6' wrap-aware SIGNED error statistics ===\n");
    cal_t cases[4]={
      {{ 8738,5243,1748,0,0},{0,16384,32768,0,0},3},
      {{ 8738,5243,1748,874,437},{0,16384,32768,49152,8000},5},
      {{32767,32767,32767,32767,32767},{0,13107,26214,39321,52428},5},
      {{-32768,-32768,-32768,-32768,-32768},{16384,16384,16384,16384,16384},5}};
    const char*nm[4]={"3H 1.5/0.9/0.3","5H geometric","5H all +max","5H all INT16_MIN"};
    for(int i=0;i<4;i++){double m;double w=sweep(&cases[i],&m);
      printf("  %-18s max|e|=%7.3f LSB (%.6f deg)  mean(e)=%+7.3f LSB (%+.6f deg)\n",
        nm[i],w,w*L,m,m*L);}
    printf("  sin_q15 pre-negation value range observed: [%d .. %d]  (int16 safe: %s)\n",
        v_min,v_max,(v_min>=-32768&&v_max<=32767)?"yes":"NO");

    printf("\n=== 7. directed hill-climb for the WORST legal 5-harmonic USERROW ===\n");
    srand(7); cal_t best={{-32768,-32768,-32768,-32768,-32768},{0,0,0,0,0},5};
    double bw=sweep(&best,NULL);
    for(int it=0;it<6000;it++){
        cal_t t=best; int k=rand()%5;
        if(rand()&1){ int step=(rand()%2)?1:-1; int a=t.amp[k]+step*(1+rand()%2000);
                      if(a>32767)a=32767; if(a<-32768)a=-32768; t.amp[k]=(int16_t)a; }
        else { t.phase[k]=(uint16_t)(t.phase[k]+((rand()%2)?1:-1)*(1+rand()%4000)); }
        double w=sweep(&t,NULL);
        if(w>bw){bw=w;best=t;}
    }
    printf("  best found: %.3f LSB = %.6f deg  vs budget 0.005 -> %s (margin %.2fx)\n",
        bw,bw*L,bw*L<=0.005?"PASS":"**FAIL**",0.005/(bw*L));
    printf("  amps:"); for(int k=0;k<5;k++)printf(" %d(%.2fdeg)",best.amp[k],best.amp[k]*L);
    printf("\n  phases:"); for(int k=0;k<5;k++)printf(" %u",best.phase[k]); printf("\n");

    printf("\n=== 8. per-harmonic error contribution (isolate the arg>>5 truncation) ===\n");
    for(int k=1;k<=5;k++){
        cal_t c={{0,0,0,0,0},{0,0,0,0,0},5}; c.amp[k-1]=32767;
        double w=sweep(&c,NULL);
        printf("  H%d alone, amp=32767 (5.63deg): max err %6.3f LSB = %.6f deg\n",k,w,w*L);
    }
    return 0;}
