"""Step 3: build ASS subtitles (pantun: lines 1-2 together, then lines 3-4) and SRT,
plus the list of SFX cue times. Times are word timestamps from Whisper alignment,
shifted by +PAUSE after the pembayang/maksud cut point."""
import sys, json
CUT, PAUSE = 36.86, 1.20
def sh(t): return t if t < CUT else t + PAUSE
G = r"{\c&H5FC8F5&}"   # warm gold (BGR) for the title
R = r"{\r}"
# (start, end, style, text) in ORIGINAL timeline
ev = [
 (0.25, 5.15, "Body", r"Assalamualaikum\Nwarahmatullahi wabarakatuh"),
 (14.00, 21.20, "Body", r"Hari ini saya akan membaca\Npantun empat kerat"),
 (21.20, 29.40, "Body", r"yang bertajuk\N" + G + "Cintailah Bahasa Kebangsaan" + R),
 (29.85, CUT + 1.05, "Pantun", r"Burung merpati terbang ke desa,\NHinggap sebentar di pohon jati,"),
 (CUT + 0.05, 44.90, "Pantun", r"Bahasa Melayu warisan bangsa,\NMarilah kita santuni dan cintai."),
 (46.55, 49.80, "Body", r"{\c&H5FC8F5&}Pengajaran" + R + " pantun ini ialah"),
 (49.80, 54.50, "Body", r"kita hendaklah mencintai,\Nmenghargai dan"),
 (54.50, 60.40, "Body", r"memartabatkan bahasa Melayu\Nsebagai bahasa kebangsaan"),
 (60.40, 64.45, "Body", r"kerana bahasa Melayu\Nmerupakan warisan bangsa"),
 (64.45, 67.85, "Body", r"dan lambang\Nidentiti negara."),
 (67.85, 70.75, "Body", r"Kita juga perlu\Nmenggunakannya"),
 (70.75, 74.50, "Body", r"dengan betul\Ndalam kehidupan seharian."),
 (74.50, 76.65, "Body", r"Itu sahaja daripada saya."),
 (76.65, 78.90, "Body", r"Sekian, terima kasih."),
]
def ts(t): h=int(t//3600); m=int(t%3600//60); s=t%60; return f"{h}:{m:02d}:{s:05.2f}"
def srt(t): ms=int(round(t*1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
hdr = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Body,Inter SemiBold,42,&H00FFFFFF,&H00FFFFFF,&H70141E2A,&H00000000,0,0,0,0,100,100,0,0,3,9,0,2,40,40,200,1
Style: Pantun,Inter SemiBold,40,&H00FFFFFF,&H00FFFFFF,&H70141E2A,&H00000000,0,0,0,0,100,100,0,0,3,9,0,2,24,24,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
lines, srts, cues = [], [], []
for i, (a, b, st, tx) in enumerate(ev, 1):
    a2, b2 = sh(a), sh(b) if b != CUT + 1.05 else CUT + 1.05
    if a == CUT + 0.05: a2 = CUT + 1.10   # maksud appears just before line 3 is spoken
    lines.append(f"Dialogue: 0,{ts(a2)},{ts(b2)},{st},,0,0,0,,{{\\fad(180,180)}}{tx}")
    plain = tx.replace(r"\N", "\n").replace(G, "").replace(R, "").replace(r"{\c&H5FC8F5&}", "")
    srts.append(f"{i}\n{srt(a2)} --> {srt(b2)}\n{plain}\n")
    cues.append({"t": round(a2, 3), "strong": st == "Pantun"})
open(sys.argv[1], "w").write(hdr + "\n".join(lines) + "\n")
open(sys.argv[2], "w").write("\n".join(srts))
json.dump(cues, open(sys.argv[3], "w"))
print("\n".join(lines))
