"""
qnexus_core.py  -  the Q-Nexus engine (no user-interface code in this file)
===========================================================================
Everything here is a SIMULATION running on a normal computer. It is not a physical quantum network.

Flow implemented (matches the project PPT):

  Aasrita's voice
     -> entangled Bell-pair channel check     (your 0.py idea: correlation + QBER + decision)
     -> BB84 quantum key distribution         (superposition, measurement, no-cloning)
     -> eavesdropping / noise detection       (QBER)
     -> security decision                     (SECURE / WARNING / COMPROMISED)
     -> voice encrypted with the quantum key  (classical channel carries only encrypted data)
     -> Bhavya receives, verifies and decrypts

Two simulation engines with the SAME physics:
  QiskitBackend   - real Qiskit circuits on the Aer simulator (used when Qiskit is installed)
  BuiltinBackend  - small NumPy model (automatic fallback, always works)
"""
from __future__ import annotations

import hashlib
import hmac
import io
import math
import os
from dataclasses import dataclass, field

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

# ----------------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------------
LEVELS = [0, 5, 10, 15, 20, 100]            # disturbance levels (%)
MODE_EVE, MODE_NOISE = "eve", "noise"
MODE_LABELS = {
    MODE_EVE: "Eavesdropper (Eve intercepts qubits)",
    MODE_NOISE: "Channel noise (qubits get disturbed)",
}

QBER_ALERT = 0.5      # % - above this we say "disturbance detected"
QBER_ABORT = 11.0     # % - BB84 security limit: above this no secret key can be made
TEST_FRACTION = 0.3   # share of sifted bits revealed publicly to measure QBER
MIN_SECRET_BITS = 128
DEFAULT_QUBITS = 4000
BELL_SHOTS = 2048
SAMPLE_RATE = 16000
MAX_SECONDS = 15

SECURE, WARNING, COMPROMISED = "SECURE", "WARNING", "COMPROMISED"


def h2(p: float) -> float:
    """Binary entropy."""
    if p <= 0 or p >= 1:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def secret_fraction(qber_percent: float) -> float:
    """Asymptotic BB84 secret-key fraction: r = 1 - 2*h2(QBER). It reaches 0 near 11 %."""
    return max(0.0, 1.0 - 2.0 * h2(qber_percent / 100.0))


# ----------------------------------------------------------------------------
# Simulation engines
# ----------------------------------------------------------------------------
class BuiltinBackend:
    """NumPy model of the same physics (no Qiskit needed)."""
    name = "Built-in NumPy simulator"
    engine_id = "builtin"

    def bb84_measure(self, a_bits, a_bases, b_bases, eve_mask, eve_bases, noise_p, rng, seed=0):
        n = len(a_bits)
        mixed = rng.random(n) < noise_p                       # depolarised qubit = random result
        eve_known = eve_mask & (eve_bases == a_bases) & ~mixed
        eve_bit = np.where(eve_known, a_bits, rng.integers(0, 2, n))
        eve_guess = np.where(eve_mask, eve_bit, rng.integers(0, 2, n))
        wire_bit = np.where(eve_mask, eve_bit, a_bits)        # Eve re-sends what she measured
        wire_basis = np.where(eve_mask, eve_bases, a_bases)
        mixed = mixed & ~eve_mask
        ok = (wire_basis == b_bases) & ~mixed
        Bhavya = np.where(ok, wire_bit, rng.integers(0, 2, n))
        return Bhavya.astype(int), eve_guess.astype(int)

    def bell_counts(self, level, mode, shots, rng, seed=0):
        d = level / 100.0
        a = rng.integers(0, 2, shots)
        b = a.copy()
        if mode == MODE_EVE:                                  # Eve measures in a random basis
            x_basis = (rng.random(shots) < d) & (rng.random(shots) < 0.5)
            b = np.where(x_basis, rng.integers(0, 2, shots), b)   # X-basis measurement breaks Z correlation
        else:
            b = np.where(rng.random(shots) < d, rng.integers(0, 2, shots), b)
        counts = {"00": 0, "01": 0, "10": 0, "11": 0}
        for key, val in zip(*np.unique(a * 2 + b, return_counts=True)):
            counts[format(int(key), "02b")] = int(val)
        return counts


class QiskitBackend:
    """Real Qiskit circuits on the Aer simulator."""
    name = "Qiskit Aer simulator"
    engine_id = "qiskit"

    def __init__(self):
        from qiskit import QuantumCircuit
        from qiskit_aer import AerSimulator
        from qiskit_aer.noise import NoiseModel, depolarizing_error
        self._QC, self._Aer, self._NM, self._dep = QuantumCircuit, AerSimulator, NoiseModel, depolarizing_error

    def _simulator(self, noise_p):
        nm = self._NM()
        if noise_p > 0:                                       # noise lives on the 'id' gate = the channel
            nm.add_all_qubit_quantum_error(self._dep(float(noise_p), 1), ["id"])
        return self._Aer(noise_model=nm)

    def _bb84_circuit(self, bit, a_basis, b_basis, eve_basis):
        qc = self._QC(1, 2)                                   # clbit0 = Bhavya, clbit1 = Eve
        if bit:
            qc.x(0)                                           # Aasrita encodes the bit
        if a_basis:
            qc.h(0)                                           # ... in the X basis (superposition)
        qc.id(0)                                              # quantum channel (noise attaches here)
        if eve_basis >= 0:                                    # Eve: measure, then re-send what she saw
            if eve_basis:
                qc.h(0)
            qc.measure(0, 1)
            if eve_basis:
                qc.h(0)
        if b_basis:
            qc.h(0)                                           # Bhavya chooses his measurement basis
        qc.measure(0, 0)
        return qc

    def bb84_measure(self, a_bits, a_bases, b_bases, eve_mask, eve_bases, noise_p, rng, seed=0):
        n = len(a_bits)
        eb = np.where(eve_mask, eve_bases, -1)
        code = ((a_bits * 2 + a_bases) * 2 + b_bases) * 3 + (eb + 1)
        Bhavya = np.zeros(n, dtype=int)
        eve_guess = rng.integers(0, 2, n)
        sim = self._simulator(noise_p)
        for i, c in enumerate(np.unique(code)):               # identical qubits are simulated together
            idx = np.flatnonzero(code == c)
            c = int(c)
            e = c % 3 - 1
            c //= 3
            b = c % 2
            c //= 2
            ab = c % 2
            bit = c // 2
            qc = self._bb84_circuit(bit, ab, b, e)
            mem = sim.run(qc, shots=len(idx), memory=True, seed_simulator=seed + i).result().get_memory()
            for j, m in zip(idx, mem):
                m = m.replace(" ", "")                        # format: clbit1 clbit0
                Bhavya[j] = int(m[-1])
                if e >= 0:
                    eve_guess[j] = int(m[-2])
        return Bhavya, eve_guess

    def bell_counts(self, level, mode, shots, rng, seed=0):
        d = level / 100.0
        noise_p = d if mode == MODE_NOISE else 0.0
        if mode == MODE_EVE:
            n_eve = int(rng.binomial(shots, d))
            n_z = int(rng.binomial(n_eve, 0.5))
            plan = [(-1, shots - n_eve), (0, n_z), (1, n_eve - n_z)]
        else:
            plan = [(-1, shots)]
        sim = self._simulator(noise_p)
        counts = {"00": 0, "01": 0, "10": 0, "11": 0}
        for i, (eve_basis, n) in enumerate(plan):
            if n <= 0:
                continue
            qc = self._QC(2, 3)
            qc.h(0)                                           # superposition
            qc.cx(0, 1)                                       # entanglement (Bell pair)
            qc.id(1)                                          # channel towards Bhavya
            if eve_basis >= 0:
                if eve_basis:
                    qc.h(1)
                qc.measure(1, 2)
                if eve_basis:
                    qc.h(1)
            qc.measure([0, 1], [0, 1])
            res = sim.run(qc, shots=n, seed_simulator=seed + i).result().get_counts()
            for key, val in res.items():
                counts[key.replace(" ", "")[-2:]] += int(val)
        return counts

    def verify(self):
        """Quick self-check so a mis-behaving Qiskit install is caught and we fall back safely."""
        rng = np.random.default_rng(1)
        n = 400
        a = rng.integers(0, 2, n)
        ab = rng.integers(0, 2, n)
        bb = rng.integers(0, 2, n)
        eb = rng.integers(0, 2, n)
        none = np.zeros(n, dtype=bool)
        full = np.ones(n, dtype=bool)

        def q(eve_mask, noise_p):
            Bhavya, _ = self.bb84_measure(a, ab, bb, eve_mask, eb, noise_p, rng, seed=5)
            s = ab == bb
            return float(np.mean(a[s] != Bhavya[s])) * 100

        ideal, noisy, eve = q(none, 0.0), q(none, 1.0), q(full, 0.0)
        if not (ideal < 1.0 and noisy > 35 and 15 < eve < 35):
            raise RuntimeError(f"Qiskit self-check failed (ideal={ideal:.1f}, noise={noisy:.1f}, eve={eve:.1f})")


def get_backend(prefer="qiskit"):
    """Return (backend, message). Falls back to the built-in simulator if Qiskit is missing/broken."""
    if prefer == "qiskit":
        try:
            backend = QiskitBackend()
            backend.verify()
            return backend, "Qiskit Aer detected and self-check passed."
        except Exception as exc:                              # noqa: BLE001
            return BuiltinBackend(), f"Qiskit not usable ({type(exc).__name__}: {exc}). Using the built-in simulator."
    return BuiltinBackend(), "Built-in simulator selected."


# ----------------------------------------------------------------------------
# Entanglement monitor (Bell pair)  -  the idea from 0.py, now mode-aware
# ----------------------------------------------------------------------------
@dataclass
class BellResult:
    counts: dict
    correlation: float
    qber: float
    status: str
    action: str


def run_bell(backend, level, mode, shots=BELL_SHOTS, seed=0) -> BellResult:
    rng = np.random.default_rng(seed + 1000)
    counts = backend.bell_counts(level, mode, shots, rng, seed=seed)
    total = sum(counts.values())
    corr = (counts["00"] + counts["11"]) / total * 100
    qber = (counts["01"] + counts["10"]) / total * 100
    if qber <= QBER_ALERT:
        status, action = "GOOD", "Entanglement intact - continue"
    elif qber < QBER_ABORT:
        status, action = "WARNING", "Entanglement degraded - monitor the channel"
    else:
        status, action = "CRITICAL", "Entanglement lost - stop / reroute"
    return BellResult(counts, corr, qber, status, action)


# ----------------------------------------------------------------------------
# BB84 key distribution
# ----------------------------------------------------------------------------
@dataclass
class QKDResult:
    level: int
    mode: str
    n_qubits: int
    a_bits: np.ndarray
    a_bases: np.ndarray
    b_bases: np.ndarray
    Bhavya_bits: np.ndarray
    eve_mask: np.ndarray
    eve_guess: np.ndarray
    key_idx: np.ndarray
    n_sifted: int
    n_test: int
    qber: float
    secret_frac: float
    n_secret_bits: int
    status: str
    session_key: bytes | None
    eve_key: bytes | None
    eve_match_percent: float
    errors_in_key: int
    reason: str = ""


def _pack(bits) -> bytes:
    return np.packbits(np.asarray(bits, dtype=np.uint8)).tobytes()


def derive_key(bits, n_secret_bits: int) -> bytes:
    """Privacy amplification: hash the long raw key down to a short, fully secret session key."""
    n_bytes = min(32, n_secret_bits // 8)
    return hashlib.shake_256(_pack(bits) + b"Q-NEXUS-v1").digest(n_bytes)


def run_qkd(backend, level, mode, n_qubits=DEFAULT_QUBITS, seed=7) -> QKDResult:
    rng = np.random.default_rng(seed)
    d = level / 100.0
    a_bits = rng.integers(0, 2, n_qubits)          # Aasrita: random bits
    a_bases = rng.integers(0, 2, n_qubits)         # Aasrita: random bases (0 = Z, 1 = X)
    b_bases = rng.integers(0, 2, n_qubits)         # Bhavya: random bases
    eve_bases = rng.integers(0, 2, n_qubits)
    if mode == MODE_EVE:
        eve_mask, noise_p = rng.random(n_qubits) < d, 0.0
    else:
        eve_mask, noise_p = np.zeros(n_qubits, dtype=bool), d

    Bhavya_bits, eve_guess = backend.bb84_measure(
        a_bits, a_bases, b_bases, eve_mask, eve_bases, noise_p, rng, seed=seed)

    sifted = np.flatnonzero(a_bases == b_bases)    # keep only matching bases (public discussion)
    perm = rng.permutation(len(sifted))
    n_test = int(len(sifted) * TEST_FRACTION)      # sacrifice some bits to measure QBER
    test_idx = sifted[perm[:n_test]]
    key_idx = np.sort(sifted[perm[n_test:]])
    qber = float(np.mean(a_bits[test_idx] != Bhavya_bits[test_idx])) * 100 if n_test else 100.0

    frac = secret_fraction(qber)
    n_secret = int(len(key_idx) * frac)
    errors_in_key = int(np.sum(a_bits[key_idx] != Bhavya_bits[key_idx]))
    eve_match = float(np.mean(eve_guess[key_idx] == a_bits[key_idx])) * 100 if len(key_idx) else 50.0

    if qber >= QBER_ABORT or n_secret < MIN_SECRET_BITS:
        status = COMPROMISED
        if qber >= QBER_ABORT:
            reason = (f"QBER {qber:.1f}% is at/above the {QBER_ABORT:.0f}% limit - no secret key can be "
                      f"distilled, so the key is discarded and the link is aborted.")
        else:
            reason = (f"QBER {qber:.1f}% is close to the {QBER_ABORT:.0f}% limit: only {n_secret} secret bits "
                      f"would remain (minimum {MIN_SECRET_BITS}). Too short to be safe, so the link is aborted.")
        session_key = eve_key = None
    else:
        status = WARNING if qber > QBER_ALERT else SECURE
        reason = ("Disturbance detected - possible eavesdropper or noise. Key is shortened by privacy "
                  "amplification and is still safe to use." if status == WARNING
                  else "No disturbance detected - QBER is ~0%.")
        # Error reconciliation is simulated: Bhavya corrects his bits to Aasrita's (real systems use Cascade/LDPC).
        session_key = derive_key(a_bits[key_idx], n_secret)
        eve_key = derive_key(eve_guess[key_idx], n_secret)

    return QKDResult(level, mode, n_qubits, a_bits, a_bases, b_bases, Bhavya_bits, eve_mask, eve_guess,
                     key_idx, len(sifted), n_test, qber, frac, n_secret, status,
                     session_key, eve_key, eve_match, errors_in_key, reason)


def final_decision(bell: BellResult, qkd: QKDResult) -> dict:
    """Combine entanglement health + BB84 result into one security decision."""
    if qkd.status == COMPROMISED or bell.status == "CRITICAL":
        return {"status": COMPROMISED, "title": "CHANNEL COMPROMISED - TRANSMISSION BLOCKED",
                "action": "Key discarded. Stop transmission and reroute / retry on a clean channel."}
    if qkd.status == WARNING or bell.status == "WARNING":
        return {"status": WARNING, "title": "DISTURBANCE DETECTED - SECURE KEY STILL POSSIBLE",
                "action": "Key shortened by privacy amplification. Voice is sent encrypted; monitor the channel."}
    return {"status": SECURE, "title": "CHANNEL SECURE",
            "action": "No disturbance. Voice is sent encrypted with the quantum-derived key."}


def explain_level(level, mode, qkd: QKDResult) -> str:
    if level == 0:
        return "Clean channel: QBER ~0%, full-length key, Bhavya hears Aasrita."
    who = "Eve intercepts" if mode == MODE_EVE else "the channel disturbs"
    if qkd.status == COMPROMISED:
        return f"{who} so many qubits that QBER passes {QBER_ABORT:.0f}%. Key discarded, voice blocked."
    return (f"{who} {level}% of the qubits -> QBER {qkd.qber:.1f}% detected. "
            f"Key shrinks to {qkd.secret_frac * 100:.0f}% and voice is still delivered securely.")


# ----------------------------------------------------------------------------
# Voice: load, encrypt with the quantum key, decrypt
# ----------------------------------------------------------------------------
def load_voice(data: bytes) -> np.ndarray:
    """WAV bytes -> mono float32 at 16 kHz (max 15 s)."""
    sr, x = wavfile.read(io.BytesIO(data))
    if x.ndim > 1:
        x = x.mean(axis=1)
    if x.dtype == np.int16:
        x = x / 32768.0
    elif x.dtype == np.int32:
        x = x / 2147483648.0
    elif x.dtype == np.uint8:
        x = (x.astype(np.float32) - 128) / 128.0
    x = x.astype(np.float32)
    if sr != SAMPLE_RATE:
        g = math.gcd(int(sr), SAMPLE_RATE)
        x = resample_poly(x, SAMPLE_RATE // g, int(sr) // g).astype(np.float32)
    x = x[: SAMPLE_RATE * MAX_SECONDS]
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    return (x / peak * 0.9).astype(np.float32) if peak > 1e-6 else x


def synthetic_voice() -> np.ndarray:
    """Built-in demo sound (a short melody) so the demo works without a microphone."""
    notes = [262, 330, 392, 523, 392, 330, 262]
    t = np.arange(int(0.3 * SAMPLE_RATE)) / SAMPLE_RATE
    parts = []
    for f in notes:
        tone = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t)
        parts.append(tone * np.hanning(len(t)))
    x = np.concatenate(parts).astype(np.float32)
    return x / np.max(np.abs(x)) * 0.8


def to_pcm16(x: np.ndarray) -> np.ndarray:
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)


def wav_bytes(x, sr: int = SAMPLE_RATE) -> bytes:
    arr = np.asarray(x)
    if arr.dtype != np.int16:
        arr = to_pcm16(arr)
    buf = io.BytesIO()
    wavfile.write(buf, sr, arr)
    return buf.getvalue()


def _keystream(key: bytes, nonce: bytes, n: int) -> np.ndarray:
    return np.frombuffer(hashlib.shake_256(key + nonce).digest(n), dtype=np.uint8)


def encrypt(pcm_bytes: bytes, key: bytes):
    """Demo cipher: SHAKE-256 keystream seeded by the quantum key + HMAC tag (use AES-256 / a one-time pad in production)."""
    nonce = os.urandom(16)
    cipher = (np.frombuffer(pcm_bytes, dtype=np.uint8) ^ _keystream(key, nonce, len(pcm_bytes))).tobytes()
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return nonce, cipher, tag


def decrypt(nonce: bytes, cipher: bytes, tag: bytes, key: bytes):
    """Returns plaintext bytes, or None if the integrity check fails."""
    good = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(good, tag):
        return None
    return (np.frombuffer(cipher, dtype=np.uint8) ^ _keystream(key, nonce, len(cipher))).tobytes()


def _bytes_to_audio(raw: bytes, gain=0.25) -> np.ndarray:
    n = len(raw) // 2 * 2
    return (np.frombuffer(raw[:n], dtype=np.int16).astype(np.float32) / 32768.0 * gain)


@dataclass
class VoiceResult:
    sent: bool
    verified: bool = False
    Bhavya_audio: np.ndarray | None = None
    cipher_audio: np.ndarray | None = None       # what anyone tapping the classical line hears
    eve_attempt_audio: np.ndarray | None = None  # Eve decrypting with her partial key
    cipher_bytes: int = 0
    note: str = ""


def transmit_voice(audio: np.ndarray, qkd: QKDResult, decision: dict) -> VoiceResult:
    if decision["status"] == COMPROMISED or qkd.session_key is None:
        return VoiceResult(False, note="Transmission blocked - no safe key. Bhavya receives nothing.")
    pcm = to_pcm16(audio).tobytes()
    nonce, cipher, tag = encrypt(pcm, qkd.session_key)
    plain = decrypt(nonce, cipher, tag, qkd.session_key)      # Bhavya uses his (reconciled) copy of the key
    ok = plain is not None
    res = VoiceResult(True, ok, _bytes_to_audio(plain, 1.0) if ok else None,
                      _bytes_to_audio(cipher), None, len(cipher),
                      "Bhavya verified the integrity tag and decrypted the voice." if ok
                      else "Integrity check failed - message rejected.")
    if qkd.eve_key is not None and qkd.mode == MODE_EVE and qkd.level > 0:
        wrong = (np.frombuffer(cipher, dtype=np.uint8) ^ _keystream(qkd.eve_key, nonce, len(cipher))).tobytes()
        res.eve_attempt_audio = _bytes_to_audio(wrong)
    return res


# Effect of disturbance on a plain (unprotected) classical channel - from your audio notebook
VOICE_STRENGTH = {0: 1.0, 5: 1.0, 10: 1.0, 15: 1.0, 20: 1.0, 100: 0.0}
NOISE_STRENGTH = {0: 0.0, 5: 0.015, 10: 0.03, 15: 0.07, 20: 0.15, 100: 1.0}


def classical_noisy(audio: np.ndarray, level: float, seed=3) -> np.ndarray:
    """Any level 0-100 works: values between the table entries are interpolated."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 1, len(audio)).astype(np.float32)
    noise /= np.max(np.abs(noise)) + 1e-9
    points = sorted(VOICE_STRENGTH)
    voice_gain = float(np.interp(level, points, [VOICE_STRENGTH[p] for p in points]))
    noise_gain = float(np.interp(level, points, [NOISE_STRENGTH[p] for p in points]))
    return np.clip(voice_gain * audio + noise_gain * noise, -1, 1).astype(np.float32)


# ----------------------------------------------------------------------------
# Run every disturbance level
# ----------------------------------------------------------------------------
def run_all_levels(backend, mode, n_qubits=DEFAULT_QUBITS, seed=7):
    rows = []
    for level in LEVELS:
        bell = run_bell(backend, level, mode, seed=seed + level)
        qkd = run_qkd(backend, level, mode, n_qubits, seed=seed + level)
        dec = final_decision(bell, qkd)
        rows.append({
            "Level (%)": level,
            "Bell correlation (%)": round(bell.correlation, 1),
            "QBER (%)": round(qkd.qber, 2),
            "Secret key (%)": round(qkd.secret_frac * 100, 1),
            "Secret bits": qkd.n_secret_bits,
            "Decision": dec["status"],
            "What happens": explain_level(level, mode, qkd),
        })
    return rows
