"""Step 2: synthesise a soft traditional-style instrumental BGM and transition SFX.
BGM: plucked-string melody (Karplus-Strong, gambus/kecapi-like) on a D pentatonic scale,
a soft D/A drone, and a gentle frame-drum (rebana-like) 'dum..tak' pattern at 76 BPM.
SFX: a soft airy whoosh with a light bell tail."""
import sys, numpy as np, soundfile as sf
SR = 48000
rng = np.random.default_rng(7)
dur = float(sys.argv[1]); out_bgm = sys.argv[2]; out_sfx = sys.argv[3]
N = int(dur*SR)

def pluck(freq, length=2.2, bright=0.5):
    n = int(length*SR); p = int(SR/freq)
    buf = rng.uniform(-1, 1, p)
    # soften the excitation for a warmer, nylon/gut-like attack
    for _ in range(2): buf = 0.5*(buf + np.roll(buf, 1))
    out = np.empty(n); idx = 0; decay = 0.996
    for i in range(n):
        v = buf[idx]; nxt = buf[(idx+1) % p]
        buf[idx] = decay*(bright*v + (1-bright)*0.5*(v+nxt))
        out[i] = v; idx = (idx+1) % p
    env = np.minimum(1, np.arange(n)/(0.004*SR))
    return out*env

def drum(kind):
    t = np.arange(int(0.6*SR))/SR
    if kind == "dum":
        f = 95*np.exp(-t*6)+60
        return 0.9*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*7)
    n = rng.normal(0, 1, t.size)
    n = np.convolve(n, np.ones(6)/6, "same")
    return 0.35*(n*np.exp(-t*35) + 0.6*np.sin(2*np.pi*420*t)*np.exp(-t*30))

bgm = np.zeros(N+SR*3)
# drone: D2 + A2 soft sine pad with slow breathing
t = np.arange(bgm.size)/SR
drone = (np.sin(2*np.pi*73.42*t) + 0.6*np.sin(2*np.pi*110*t) + 0.25*np.sin(2*np.pi*146.83*t))
drone *= 0.06*(0.8+0.2*np.sin(2*np.pi*t/9))
bgm += drone
# melody, D major pentatonic-ish with a lowered 7th colour (asli feel)
notes = {"D4":293.66,"E4":329.63,"F#4":369.99,"A4":440.0,"B4":493.88,"C5":523.25,"D5":587.33,"A3":220.0}
phrase = ["A4","B4","A4","F#4","E4","D4","E4","F#4", "A4","D5","B4","A4","F#4","E4","D4","-",
          "F#4","A4","B4","C5","B4","A4","F#4","E4", "D4","E4","F#4","E4","D4","A3","D4","-"]
beat = 60/76
pos = 1.0; k = 0
while pos < dur:
    nm = phrase[k % len(phrase)]
    if nm != "-":
        s = pluck(notes[nm], 2.4, 0.45)*0.32
        i = int(pos*SR); bgm[i:i+s.size] += s[:max(0, bgm.size-i)]
    pos += beat; k += 1
# frame drum: asli-style pattern per 2 beats: dum . tak tak
pos = 1.0; b = 0
while pos < dur:
    pat = [("dum",0),("tak",1),("tak",1.5)] if b % 2 == 0 else [("dum",0),("tak",1)]
    for kind, off in pat:
        s = drum(kind)*0.5; i = int((pos+off*beat)*SR)
        if i+s.size < bgm.size: bgm[i:i+s.size] += s
    pos += 2*beat; b += 1
bgm = bgm[:N]
# gentle fades
fi, fo = int(2*SR), int(3*SR)
bgm[:fi] *= np.linspace(0, 1, fi); bgm[-fo:] *= np.linspace(1, 0, fo)
# simple stereo widening via tiny delay
stereo = np.stack([bgm, np.concatenate([np.zeros(240), bgm[:-240]])], 1)
stereo /= np.abs(stereo).max()*1.1
sf.write(out_bgm, stereo.astype(np.float32), SR, subtype="PCM_24")

# SFX: 0.7 s airy whoosh (band-swept noise) + soft bell
n = int(0.9*SR); tt = np.arange(n)/SR
noise = rng.normal(0, 1, n)
spec = np.fft.rfft(noise); fr = np.fft.rfftfreq(n, 1/SR)
spec *= np.exp(-((np.log(fr+1)-np.log(2500))**2)/0.8)
wh = np.fft.irfft(spec, n)
wh *= np.sin(np.pi*np.clip(tt/0.55, 0, 1))**2
bell = (np.sin(2*np.pi*1318.5*tt)+0.4*np.sin(2*np.pi*2637*tt))*np.exp(-tt*6)*np.clip((tt-0.25)/0.01, 0, 1)
sfx = wh/np.abs(wh).max()*0.8 + 0.18*bell
sfx /= np.abs(sfx).max()*1.05
sf.write(out_sfx, np.stack([sfx, sfx], 1).astype(np.float32), SR, subtype="PCM_24")
print("ok", N/SR)
