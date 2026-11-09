"""Step 1: noise reduction on the raw voice track (spectral gating, noise profile from silent gaps)."""
import sys, numpy as np, soundfile as sf, noisereduce as nr
src, dst = sys.argv[1], sys.argv[2]
y, sr = sf.read(src, dtype="float32")
# Noise-only regions found with silencedetect: 12.9-14.3 s and 78.5-79.5 s
noise = np.concatenate([y[int(12.95*sr):int(14.30*sr)], y[int(78.50*sr):int(79.55*sr)]])
out = nr.reduce_noise(y=y, sr=sr, y_noise=noise, stationary=True,
                      prop_decrease=0.85, n_std_thresh_stationary=1.5,
                      freq_mask_smooth_hz=400, time_mask_smooth_ms=60)
sf.write(dst, out, sr, subtype="PCM_24")
print("noise rms before/after:", float(np.sqrt((noise**2).mean())),
      float(np.sqrt((out[int(12.95*sr):int(14.3*sr)]**2).mean())))
