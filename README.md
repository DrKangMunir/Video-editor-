# Suntingan video pantun: "Cintailah Bahasa Kebangsaan"

Skrip pasca-produksi (ffmpeg + Python) yang digunakan untuk menyunting rakaman pantun.
Fail video tidak disimpan dalam repo (privasi); hanya skrip dan subtitle.

| Langkah | Skrip | Apa yang dibuat |
|---|---|---|
| 1 | `scripts/01_audio_clean.py` | Pengurangan hingar (spectral gating, profil hingar dari jeda senyap) |
| 2 | `scripts/02_make_bgm_sfx.py` | BGM instrumental sintetik (petikan pentatonik + dron + rebana lembut) dan SFX whoosh |
| 3 | `scripts/03_make_subs.py` | Subtitle ASS/SRT; pantun baris 1-2 kemudian 3-4 |
| 4 | `scripts/04_render.sh` | EQ suara, jeda pembayang→maksud (+1.2 s), ducking BGM, -14 LUFS, gred warna hangat, burn-in subtitle |

Keperluan: `ffmpeg`, Python 3 dengan `numpy`, `soundfile`, `noisereduce`, fon Inter.

## Video 2: "Cintai Bahasa Kebangsaan" (gabungan 4 klip)

`scripts/p2_render.py` menggabungkan WA0023 → WA0025 → WA0032 → WA0031 dalam satu langkah:
pembersihan audio dan penyelarasan kelantangan setiap klip, pemendekan senyap >1.2 s kepada 0.7 s,
jeda pembayang→maksud ~1.7 s, crossfade 0.3 s antara klip (di atas bingkai beku, tidak menyentuh suara),
gred hangat, subtitle `subtitles/pantun2.ass`/`.srt`, BGM sintetik dengan ducking dan SFX.
