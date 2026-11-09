"""Project 2: merge 4 clips (WA0023, WA0025, WA0032, WA0031), clean audio, shorten long
silences, extend the pembayang->maksud pause, warm grade, pantun subtitles, BGM + SFX.
Usage: p2_render.py <workdir with c1..c4.mp4> <repo subtitles dir> <out.mp4>"""
import sys, os, json, subprocess, re
import numpy as np, soundfile as sf, noisereduce as nr
W, SUBDIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS, SR = 30, 48000
XF_CLIP, XF_TRIM, XF_CUT = 0.30, 0.20, 1/30
def run(cmd): subprocess.run(cmd, shell=True, check=True)
def dur(f): return float(subprocess.check_output(f"ffprobe -v error -show_entries format=duration -of csv=p=0 {f}", shell=True))

# ---------- per-clip config (times in original clip seconds) ----------
CLIPS = {
 "c1": dict(noise=[(8.40, 9.25), (20.83, 21.93)], silences=[]),
 "c2": dict(noise=[(15.34, 16.45), (30.61, 32.03)], silences=[(30.60, 32.04)], hold=(15.75, 0.60)),
 "c3": dict(noise=[(29.27, 31.67), (42.67, 44.63), (55.31, 57.96)],
            silences=[(29.26, 31.68), (42.66, 45.38), (55.30, 57.97), (61.23, 62.63)]),
 "c4": dict(noise=[(1.60, 2.88)], silences=[], end=2.60),
}
KEEP = 0.70   # a long silence is shortened to this length (cut in its middle)

# ---------- 1. audio clean + clarity + per-clip loudness match ----------
CHAIN = ("highpass=f=90,lowpass=f=14000,equalizer=f=320:t=q:w=1.1:g=-3,"
         "equalizer=f=3200:t=q:w=1.4:g=3.5,equalizer=f=8000:t=q:w=1:g=1,deesser=i=0.35,"
         "acompressor=threshold=-26dB:ratio=3:attack=8:release=160:makeup=2")
for c, cfg in CLIPS.items():
    run(f"ffmpeg -v error -y -i {W}/{c}.mp4 -vn -ac 1 -ar {SR} {W}/{c}_raw.wav")
    y, _ = sf.read(f"{W}/{c}_raw.wav", dtype="float32")
    noise = np.concatenate([y[int(a*SR):int(b*SR)] for a, b in cfg["noise"]])
    y = nr.reduce_noise(y=y, sr=SR, y_noise=noise, stationary=True, prop_decrease=0.85,
                        n_std_thresh_stationary=1.5, freq_mask_smooth_hz=400, time_mask_smooth_ms=60)
    sf.write(f"{W}/{c}_nr.wav", y, SR, subtype="PCM_24")
    run(f"ffmpeg -v error -y -i {W}/{c}_nr.wav -af '{CHAIN}' -c:a pcm_s24le {W}/{c}_eq.wav")
    log = subprocess.run(f"ffmpeg -hide_banner -i {W}/{c}_eq.wav -af ebur128 -f null -", shell=True,
                         capture_output=True, text=True).stderr
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])
    g = -20.0 - I
    run(f"ffmpeg -v error -y -i {W}/{c}_eq.wav -af 'volume={g:.2f}dB' -c:a pcm_s24le {W}/{c}_voice.wav")
    print(f"{c}: integrated {I:.1f} LUFS -> gain {g:+.1f} dB")

# ---------- 2. piece list: (clip, src_start, src_end, kind) + join type before each ----------
pieces = []   # dicts: clip, a, b, hold(bool), join(duration of transition from previous)
for idx, (c, cfg) in enumerate(CLIPS.items()):
    D = cfg.get("end") or dur(f"{W}/{c}.mp4") - 0.05
    cuts, t = [], 0.0
    for s, e in cfg["silences"]:
        mid = (s + e) / 2; rm = (e - s) - KEEP
        cuts.append((t, mid - rm/2)); t = mid + rm/2
    cuts.append((t, D))
    for k, (a, b) in enumerate(cuts):
        join = XF_CLIP if (k == 0 and idx > 0) else (XF_TRIM if k > 0 else 0)
        if "hold" in cfg and a < cfg["hold"][0] < b:
            h, hd = cfg["hold"]
            pieces += [dict(clip=c, a=a, b=h, join=join),
                       dict(clip=c, a=h, b=h, hold=hd, join=XF_CUT),
                       dict(clip=c, a=h, b=b, join=XF_CUT)]
        else:
            pieces.append(dict(clip=c, a=a, b=b, join=join))
# Clip-to-clip crossfades run over frozen padding (first/last frame + silence), never over speech
clips_order = list(CLIPS)
for i, p in enumerate(pieces):
    p["pre"] = XF_CLIP if (i > 0 and p["join"] == XF_CLIP) else 0.0
    nxt = pieces[i+1] if i + 1 < len(pieces) else None
    p["post"] = XF_CLIP if (nxt and nxt["join"] == XF_CLIP) else 0.0
    p["len"] = (p.get("hold") or (p["b"] - p["a"])) + p["pre"] + p["post"]

# output timeline
t = 0.0
for i, p in enumerate(pieces):
    p["out"] = t - p["join"] if i else 0.0
    t = p["out"] + p["len"]
TOTAL = t
def to_out(clip, ts):
    for p in pieces:
        if p["clip"] == clip and not p.get("hold") and p["a"] - 1e-6 <= ts <= p["b"] + 1e-6:
            return p["out"] + p["pre"] + (ts - p["a"])
    # inside a removed silence -> snap to nearest piece boundary
    best = min((p for p in pieces if p["clip"] == clip and not p.get("hold")),
               key=lambda p: min(abs(ts - p["a"]), abs(ts - p["b"])))
    return best["out"] + (best["pre"] if abs(ts-best["a"]) < abs(ts-best["b"]) else best["len"] - best["post"])
json.dump(pieces, open(f"{W}/pieces.json", "w"), indent=1)
print(f"pieces={len(pieces)} total={TOTAL:.2f}s")

# ---------- 3. filter graph: per-piece video/audio, xfade/acrossfade chain ----------
inputs = " ".join(f"-i {W}/{c}.mp4" for c in CLIPS) + " " + " ".join(f"-i {W}/{c}_voice.wav" for c in CLIPS)
ci = {c: i for i, c in enumerate(CLIPS)}
fg = []
for i, p in enumerate(pieces):
    vi, ai = ci[p["clip"]], ci[p["clip"]] + len(CLIPS)
    if p.get("hold"):
        n = round(p["hold"]*FPS)
        fg.append(f"[{vi}:v]fps={FPS},setsar=1,trim=start={p['a']:.3f},setpts=PTS-STARTPTS,trim=end_frame=1,"
                  f"loop=loop={n-1}:size=1:start=0,setpts=N/{FPS}/TB,scale=1440:2560,"
                  f"zoompan=z='1+0.03*sin(PI*on/{n})':x='iw/2-iw/zoom/2':y='ih*0.28-ih/zoom*0.28':d=1:s=720x1280:fps={FPS},"
                  f"format=yuv420p[v{i}]")
        fg.append(f"anullsrc=r={SR}:cl=mono,atrim=0:{p['hold']:.3f}[a{i}]")
    else:
        fg.append(f"[{vi}:v]fps={FPS},setsar=1,trim={p['a']:.3f}:{p['b']:.3f},setpts=PTS-STARTPTS,"
                  f"tpad=start_mode=clone:start_duration={p['pre']}:stop_mode=clone:stop_duration={p['post']},format=yuv420p[v{i}]")
        fg.append(f"[{ai}:a]atrim={p['a']:.3f}:{p['b']:.3f},asetpts=PTS-STARTPTS,"
                  f"adelay={int(p['pre']*1000)}:all=1,apad=pad_dur={p['post']}[a{i}]")
pv, pa = "v0", "a0"
for i in range(1, len(pieces)):
    p = pieces[i]; d = p["join"]
    fg.append(f"[{pv}][v{i}]xfade=transition=fade:duration={d:.4f}:offset={p['out']:.4f}[vx{i}]")
    fg.append(f"[{pa}][a{i}]acrossfade=d={d:.4f}:c1=tri:c2=tri[ax{i}]")
    pv, pa = f"vx{i}", f"ax{i}"
fg.append(f"[{pa}]aformat=channel_layouts=stereo[aout]")
open(f"{W}/assemble.txt", "w").write(";\n".join(fg))
run(f"ffmpeg -v error -y {inputs} -filter_complex_script {W}/assemble.txt -map '[{pv}]' -map '[aout]' "
    f"-c:v libx264 -preset fast -crf 14 -c:a pcm_s24le {W}/assembled.mkv")

# ---------- 4. subtitles (exact text supplied by the user; name line intentionally not captioned) ----------
G, R = r"{\c&H5FC8F5&}", r"{\r}"
subs = [
 ("c1", 0.00, 3.15, "Body", r"Assalamualaikum\Nwarahmatullahi wabarakatuh"),
 ("c1", 8.45, 13.90, "Body", r"Saya akan membaca pantun"),
 ("c1", 13.90, 26.20, "Body", r"bertajuk\N" + G + "Cintai Bahasa Kebangsaan" + R),
 ("c2", 0.00, None, "Pantun", r"Pergi ke taman memetik selasih,\NSelasih dipetik di tepi perigi,"),
 ("c2", "maksud", 35.80, "Pantun", r"Bahasa kebangsaan warisan kasih,\NGunakan selalu sepenuh hati."),
 ("c3", 0.00, 6.40, "Body", G + "Pengajaran" + R),
 ("c3", 6.40, 27.40, "Body", r"Kita hendaklah menggunakan\Nbahasa kebangsaan"),
 ("c3", 27.40, 42.60, "Body", r"dengan bangga dan\Npenuh rasa cinta"),
 ("c3", 42.60, 63.80, "Body", r"supaya bahasa Melayu\Nterus terpelihara"),
 ("c3", 63.80, 80.60, "Body", r"dan dihormati oleh\Ngenerasi akan datang."),
 ("c4", 0.00, 2.60, "Body", r"Sekian, terima kasih."),
]
hold = next(p for p in pieces if p.get("hold"))
swap = hold["out"] + hold["len"] - 0.35          # maksud appears just before line 3 is spoken
events = []
for c, a, b, st, tx in subs:
    if a == "maksud": oa = swap
    else: oa = to_out(c, a)
    ob = swap if b is None else to_out(c, b)
    events.append((oa, ob, st, tx))
# no overlaps; tiny gap between consecutive captions
events.sort()
for i in range(len(events) - 1):
    if events[i][1] > events[i+1][0]: events[i] = (events[i][0], events[i+1][0], *events[i][2:])
def ts(t): return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"
def srt(t): ms = int(round(t*1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
hdr = open(f"{SUBDIR}/pantun.ass").read().split("[Events]")[0]
with open(f"{SUBDIR}/pantun2.ass", "w") as f:
    f.write(hdr + "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    for a, b, st, tx in events:
        f.write(f"Dialogue: 0,{ts(a)},{ts(b)},{st},,0,0,0,,{{\\fad(180,180)}}{tx}\n")
with open(f"{SUBDIR}/pantun2.srt", "w") as f:
    for i, (a, b, st, tx) in enumerate(events, 1):
        plain = re.sub(r"\{[^}]*\}", "", tx).replace(r"\N", "\n")
        f.write(f"{i}\n{srt(a)} --> {srt(b)}\n{plain}\n\n")
cues = [{"t": round(e[0], 3), "strong": e[2] == "Pantun"} for e in events[1:]]
# (clip joins coincide with caption changes, so they already get a whoosh)
for e in events: print(f"{e[0]:7.2f} {e[1]:7.2f} {e[3]}")

# ---------- 5. BGM + SFX, mix, loudness, grade, burn subtitles ----------
run(f"python3 {REPO}/scripts/02_make_bgm_sfx.py {TOTAL:.3f} {W}/bgm2.wav {W}/sfx2.wav")
sfx = ";".join(f"[2:a]volume={0.22 if q['strong'] else 0.12},adelay={max(0,int((q['t']-0.35)*1000))}|{max(0,int((q['t']-0.35)*1000))}[s{i}]"
               for i, q in enumerate(cues))
lab = "".join(f"[s{i}]" for i in range(len(cues)))
run(f"ffmpeg -v error -y -i {W}/assembled.mkv -i {W}/bgm2.wav -i {W}/sfx2.wav -filter_complex "
    f"\"[0:a]asplit[vo][key];[1:a]volume=0.09[bg];"
    f"[bg][key]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=600:makeup=1[bgd];"
    f"{sfx};{lab}amix=inputs={len(cues)}:normalize=0[sx];"
    f"[vo][bgd][sx]amix=inputs=3:normalize=0:duration=first[m]\" -map '[m]' -c:a pcm_s24le {W}/mix2.wav")
log = subprocess.run(f"ffmpeg -hide_banner -i {W}/mix2.wav -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null -",
                     shell=True, capture_output=True, text=True).stderr
d = json.loads(re.search(r"\{[^{}]*\}", log, re.S).group())
run(f"ffmpeg -v error -y -i {W}/mix2.wav -af \"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={d['input_i']}:"
    f"measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:"
    f"offset={d['target_offset']}:linear=true,aresample={SR}\" -c:a pcm_s24le {W}/mix2_norm.wav")
GRADE = ("curves=master='0/0 0.2/0.18 0.5/0.54 0.82/0.84 1/0.96',eq=contrast=1.06:saturation=1.12,"
         "colorbalance=rs=0.03:bs=-0.04:rm=0.05:gm=0.012:bm=-0.05:rh=0.025:bh=-0.035,vignette=angle=PI/7,unsharp=5:5:0.45")
run(f"ffmpeg -v error -y -i {W}/assembled.mkv -i {W}/mix2_norm.wav -filter_complex "
    f"\"[0:v]{GRADE},subtitles='{SUBDIR}/pantun2.ass',fade=t=in:d=0.4,fade=t=out:st={TOTAL-0.6:.2f}:d=0.6,format=yuv420p[v];"
    f"[1:a]afade=t=out:st={TOTAL-0.8:.2f}:d=0.8[a]\" -map '[v]' -map '[a]' -c:v libx264 -preset slow -crf 18 "
    f"-profile:v high -movflags +faststart -c:a aac -b:a 192k -shortest {OUT}")
print("done", OUT, f"{TOTAL:.2f}s")
