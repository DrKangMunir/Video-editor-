#!/usr/bin/env bash
# Step 4: audio chain + pause insertion + mix, then video grade + freeze-hold + subtitles.
# Usage: 04_render.sh <input.mp4> <voice_nr.wav> <bgm.wav> <sfx.wav> <cues.json> <subs.ass> <workdir> <out.mp4>
set -euo pipefail
IN=$1; VOICE=$2; BGM=$3; SFX=$4; CUES=$5; ASS=$6; W=$7; OUT=$8
CUT=36.86; PAUSE=1.20

# --- Voice: clarity EQ, de-esser, compression; insert the pembayang->maksud pause
ffmpeg -v error -y -i "$VOICE" -filter_complex "
 [0:a]highpass=f=90,lowpass=f=14000,
  equalizer=f=320:t=q:w=1.1:g=-3,
  equalizer=f=3200:t=q:w=1.4:g=3.5,
  equalizer=f=8000:t=q:w=1:g=1,
  deesser=i=0.35,
  acompressor=threshold=-24dB:ratio=3:attack=8:release=160:makeup=3,
  asplit[a][b];
 [a]atrim=0:$CUT,afade=t=out:st=$(echo "$CUT-0.03"|bc):d=0.03,asetpts=N/SR/TB[a1];
 anullsrc=r=48000:cl=mono,atrim=0:$PAUSE[sil];
 [b]atrim=start=$CUT,asetpts=N/SR/TB,afade=t=in:d=0.03[b1];
 [a1][sil][b1]concat=n=3:v=0:a=1,aformat=channel_layouts=stereo[v]" -map "[v]" -c:a pcm_s24le "$W/voice_final.wav"

# --- SFX track: one cue per subtitle change (whoosh peaks right at the swap)
SFXF=$(python3 -c "
import json; c=json.load(open('$CUES'))
parts=[]; labels=''
for i,x in enumerate(c[1:]):          # no whoosh for the very first caption
    d=max(0,int((x['t']-0.35)*1000)); v=0.22 if x['strong'] else 0.12
    parts.append(f'[2:a]volume={v},adelay={d}|{d}[s{i}]'); labels+=f'[s{i}]'
print(';'.join(parts)+';'+labels+f'amix=inputs={len(c)-1}:normalize=0[sfx]')")
ffmpeg -v error -y -i "$W/voice_final.wav" -i "$BGM" -i "$SFX" -filter_complex "
 [0:a]asplit[vo][key];
 [1:a]volume=0.09[bg];
 [bg][key]sidechaincompress=threshold=0.02:ratio=5:attack=30:release=600:makeup=1[bgd];
 $SFXF;
 [vo][bgd][sfx]amix=inputs=3:normalize=0:duration=first[mix]" -map "[mix]" -c:a pcm_s24le "$W/mix.wav"

# --- Two-pass loudness normalisation to -14 LUFS / -1.5 dBTP
read I TP LRA TH OFF < <(ffmpeg -hide_banner -i "$W/mix.wav" -af loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 \
  | python3 -c "import sys,json,re;d=json.loads(re.search(r'\{[^{}]*\}',sys.stdin.read(),re.S).group());print(d['input_i'],d['input_tp'],d['input_lra'],d['input_thresh'],d['target_offset'])")
ffmpeg -v error -y -i "$W/mix.wav" -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$I:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$TH:offset=$OFF:linear=true,aresample=48000" -c:a pcm_s24le "$W/mix_norm.wav"

# --- Video: CFR 30, freeze-hold with gentle breathing zoom during the pause, warm grade, subtitles
GRADE="curves=master='0/0 0.2/0.18 0.5/0.54 0.82/0.84 1/0.96',eq=contrast=1.06:saturation=1.12,colorbalance=rs=0.03:bs=-0.04:rm=0.05:gm=0.012:bm=-0.05:rh=0.025:bh=-0.035,vignette=angle=PI/7,unsharp=5:5:0.45"
NF=$(python3 -c "print(round($PAUSE*30))")
ffmpeg -v error -y -i "$IN" -i "$W/mix_norm.wav" -filter_complex "
 [0:v]fps=30,setsar=1,split=3[x][y][z];
 [x]trim=0:$CUT,setpts=PTS-STARTPTS[v1];
 [y]trim=start=$CUT,setpts=PTS-STARTPTS,trim=end_frame=1,loop=loop=$((NF-1)):size=1:start=0,setpts=N/30/TB,
    scale=1440:2560,zoompan=z='1+0.035*sin(PI*on/$NF)':x='iw/2-iw/zoom/2':y='ih*0.28-ih/zoom*0.28':d=1:s=720x1280:fps=30[v2];
 [z]trim=start=$CUT,setpts=PTS-STARTPTS[v3];
 [v1][v2][v3]concat=n=3:v=1:a=0,$GRADE,subtitles='$ASS',format=yuv420p[v]" \
 -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 18 -profile:v high -movflags +faststart \
 -c:a aac -b:a 192k -shortest "$OUT"
echo "done: $OUT"
