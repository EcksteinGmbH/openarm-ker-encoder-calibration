import re,sys
# AVRxt (megaAVR/attiny1616) cycle costs. Where an instruction is conditional,
# the worst case is used and noted.
C={'push':1,'pop':2,'mov':1,'movw':1,'ldi':1,'add':1,'adc':1,'sub':1,'sbc':1,'sbci':1,'subi':1,
   'and':1,'andi':1,'eor':1,'or':1,'ori':1,'neg':1,'com':1,'dec':1,'inc':1,'cp':1,'cpc':1,'cpi':1,
   'lsr':1,'lsl':1,'ror':1,'rol':1,'asr':1,'swap':1,'sbiw':2,'adiw':2,'mul':2,'muls':2,'mulsu':2,
   'ld':2,'ldd':2,'st':1,'std':1,'lds':3,'sts':2,'lpm':3,'elpm':3,
   'rjmp':2,'jmp':3,'rcall':2,'call':3,'ret':4,'reti':4,
   'brne':2,'breq':2,'brcs':2,'brcc':2,'brpl':2,'brmi':2,'brlt':2,'brge':2,'brsh':2,'brlo':2,
   'sbrs':3,'sbrc':3,'sbis':3,'sbic':3,'nop':1,'clr':1,'ser':1,'tst':1}
def parse(path,fn):
    out=[];started=False
    for line in open(path):
        if re.search(r'<%s>:'%re.escape(fn),line): started=True; continue
        if started:
            m=re.match(r'\s+([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*\t(\S+)',line)
            if m: out.append((int(m.group(1),16),m.group(3)))
            elif line.strip()=='' and out: break
    return out
ins=parse('ker_comp_avr.lst','ker_compensate')
def cost(ops): return sum(C.get(m,1) for _,m in ops)
def rng(a,b): return [(o,m) for o,m in ins if a<=o<b]
# helper costs, measured from libgcc disassembly above
HELP={'__umulhisi3':10+5+4,            # 5 mul(2) + 5 alu(1) + ret(4)
      '__muluhisi3':3+(10+5+4)+3*2+5+4, # call + umulhisi3 + 3 mul + 5 alu + ret
      '__mulhisi3' :3+(10+5+4)+3+3,     # call + umulhisi3 + sign fixup + jmp
      '__usmulhisi3':3+(10+5+4)+3+3}
print("== ker_compensate, avr-gcc 7.3.0 -O2 -mmcu=attiny1616, one harmonic iteration ==")
pre  = rng(0x42,0x56); print(f"  0x42-0x54 setup (k*u operand marshalling)     : {cost(pre):4d} cy")
c1   = 3+HELP['__muluhisi3']; print(f"  0x56 call __muluhisi3  (32x32 k*u)           : {c1:4d} cy")
mid1 = rng(0x5a,0x60); sh1 = 4*7+6
print(f"  0x5a-0x5e                                     : {cost(mid1):4d} cy")
print(f"  0x60-0x6a SOFTWARE >>5 loop (5 iters x 7 cy)  : {sh1:4d} cy   <-- (arg>>5)")
mid2 = rng(0x6c,0xbc); print(f"  0x6c-0xba sin_q15 inlined (2x lpm, quad, interp): {cost(mid2):4d} cy")
c2   = 3+HELP['__usmulhisi3']; print(f"  0xbc call __usmulhisi3 (interp (a1-a0)*frac)  : {c2:4d} cy")
mid3 = rng(0xc0,0xde); print(f"  0xc0-0xdc sign/mirror fixups                   : {cost(mid3):4d} cy")
c3   = 3+HELP['__mulhisi3']; print(f"  0xde call __mulhisi3   (16x16 amp*sin_q15)    : {c3:4d} cy")
sh2  = 14*7+6
print(f"  0xe2-0xee SOFTWARE >>15 loop (15 iters x 7 cy): {sh2:4d} cy   <-- ((amp*sin)>>15)")
tail = rng(0xf0,0x100); print(f"  0xf0-0xfe accumulate + loop tail               : {cost(tail):4d} cy")
per = cost(pre)+c1+cost(mid1)+sh1+cost(mid2)+c2+cost(mid3)+c3+sh2+cost(tail)
pro = cost(rng(0x0,0x42)) + cost(rng(0x100,0x136))
print(f"  ------------------------------------------------------")
print(f"  PER HARMONIC                                  : {per:4d} cy = {per/20.0:.2f} us @20MHz")
print(f"  prologue+epilogue (18 push/pop pairs)         : {pro:4d} cy = {pro/20.0:.2f} us")
for n in (3,5):
    t=per*n+pro
    print(f"  N_HARM={n}: {t:5d} cy = {t/20.0:6.2f} us   (spec 5.1 says 15 us for N_HARM=5)")
print()
print("  HARD LOWER BOUND using ONLY the two compiler-emitted shift loops and the")
print(f"  three libgcc multiply calls (no inline code counted at all):")
lb=sh1+sh2+c1+c2+c3
print(f"    {lb} cy/harmonic -> N_HARM=5: {lb*5} cy = {lb*5/20.0:.1f} us")
