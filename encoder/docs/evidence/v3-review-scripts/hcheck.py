import numpy as np
exec(open("harmonics_v3.py").read().split('H1 = {')[0])   # reuse sensor/wrap/fit defs, no printing
def fit_m(tm, nh, const=False, demean=False):
    r = np.deg2rad(tm); cols=[f(k*r) for k in range(1,nh+1) for f in (np.sin,np.cos)]
    if const: cols.append(np.ones_like(r))
    M=np.column_stack(cols); c,*_=np.linalg.lstsq(M, wrap(tt-tm), rcond=None)
    res=wrap(tm+M@c-tt)
    if demean: res=res-res.mean()
    return np.abs(res).max()
rel=[1,.5,.2,.02,.01,.005]
rng=np.random.default_rng(99)
rows=[]
for d in range(60):
    ph=rng.uniform(0,2*np.pi,6); tm=sensor([1.0*r for r in rel],ph)
    qc=np.floor(tm/Q)*Q+Q/2; qf=np.floor(tm/Q)*Q
    rows.append([fit_m(qc,6), fit_m(qf,6), fit_m(qf,6,demean=True), fit_m(qf,6,const=True), fit_m(qc,5), fit_m(qc,6)])
a=np.array(rows)
print("typical, small H4-6, 60 fresh draws, H1-6 unless noted (deg)")
print(" bin centre as in script            : worst %.5f  median %.5f" % (a[:,0].max(), np.median(a[:,0])))
print(" bin floor (firmware), no demean    : worst %.5f" % a[:,1].max())
print(" bin floor, residual mean removed   : worst %.5f" % a[:,2].max())
print(" bin floor, const column in fit     : worst %.5f" % a[:,3].max())
w20=[a[i:i+20,0].max() for i in (0,20,40)]; print(" worst-of-20 over three disjoint batches:", " ".join("%.5f"%x for x in w20))
print(" paired H1-6 < H1-5 in %d/60 draws" % (a[:,5]<a[:,4]).sum())
