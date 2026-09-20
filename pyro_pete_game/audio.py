"""Music for the title, menus, gameplay and the two endings.

The repository ships no audio files -- adding minutes of .ogg would dwarf
the rest of the project -- so the tracks are synthesised into memory at
startup from note data (see _TRACKS below). A few seconds of numpy per
track buys a soundtrack that costs nothing in the repo and sounds the
same on every machine.

Everything here degrades to silence rather than raising: a machine with
no audio device (or a headless test run under SDL_AUDIODRIVER=dummy)
gets an AudioManager whose methods are no-ops, so nothing in the game
needs to guard its calls.

Usage from main.py:
    audio = AudioManager()
    audio.play("title")        # loops until something else is played
    audio.play("win", loop=False)
"""

import math
from functools import partial

import numpy as np
import pygame

SAMPLE_RATE = 44100

# Semitone offsets from A4 for the note names used in _TRACKS.
_NOTE_BASE = {"C": -9, "D": -7, "E": -5, "F": -4, "G": -2, "A": 0, "B": 2}


def note_hz(name):
    """'A4' / 'C#5' / 'Eb3' -> frequency in Hz. '-' is a rest (0 Hz)."""
    if name == "-":
        return 0.0
    letter, rest = name[0].upper(), name[1:]
    semis = _NOTE_BASE[letter]
    while rest and rest[0] in "#b":
        semis += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    octave = int(rest)
    return 440.0 * (2.0 ** ((semis + (octave - 4) * 12) / 12.0))


# ------------------------------------------------------------------ synthesis
def _envelope(n, attack, decay, sustain, release):
    """Straight ADSR over n samples, as a 0..1 gain curve."""
    a = min(int(attack * SAMPLE_RATE), n)
    d = min(int(decay * SAMPLE_RATE), max(0, n - a))
    r = min(int(release * SAMPLE_RATE), max(0, n - a - d))
    s = max(0, n - a - d - r)
    return np.concatenate([
        np.linspace(0.0, 1.0, a, endpoint=False),
        np.linspace(1.0, sustain, d, endpoint=False),
        np.full(s, sustain),
        np.linspace(sustain, 0.0, r),
    ])[:n]


def _tone(freq, seconds, wave="tri", gain=0.25, env=(0.01, 0.08, 0.7, 0.12),
          detune=0.0):
    """One note. `detune` in cents adds a second slightly-off oscillator,
    which is what stops the sustained chords sounding like a test tone."""
    n = max(1, int(seconds * SAMPLE_RATE))
    if freq <= 0:
        return np.zeros(n)
    t = np.arange(n) / SAMPLE_RATE

    def osc(f):
        phase = 2 * math.pi * f * t
        if wave == "sine":
            return np.sin(phase)
        if wave == "square":
            return np.sign(np.sin(phase)) * 0.6
        if wave == "saw":
            return 2.0 * ((f * t) % 1.0) - 1.0
        # triangle: mellow default, easiest on the ear over a long loop
        return 2.0 * np.abs(2.0 * ((f * t) % 1.0) - 1.0) - 1.0

    sig = osc(freq)
    if detune:
        sig = 0.6 * sig + 0.4 * osc(freq * (2.0 ** (detune / 1200.0)))
    return sig * _envelope(n, *env) * gain


def _sequence(notes, beat, **kw):
    """notes: [(name, beats), ...] -> one concatenated mono track."""
    return np.concatenate([_tone(note_hz(n), b * beat, **kw) for n, b in notes])


def _mix(*layers):
    """Sum layers of differing length, padding to the longest, then soft-clip."""
    longest = max(len(x) for x in layers)
    out = np.zeros(longest)
    for layer in layers:
        out[:len(layer)] += layer
    return np.tanh(out)


# ------------------------------------------------------------------- tracks
def _build_title():
    """Slow, minor, a bit stately -- it plays under the opening alarm."""
    beat = 0.5
    lead = _sequence([("A4", 2), ("C5", 1), ("E5", 1), ("D5", 2), ("C5", 2),
                      ("A4", 2), ("G4", 1), ("A4", 1), ("E4", 4)],
                     beat, wave="tri", gain=0.22, detune=8,
                     env=(0.04, 0.2, 0.75, 0.3))
    pad = _sequence([("A3", 4), ("F3", 4), ("C3", 4), ("E3", 4)],
                    beat, wave="sine", gain=0.16, detune=12,
                    env=(0.3, 0.4, 0.8, 0.6))
    bass = _sequence([("A2", 4), ("F2", 4), ("C2", 4), ("E2", 4)],
                     beat, wave="tri", gain=0.20, env=(0.02, 0.15, 0.6, 0.2))
    return _mix(lead, pad, bass)


def _build_menu():
    """Lighter and shorter than the title -- you sit on this screen for
    seconds, not minutes, so it loops tighter."""
    beat = 0.42
    lead = _sequence([("E4", 1), ("A4", 1), ("C5", 1), ("B4", 1),
                      ("A4", 1), ("G4", 1), ("E4", 2)],
                     beat, wave="tri", gain=0.18, detune=6,
                     env=(0.02, 0.12, 0.6, 0.18))
    bass = _sequence([("A2", 2), ("A2", 2), ("F2", 2), ("E2", 2)],
                     beat, wave="sine", gain=0.20, env=(0.02, 0.2, 0.5, 0.2))
    return _mix(lead, bass)


def _build_game(intensity=0.0):
    """The gameplay bed, dialled from calm to frantic by `intensity`.

    intensity is 0.0 on stage 1 and 1.0 on stage 10 (see game_track).
    One track parameterised across the campaign, rather than ten
    hand-written ones, so the progression is monotonic by construction --
    every knob below moves one way only, and a stage can never
    accidentally end up calmer than the one before it.

    What actually changes, and why each reads as panic:

    * **tempo** -- the beat shortens from 0.30s to 0.17s. The single
      strongest cue; everything else is reinforcement.
    * **timbre** -- the arpeggio starts as a soft triangle and crosses to
      a square wave, which is buzzier and more urgent.
    * **the pulse** -- the eighth-note bass gets louder and drier
      (shorter release), so late stages feel like a countdown rather
      than a groove.
    * **detune** -- the pad's second oscillator drifts from 8 to 34
      cents. Slight detuning is warmth; heavy detuning beats against
      itself and reads as queasy.
    * **the tritone** -- from the midpoint a dissonant Eb against the A
      fades in. It is the interval that refuses to resolve, and it is
      doing most of the "something is wrong" work on stages 6+.

    A swept-sine siren used to sit under stages 8-10 as well. It was cut:
    a continuous glide on a pure sine reads as a wobbling hum rather than
    as an alarm, and it was the most noticeable thing about the late
    stages for the wrong reason. The four knobs above carry the ramp on
    their own.
    """
    i = max(0.0, min(1.0, float(intensity)))

    beat = 0.30 - 0.13 * i
    arp_wave = "tri" if i < 0.35 else "square"
    arp_gain = 0.10 + 0.04 * i
    pulse_gain = 0.13 + 0.07 * i
    pulse_release = 0.10 - 0.06 * i
    pad_detune = 8 + 26 * i

    # The melody climbs a fifth over the campaign (A minor -> E minor
    # shapes) so the later stages sit higher and tighter in the ear.
    high = i > 0.6
    arp_notes = ([("A4", 1), ("C5", 1), ("E5", 1), ("C5", 1),
                  ("A4", 1), ("C5", 1), ("E5", 1), ("G5", 1),
                  ("F4", 1), ("A4", 1), ("C5", 1), ("A4", 1),
                  ("G4", 1), ("B4", 1), ("D5", 1), ("B4", 1)]
                 if not high else
                 [("E5", 1), ("G5", 1), ("B5", 1), ("G5", 1),
                  ("E5", 1), ("G5", 1), ("B5", 1), ("D6", 1),
                  ("C5", 1), ("E5", 1), ("G5", 1), ("E5", 1),
                  ("D5", 1), ("F5", 1), ("A5", 1), ("F5", 1)])

    arp = _sequence(arp_notes, beat, wave=arp_wave, gain=arp_gain,
                    env=(0.005, 0.06, 0.35, 0.08))
    pulse = _sequence([("A2", 1)] * 8 + [("F2", 1)] * 4 + [("G2", 1)] * 4,
                      beat, wave="saw", gain=pulse_gain,
                      env=(0.005, 0.09, 0.2, max(0.02, pulse_release)))
    pad = _sequence([("A3", 8), ("F3", 4), ("G3", 4)],
                    beat, wave="sine", gain=0.13, detune=pad_detune,
                    env=(0.2, 0.3, 0.8, 0.4))
    layers = [arp, pulse, pad]

    if i >= 0.5:
        # Eb against A: a tritone, the most unstable interval there is.
        # Faded in by how far past the midpoint the stage sits, so it
        # arrives as unease rather than a jump-scare on stage 6.
        weight = (i - 0.5) / 0.5
        layers.append(_sequence([("Eb4", 4), ("Eb4", 4), ("Eb4", 4), ("Eb4", 4)],
                                beat, wave="tri", gain=0.11 * weight,
                                detune=18, env=(0.25, 0.3, 0.7, 0.4)))

    return _mix(*layers)


def _build_win():
    """Short major fanfare -- one-shot, not looped."""
    beat = 0.16
    lead = _sequence([("C5", 1), ("E5", 1), ("G5", 1), ("C6", 3), ("G5", 1),
                      ("C6", 4)],
                     beat, wave="tri", gain=0.26, detune=6,
                     env=(0.01, 0.1, 0.7, 0.25))
    bass = _sequence([("C3", 3), ("G3", 3), ("C4", 5)],
                     beat, wave="sine", gain=0.22, env=(0.01, 0.15, 0.6, 0.3))
    return _mix(lead, bass)


def _build_loss():
    """Short descending minor figure -- the other one-shot."""
    beat = 0.26
    lead = _sequence([("A4", 2), ("G4", 2), ("F4", 2), ("E4", 4)],
                     beat, wave="tri", gain=0.24, detune=10,
                     env=(0.02, 0.2, 0.7, 0.5))
    bass = _sequence([("A2", 4), ("E2", 6)],
                     beat, wave="sine", gain=0.20, env=(0.02, 0.3, 0.5, 0.5))
    return _mix(lead, bass)


# How many stages the gameplay bed is spread across. Reads levels.
# STAGE_COUNT indirectly -- audio.py deliberately does not import levels
# (it would drag pygame display setup into the music tests), so this is
# asserted against the real campaign length in tests/test_campaign.py.
STAGE_TRACKS = 10


def game_track(stage_index):
    """Track name for a 0-based stage index: 'game_1' ... 'game_10'.

    Out-of-range indices clamp rather than raise, matching levels.get(),
    so a stage index that has drifted can only ever pick the wrong music
    and never crash a run.
    """
    n = max(0, min(STAGE_TRACKS - 1, int(stage_index)))
    return f"game_{n + 1}"


_TRACKS = {
    "title": _build_title,
    "menu": _build_menu,
    "game": _build_game,        # stage-1 intensity; kept as the neutral default
    "win": _build_win,
    "loss": _build_loss,
}

# One gameplay bed per stage, calm (stage 1) through frantic (stage 10).
# Built by partial rather than by writing ten builders so the ramp is
# defined in exactly one place -- see _build_game for what each knob
# does. They stay lazy: AudioManager only synthesises a track the first
# time it is played, so reaching stage 3 never costs the seven stages
# you haven't seen.
for _n in range(STAGE_TRACKS):
    _TRACKS[f"game_{_n + 1}"] = partial(
        _build_game, _n / (STAGE_TRACKS - 1))
del _n

# Endings are stingers, not beds: they play once and let the results
# panel sit in silence rather than looping a fanfare under it.
_ONE_SHOT = {"win", "loss"}


class AudioManager:
    """Owns the mixer and the synthesised tracks.

    Tracks are built lazily on first play so start-up isn't held up
    synthesising music the player may never hear (nobody reaches the loss
    sting in the first second of the game).
    """

    def __init__(self, volume=0.55):
        self.enabled = False
        self.volume = volume
        self.current = None
        self._sounds = {}
        self._channel = None
        try:
            # pygame.init() may already have opened the mixer at its own
            # defaults; close it first so the sample rate here is the one
            # the synthesised buffers were written at (a mismatch plays
            # everything at the wrong pitch).
            pygame.mixer.quit()
        except pygame.error:
            pass
        try:
            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2,
                              buffer=512)
            pygame.mixer.set_num_channels(8)
            self._channel = pygame.mixer.Channel(0)
            self.enabled = True
        except pygame.error:
            # No audio device (CI, a dummy SDL driver, a machine with sound
            # disabled). Every method below becomes a no-op.
            self.enabled = False

    # -- internals ------------------------------------------------------
    def _sound(self, name):
        if name not in self._sounds:
            mono = _TRACKS[name]()
            stereo = np.repeat((mono * 32767).astype(np.int16)[:, None], 2, axis=1)
            self._sounds[name] = pygame.sndarray.make_sound(
                np.ascontiguousarray(stereo))
        return self._sounds[name]

    # -- API -----------------------------------------------------------
    def play(self, name, loop=None):
        """Switch to `name`. Re-playing the track already running is
        ignored, so calling this every frame from a screen's update() is
        safe and the music doesn't restart on every tick."""
        if not self.enabled or name not in _TRACKS:
            return
        if name == self.current:
            return
        if loop is None:
            loop = name not in _ONE_SHOT
        try:
            sound = self._sound(name)
            sound.set_volume(self.volume)
            self._channel.stop()
            self._channel.play(sound, loops=-1 if loop else 0)
            self.current = name
        except (pygame.error, ValueError):
            self.enabled = False

    def stop(self):
        if not self.enabled:
            return
        self._channel.stop()
        self.current = None

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, volume))
        if self.enabled and self._channel.get_sound():
            self._channel.get_sound().set_volume(self.volume)

    def toggle_mute(self):
        """Returns True if audio is now muted. Restores whatever the
        volume was before muting rather than a hard-coded level."""
        if not self.enabled:
            return True
        if self.volume > 0:
            self._volume_before_mute = self.volume
            self.set_volume(0.0)
            return True
        self.set_volume(getattr(self, "_volume_before_mute", 0.55))
        return False
