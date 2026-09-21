import numpy as np
rng = np.random.default_rng(20260919)
tt  = np.linspace(0,360,200001,endpoint=False); ttr = np.deg2rad(tt)

def fit_md(tt,tm,nh,remove_mean=True,dc=False):
    tmr=np.deg2rad(tm); y=(tt-tm+180)%360-180
    cols=([np.ones_like(tmr)] if dc else [])
    for k in range(1,nh+1): cols+=[np.sin(k*tmr),np.cos(k*tmr)]
    M=np.vstack(cols).T
    coef,*_=np.linalg.lstsq(M,y,rcond=None)
    r=(tm+M@coef-tt+180)%360-180
    if remove_mean: r=r-np.mean(r)
    return np.abs(r).max(),coef

def approachA(tt,tm,A,ph,nh_true):
    tmr=np.deg2rad(tm)
    corr=-sum(A[k]*np.sin((k+1)*tmr+ph[k]) for k in range(nh_true))
    e=(tm+corr-tt+180)%360-180
    return np.abs(e).max()

def mk(A,phi_deg):
    A=np.array(A,float); ph=np.deg2rad(phi_deg)
    e=sum(A[k]*np.sin((k+1)*ttr+ph[k]) for k in range(len(A)))
    return e, tt+e, A, ph

print("### B1. improvement factor A/B over 300 RANDOM phase sets & amplitude ratios (3 intrinsic harmonics)")
ratios=[]
for _ in range(300):
    a1=rng.uniform(0.2,2.5)
    A=[a1, a1*rng.uniform(0.05,1.2), a1*rng.uniform(0.02,0.9)]
    phi=rng.uniform(0,360,3)
    e,tm,A,ph=mk(A,phi)
    a=approachA(tt,tm,A,ph,3); b,_=fit_md(tt,tm,3)
    ratios.append(a/b)
r=np.array(ratios)
print(f"   A/B factor: min {r.min():.2f}  p5 {np.percentile(r,5):.2f}  median {np.median(r):.2f}  p95 {np.percentile(r,95):.2f}  max {r.max():.2f}")
print(f"   fraction inside the spec's quoted 2.4-2.7x band: {np.mean((r>=2.4)&(r<=2.7))*100:.1f}%")
print(f"   fraction where B is WORSE than A (ratio<1): {np.mean(r<1)*100:.1f}%")

print("\n### B2. is Approach A a strawman? compare to a proper true-domain fit + 1 Newton inversion step")
for A,phi,lab in [([1.0,0.5,0.2],[30,100,200],'typical'),([2.5,1.2,0.6],[10,70,300],'worst')]:
    e,tm,A,ph=mk(A,phi)
    a=approachA(tt,tm,A,ph,3); b,_=fit_md(tt,tm,3)
    # "A + one fixed-point inversion iteration" (what a competent station doing true-domain would do)
    tmr=np.deg2rad(tm)
    x=tm.copy()
    for _ in range(3):
        xr=np.deg2rad(x)
        x=tm-sum(A[k]*np.sin((k+1)*xr+ph[k]) for k in range(3))
    an=np.abs((x-tt+180)%360-180).max()
    print(f"   {lab:8s}: A(naive)={a:.4f}  A(3 fixed-point iters)={an:.6f}  B(measured-domain)={b:.4f}")

print("\n### C1. effect of nharm.py's post-hoc mean removal (firmware has NO DC term)")
hdr=f"{'case':<20}"+ "".join(f"{'H1-'+str(n):>22}" for n in (3,5))
print(hdr); print("   (max|resid| with mean removed / without)")
for lab,A,phi in [("typical",[1.0,.5,.2],[30,100,200]),("large",[1.5,.9,.3],[0,90,180]),
                  ("good",[.3,.15,.05],[45,135,250]),("worst",[2.5,1.2,.6],[10,70,300])]:
    e,tm,A,ph=mk(A,phi); row=f"{lab:<20}"
    for nh in (3,5):
        m1,_=fit_md(tt,tm,nh,remove_mean=True); m0,_=fit_md(tt,tm,nh,remove_mean=False)
        row+=f"{m1:11.5f} /{m0:9.5f}"
    print(row)

print("\n### C2. does the conclusion survive if the SENSOR itself has 4th/5th harmonics?")
print(f"{'intrinsic model':<34}{'raw':>8}{'H1-3':>10}{'H1-4':>10}{'H1-5':>10}{'H1-6':>10}{'H1-8':>10}")
mods=[("3 harmonics (nharm.py assumption)",[1.5,.9,.3],[0,90,180]),
      ("5 harmonics (1.5/.9/.3/.15/.08)",[1.5,.9,.3,.15,.08],[0,90,180,45,270]),
      ("6 harmonics (adds H6=0.05)",[1.5,.9,.3,.15,.08,.05],[0,90,180,45,270,120]),
      ("3H + H7=0.02 (mounting)",[1.5,.9,.3,0,0,0,.02],[0,90,180,0,0,0,60]),
      ("3H + H11=0.015",[1.5,.9,.3,0,0,0,0,0,0,0,.015],[0,90,180,0,0,0,0,0,0,0,200])]
for lab,A,phi in mods:
    e,tm,A,ph=mk(A,phi); row=f"{lab:<34}{np.abs(e).max():8.4f}"
    for nh in (3,4,5,6,8):
        m,_=fit_md(tt,tm,nh); row+=f"{m:10.5f}"
    print(row)
print("   floor = 0.0055 deg")

print("\n### C3. with 15-bit sensor quantisation actually applied (what the firmware really sees)")
for lab,A,phi in [("large 1.5/.9/.3",[1.5,.9,.3],[0,90,180]),("worst 2.5/1.2/.6",[2.5,1.2,.6],[10,70,300])]:
    e,tm,A,ph=mk(A,phi)
    tmq = np.floor(((tm%360)/360.0)*32768.0)/32768.0*360.0   # 15-bit sensor code
    row=f"   {lab:<18}"
    for nh in (3,5,6):
        m,_=fit_md(tt,tmq,nh); row+=f"  H1-{nh}={m:.5f}"
    print(row)
