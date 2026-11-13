"""Score for the Omnixon film: 100 BPM, F minor. Pure numpy.

Soft and tonal on purpose: mallets, a vibraphone, warm pads and a round bass; a soft kick and a rim
instead of hats and claps; swells built from tones, not from noise; a dark reverb and a gentle top cut.
The arrangement follows the scene map; every sound effect comes from the cue sheet the film itself
exports (render.mjs events, out/events-<lang>.json), so landings, keys and calls hit on the exact frame.
Usage: python3 music.py [en|ru]. Writes out/music-<lang>.wav (48 kHz, 16-bit stereo).
"""
import json
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
SR = 48000
LANG = sys.argv[1] if len(sys.argv) > 1 else 'en'
FILM = json.loads((HERE / f'out/events-{LANG}.json').read_text())
DUR = float(FILM['dur'])
N = int(SR * DUR)
SEC = {s['name']: (s['a'], s['b']) for s in FILM['sections']}
BEAT = float(FILM['beat'])       # 100 BPM: a beat is 0.6 s
BAR = 4 * BEAT
SLAM = float(FILM['slam'])       # the logo slam: the end of the beat
rng = np.random.default_rng(7)

music = np.zeros((2, N))   # ducked by the kick
drums = np.zeros((2, N))
sfx = np.zeros((2, N))
send = np.zeros((2, N))    # into the reverb
KICKS = []


def hz(m):
    return 440.0 * 2 ** ((np.asarray(m, float) - 69) / 12)


def tt(n):
    return np.arange(n) / SR


def add(bus, t, sig, g=1.0, pan=0.0, rev=0.0):
    i = int(round(t * SR))
    if i >= N or len(sig) == 0:
        return
    if i < 0:
        sig = sig[-i:]
        i = 0
    sig = sig[: N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[0, i:i + len(sig)] += sig * g * l * 1.414
    bus[1, i:i + len(sig)] += sig * g * r * 1.414
    if rev:
        send[0, i:i + len(sig)] += sig * g * rev * l
        send[1, i:i + len(sig)] += sig * g * rev * r


def fft_filter(x, lo=0.0, hi=None, slope=1.0):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = np.ones_like(f)
    if lo:
        m *= 1 / (1 + (lo / np.maximum(f, 1)) ** (2 * slope))
    if hi:
        m *= 1 / (1 + (f / hi) ** (2 * slope))
    return np.fft.irfft(X * m, len(x))


def fade(sig, a=0.004, r=0.02):
    """Click-free edges."""
    n = len(sig)
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return sig * e


def glide(f0, f1, n, curve=1.0):
    """Phase of a sine gliding from f0 to f1 (Hz)."""
    k = np.linspace(0, 1, n) ** curve
    return 2 * np.pi * np.cumsum(f0 * (f1 / f0) ** k) / SR


# ------------------------------------------------------------------ instruments (all tonal)
def mallet(m, d=0.6, g=1.0, bright=1.0):
    """A soft marimba: the fundamental, a fast 4th partial and a touch of the 10th."""
    n = int(SR * d)
    t = tt(n)
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 5.5)
    s += 0.32 * bright * np.sin(2 * np.pi * f * 3.99 * t) * np.exp(-t * 28)
    s += 0.06 * bright * np.sin(2 * np.pi * f * 9.9 * t) * np.exp(-t * 70)
    return fade(s * g, 0.002, 0.03)


def vibe(m, d=1.8, g=1.0):
    """A vibraphone: a pure tone with a soft 4th partial and a slow tremolo."""
    n = int(SR * d)
    t = tt(n)
    f = hz(m)
    trem = 1 - 0.18 * (0.5 + 0.5 * np.sin(2 * np.pi * 5.2 * t))
    s = (np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 6)) * np.exp(-t * 2.2) * trem
    return fade(s * g, 0.003, 0.08)


def warm(f, n, harmonics=5, roll=2.0, detune=0.0):
    t = tt(n)
    out = np.zeros(n)
    for k in range(1, harmonics + 1):
        out += np.sin(2 * np.pi * f * k * (1 + detune) * t + rng.random() * 6.28) / k ** roll
    return out


def kick(g=1.0, long=False):
    n = int(SR * (0.8 if long else 0.42))
    t = tt(n)
    f = 46 + 70 * np.exp(-t * 26)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (3.5 if long else 8))
    s += 0.12 * np.sin(2 * np.pi * 1100 * t) * np.exp(-t * 300)   # a soft tonal click, no noise
    return fade(np.tanh(s * 1.2) * g, 0.001, 0.03)


def rim(g=1.0):
    """A soft rim/snare: two tones and a breath of dark noise."""
    n = int(SR * 0.22)
    t = tt(n)
    s = 0.6 * np.sin(2 * np.pi * 185 * t) * np.exp(-t * 28) + 0.35 * np.sin(2 * np.pi * 330 * t) * np.exp(-t * 40)
    s += 0.18 * fft_filter(rng.standard_normal(n), 400, 2400) * np.exp(-t * 35)
    return fade(s * g, 0.001, 0.03)


def thump(g=1.0):
    n = int(SR * 0.45)
    t = tt(n)
    s = np.sin(glide(80, 42, n, 0.4)) * np.exp(-t * 9)
    return fade(s * g, 0.002, 0.04)


def boom(g=1.0):
    n = int(SR * 2.0)
    t = tt(n)
    s = np.sin(glide(64, 30, n, 0.3)) * np.exp(-t * 2.2)
    s += 0.25 * np.sin(glide(128, 60, n, 0.3)) * np.exp(-t * 4)
    return fade(np.tanh(s * 1.3) * g, 0.002, 0.2)


def swell(d, hi=False, g=1.0):
    """A whoosh made of tones: four sines rising together, and only a whisper of dark air."""
    n = int(SR * d)
    k = np.linspace(0, 1, n)
    env = np.sin(np.pi * k) ** 2
    base = 220 if hi else 110
    s = sum(np.sin(glide(base * r, base * r * 2, n)) / (i + 1) for i, r in enumerate([1, 1.5, 2, 3]))
    air = fft_filter(rng.standard_normal(n), 120, 900) * 0.08
    return fade((s * 0.35 + air) * env * g, 0.01, 0.05)


def riser(d, hi=False, g=1.0):
    n = int(SR * d)
    k = np.linspace(0, 1, n)
    f0 = hz(53 + (12 if hi else 0))
    s = np.zeros(n)
    for h in range(1, 6):
        s += np.sin(glide(f0 * h, f0 * h * 2, n, 1.6)) / h ** 1.8
    return fade(s * k ** 2.2 * 0.5 * g, 0.01, 0.03)


def fall_glide(m, g=1.0):
    n = int(SR * 0.4)
    t = tt(n)
    s = np.sin(glide(hz(m), hz(m - 7), n, 0.7)) * np.exp(-t * 6)
    return fade(s * g, 0.003, 0.05)


def pop(m, g=1.0):
    n = int(SR * 0.12)
    t = tt(n)
    s = np.sin(glide(hz(m), hz(m) * 1.5, n, 0.5)) * np.exp(-t * 30)
    return fade(s * g, 0.001, 0.02)


def key(v, g=1.0):
    """A soft keyboard tock: a short high tone and a small low knock — no noise."""
    n = int(SR * 0.05)
    t = tt(n)
    s = 0.22 * np.sin(2 * np.pi * (1900 + v * 120) * t) * np.exp(-t * 420)
    s += 0.35 * np.sin(2 * np.pi * (210 + v * 15) * t) * np.exp(-t * 110)
    return fade(s * g, 0.0005, 0.01)


def tick(m=100, g=1.0):
    n = int(SR * 0.04)
    t = tt(n)
    return fade(0.3 * np.sin(2 * np.pi * min(hz(m), 3200) * t) * np.exp(-t * 260) * g, 0.0005, 0.01)


def knock(g=1.0):
    n = int(SR * 0.18)
    t = tt(n)
    s = 0.5 * np.sin(2 * np.pi * 880 * t) * np.exp(-t * 70) + 0.6 * np.sin(2 * np.pi * 150 * t) * np.exp(-t * 32)
    return fade(s * g, 0.0005, 0.02)


# ------------------------------------------------------------------ harmony
CHORDS = [  # one per bar (2.4 s): Fm, Db, Ab, Eb
    ([53, 56, 60, 65], 41),
    ([49, 53, 56, 61], 37),
    ([48, 51, 56, 60], 44),
    ([51, 55, 58, 63], 39),
]


def chord_at(t):
    return CHORDS[int(t // BAR) % 4]


# ------------------------------------------------------------------ drums: a soft kick and a rim, no hats
def drum_bar(t0, t1, style):
    t = t0
    while t < t1 - 1e-6:
        e8 = int(round((t % BAR) / (BEAT / 2))) % 8   # eighth inside the bar
        if style == 'full':
            if e8 in (0, 4) or (e8 == 5 and int(t // BAR) % 2):
                add(drums, t, kick(0.85 if e8 != 5 else 0.55)); KICKS.append(t)
            if e8 in (2, 6):
                add(drums, t, rim(), 0.55, 0.08, rev=0.25)
        elif style == 'half':
            if e8 == 0:
                add(drums, t, kick(0.75)); KICKS.append(t)
            if e8 == 4:
                add(drums, t, rim(), 0.4, 0.0, rev=0.3)
        elif style == 'build':
            add(drums, t, kick(0.7)); KICKS.append(t)
            add(drums, t, rim(), 0.2 + 0.35 * (t - t0) / max(1e-3, t1 - t0), 0, rev=0.2)
        t += BEAT / 2


K0, K1 = SEC['KNOWLEDGE']
B1 = SEC['BUILT-IN MCP'][1]
STROBE = (SEC['OMNIXON'][0], SLAM)
DRUMS = [(*SEC['CHANNELS'], 'full'), (*SEC['SIMPLICITY'], 'half'), (*SEC['ANY MODEL'], 'full'), (K0 + 2 * BAR, K1, 'half'),
         (*SEC['MCP TOOLS'], 'full'), (*SEC['AGENTS'], 'full'), (SEC['BUILT-IN MCP'][0], B1 - BAR / 2, 'full'),
         (B1 - BAR / 2, B1, 'build'), (*STROBE, 'build')]
for a, b, style in DRUMS:
    drum_bar(a, b, style)


# ------------------------------------------------------------------ bass: round, mostly fundamental
def bass_note(m, dur, g=1.0, pluck=True):
    n = int(SR * dur)
    t = tt(n)
    f = hz(m)
    s = np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t) + 0.08 * np.sin(2 * np.pi * 3 * f * t)
    e = np.exp(-t * (3.2 / max(dur, 0.1))) if pluck else np.minimum(1, t / 0.08) * np.exp(-t * 0.5)
    return fade(np.tanh(s * e * 1.1) * g, 0.006, 0.04)


BASS = [(*SEC['CHANNELS'], 'quarters'), (*SEC['SIMPLICITY'], 'long'), (*SEC['ANY MODEL'], 'quarters'), (*SEC['KNOWLEDGE'], 'long'),
        (SEC['MCP TOOLS'][0], B1, 'quarters'), (*STROBE, 'eighths')]
for t0, t1, kind in BASS:
    t = t0
    while t < t1 - 1e-6:
        _, root = chord_at(t)
        if kind == 'long':
            left = BAR - (t % BAR)
            d = min(left if left > 1e-6 else BAR, t1 - t)
            add(music, t, bass_note(root, d, 0.5, pluck=False), 0.42)
            t += d
        else:
            step = BEAT if kind == 'quarters' else BEAT / 2
            octave = 12 if (kind == 'quarters' and int(round(t / step)) % 4 == 3) else 0
            add(music, t, bass_note(root + octave, step * 0.95, 0.5), 0.55)
            t += step


# ------------------------------------------------------------------ pads: soft, slow, chorused
def pad(notes, t0, t1, g, bright=4):
    n = int(SR * (t1 - t0 + 1.4))
    out = np.zeros(n)
    for m in notes:
        for det in (-0.003, 0.0, 0.0035):
            out += warm(hz(m), n, bright, 2.2, det)
    att = np.minimum(1, tt(n) / 0.5)
    rel = np.clip((t1 - t0 + 1.4 - tt(n)) / 1.4, 0, 1)
    return out * att * rel * g / len(notes)


CH0 = SEC['CHANNELS'][0]
for b in range(int(np.ceil(SLAM / BAR))):
    t0 = b * BAR
    notes, _ = CHORDS[b % 4]
    t1 = min(t0 + BAR, SLAM)
    g = 0.12 if (t0 < CH0 or K0 <= t0 < K0 + 2 * BAR) else 0.085
    add(music, t0, pad(notes, t0, t1, g, 3 if t0 < CH0 else 4), 1.0, 0, rev=0.5)
# the resolution: Ab add9, wide and bright
final = [44, 51, 56, 58, 60, 63, 68, 70]
add(music, SLAM + 0.28, pad(final, SLAM + 0.28, DUR, 0.17, 5), 1.0, 0, rev=0.7)
add(music, SLAM + 0.28, bass_note(32, DUR - SLAM - 0.28, 0.8, pluck=False), 0.7)
for i, m in enumerate([68, 72, 75, 80]):
    add(music, SLAM + 0.4 + i * 0.15, vibe(m + 12, 2.4, 0.22), 1.0, [-0.4, -0.1, 0.2, 0.45][i], rev=0.6)

# ------------------------------------------------------------------ arp: mallets on eighths with a dotted echo
ARP_SECTIONS = [(*SEC['SIMPLICITY'], 0, 0.1), (*SEC['ANY MODEL'], 0, 0.11), (*SEC['KNOWLEDGE'], 12, 0.1), (*SEC['MCP TOOLS'], 0, 0.11),
                (*SEC['AGENTS'], 12, 0.12), (*SEC['BUILT-IN MCP'], 12, 0.12)]
for t0, t1, oct_, g in ARP_SECTIONS:
    t = t0
    i = 0
    while t < t1 - 1e-6:
        notes, _ = chord_at(t)
        m = notes[[0, 1, 2, 3, 2, 1, 3, 2][i % 8]] + 12 + oct_
        p = mallet(m, 0.5, g, 0.7)
        pan = -0.35 if i % 2 else 0.35
        add(music, t, p, 1.0, pan, rev=0.3)
        add(music, t + 0.75 * BEAT, p, 0.3, -pan, rev=0.45)
        t += BEAT / 2
        i += 1

# ------------------------------------------------------------------ intro drone
n = int(SR * (CH0 + 0.4))
drone = np.sin(2 * np.pi * hz(29) * tt(n)) * 0.6 + warm(hz(41), n, 4, 2.0) * 0.3
drone *= np.minimum(1, tt(n) / 1.5) * np.clip((CH0 + 0.4 - tt(n)) / 0.5, 0, 1)
add(music, 0.0, drone, 0.2, 0, rev=0.3)

# ------------------------------------------------------------------ sound design, from the cue sheet
events = FILM['events']
for e in events:
    t, ty = e['t'], e['type']
    g = e.get('g', 1.0)
    pan = float(rng.uniform(-0.35, 0.35))
    if ty == 'tok':            # a letter (or a node) landing: one marimba note
        add(sfx, t, mallet(e['n'], 0.5, 1.0), 0.55 * g, pan, rev=0.3)
    elif ty == 'thump':        # the weight of a landing
        add(sfx, t, thump(), 0.75 * g, 0, rev=0.15); KICKS.append(t)
    elif ty == 'boom':
        add(sfx, t, boom(), 0.9 * g, 0, rev=0.35); KICKS.append(t)
    elif ty == 'impact':
        add(sfx, t, boom(0.7), 0.7 * g, 0, rev=0.3); KICKS.append(t)
    elif ty == 'hit':
        add(sfx, t, kick(0.9), 0.7 * g, 0, rev=0.2); add(sfx, t, rim(), 0.4 * g, 0.1, rev=0.3)
    elif ty in ('swell', 'whoosh', 'swirl'):
        add(sfx, t - e.get('d', 0.5) * 0.5, swell(e.get('d', 0.5), e.get('hi')), 0.28 * g, 0, rev=0.4)
    elif ty == 'warp':
        add(sfx, t, swell(e['d'], True), 0.32, 0, rev=0.5)
    elif ty == 'riser':
        add(sfx, t, riser(e['d'], e.get('hi')), 0.28, 0, rev=0.4)
    elif ty == 'sweep':
        add(sfx, t, swell(e['d'], e.get('hi')), 0.22, 0, rev=0.5)
    elif ty == 'reverse':
        add(sfx, t, vibe(84, e['d'], 1.0)[::-1], 0.3, 0, rev=0.6)
    elif ty == 'fall':
        add(sfx, t, fall_glide(e.get('n', 72)), 0.25, pan, rev=0.3)
    elif ty == 'pop':
        add(sfx, t, pop(e['n']), 0.4, 0, rev=0.25)
    elif ty == 'bubble':
        add(sfx, t, pop(e['n']), 0.32, pan, rev=0.3); add(sfx, t + 0.04, mallet(e['n'] + 12, 0.4, 0.5), 0.3, -pan, rev=0.3)
    elif ty == 'blip':
        add(sfx, t, mallet(e['n'], 0.3, 1.0, 0.5), 0.4 * g, 0.2, rev=0.3)
    elif ty == 'tick':
        add(sfx, t, tick(e.get('n', 100)), 0.5 * g, pan)
    elif ty == 'key':
        add(sfx, t, key(e.get('v', 0)), 0.45 * g, pan, rev=0.05)
    elif ty == 'stream':
        add(sfx, t, mallet(84 + [0, 3, 7, 10][e.get('v', 0)], 0.35, 1.0, 0.4), 0.14, pan, rev=0.3)
    elif ty in ('chime', 'pluck'):
        add(sfx, t, vibe(e['n'], 1.8), 0.32, pan, rev=0.45)
    elif ty == 'land':         # a model landing in the reel
        add(sfx, t, thump(0.8), 0.6, 0, rev=0.2); add(sfx, t, vibe([84, 87, 89, 91][e['i']], 1.4), 0.28, 0, rev=0.4)
    elif ty == 'snap':         # a tool docking / a call arriving
        add(sfx, t, knock(), 0.42, [-0.4, 0.4, 0.3, 0, -0.3, -0.4][e['i'] % 6], rev=0.2)
    elif ty == 'flood':        # a colour flood: a low swell and a soft thump
        add(sfx, t - 0.15, swell(0.4, True), 0.22, [-0.4, 0.4, -0.4, 0.4][e['i'] % 4], rev=0.3)
        add(sfx, t, thump(0.6), 0.5, 0, rev=0.2)
    elif ty == 'stutter':      # the feature strobe: a mallet chord on every word
        for k, m in enumerate([[65, 68, 72], [61, 65, 68], [60, 63, 68], [63, 67, 70], [65, 68, 72], [61, 65, 70]][e['i'] % 6]):
            add(sfx, t, mallet(m + 12, 0.5, 1.0, 0.8), 0.22, [-0.3, 0, 0.3][k], rev=0.3)
        add(drums, t, kick(0.7), 0.6); KICKS.append(t)

# ------------------------------------------------------------------ sidechain the music gently to every kick
duck = np.ones(N)
for k in KICKS:
    i = int(k * SR)
    n = min(int(0.3 * SR), N - i)
    if n <= 0:
        continue
    d = 1 - 0.45 * np.exp(-tt(n) / 0.1)
    duck[i:i + n] = np.minimum(duck[i:i + n], d)
music *= duck

# ------------------------------------------------------------------ a dark hall: lowpassed tail, a short pre-delay
ir_n = int(SR * 2.2)
ir_t = tt(ir_n)
ir = np.stack([fft_filter(rng.standard_normal(ir_n), 180, 3200) * np.exp(-ir_t * 2.8) for _ in range(2)])
ir[:, : int(0.018 * SR)] = 0
size = 1 << int(np.ceil(np.log2(N + ir_n)))
wet = np.stack([np.fft.irfft(np.fft.rfft(send[c], size) * np.fft.rfft(ir[c], size), size)[:N] for c in range(2)])
wet /= np.max(np.abs(wet)) + 1e-9


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12)


for name, bus in [('music', music), ('drums', drums), ('sfx', sfx), ('wet', wet)]:
    print(f'{name:6s} peak {20 * np.log10(np.max(np.abs(bus)) + 1e-12):6.1f} dB   rms {rms_db(bus):6.1f} dB')
mix = music * 2.0 + drums * 0.55 + sfx * 0.85 + wet * 0.2
# master: a little lift off the sub, a gentle top cut (nothing hissy), a soft limiter, -1.5 dBFS
mix = np.stack([fft_filter(c, 28, 11000, 1.0) for c in mix])
mix /= np.percentile(np.abs(mix), 99.9)
mix = np.tanh(mix * 0.85) / np.tanh(0.85)
tail = np.ones(N)
tail[-int(0.6 * SR):] = np.linspace(1, 0, int(0.6 * SR)) ** 2
mix *= tail
mix *= 10 ** (-1.5 / 20) / np.max(np.abs(mix))

pcm = (mix.T * 32767).astype(np.int16)
out = HERE / f'out/music-{LANG}.wav'
with wave.open(str(out), 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print(f'{out}  {DUR:.0f}s  peak -1.5 dBFS, {len(events)} cues')
