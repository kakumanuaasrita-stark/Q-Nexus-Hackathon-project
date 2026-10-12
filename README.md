# Q-Nexus

Q-Nexus is a prototype that demonstrates **quantum-secured voice communication**.
Aasrita's voice is encrypted with a key produced by BB84 quantum key distribution.
If an eavesdropper or channel noise disturbs the qubits, the error rate rises and
the system warns or blocks the transmission.

> **Simulation only.** All quantum behaviour is simulated on a normal computer
> (Qiskit Aer, or a built-in NumPy model). No photons or quantum hardware are used,
> and the cipher is a demo cipher, not a production one.

## How it works

1. **Entanglement check** – Bell pairs are prepared and measured; the share of
   matching results (`00` / `11`) shows whether the channel is healthy.
2. **BB84 key exchange** – Aasrita sends random bits in random bases, Bhavya measures
   in random bases, and they keep only the positions where the bases match.
3. **QBER** – 30% of the kept bits are revealed publicly to measure the quantum
   bit error rate.
4. **Decision**

   | QBER | Decision | What happens |
   |---|---|---|
   | ≤ 0.5% | SECURE | Voice is sent encrypted |
   | 0.5% – 11% | WARNING | Key is shortened (privacy amplification), voice is still sent |
   | ≥ 11%, or fewer than 128 secret bits left | COMPROMISED | Key discarded, voice blocked |

5. **Voice** – the audio is encrypted with the quantum-derived key and sent over
   the classical channel. Bhavya verifies an integrity tag and decrypts it.

Two kinds of disturbance can be simulated: an **eavesdropper** (Eve intercepts
and re-sends qubits) and **channel noise** (qubits are depolarised).

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit app: an eight-slide walkthrough of the whole flow |
| `qnexus_core.py` | The engine: Bell check, BB84, decision, voice encryption (no UI code) |
| `main.py` | Command-line demo: runs every disturbance level |
| `selftest.py` | Quick check that everything works on your machine |
| `run.bat` | Double-click launcher for the Streamlit app (Windows) |
| `requirements.txt` | Python packages |

## Setup

Python 3.9 or newer is required.

```bat
python -m pip install -r requirements.txt
```

Qiskit is optional: if it is missing or fails its self-check, the built-in NumPy
simulator is used automatically.

## Run

**The app**

```bat
streamlit run app.py
```

or double-click `run.bat`. Then follow the slides:

1. **Setup** – disturbance level and type, engine, qubit count, random seed
2. **Aasrita** – record with the microphone, upload a WAV file, or use the demo sound
3. **Secure channel** – press **Send through Q-Nexus**
4. **Detection** – the security decision and channel metrics
5. **BB84** – the first qubits of the key exchange, one row each
6. **QBER** – the error rate against the alert and abort limits
7. **Bhavya** – the decrypted voice (or nothing, if the channel was compromised)
8. **Eve** – what an eavesdropper hears, compared with an unprotected channel

If you change the settings or the audio after sending, press **Send** again on
Slide 3; the later slides tell you when their results are out of date.

**The command-line demo**

```bat
python main.py
python main.py --audio "C:\path\to\voice.wav" --mode noise
```

It prints one row per disturbance level and saves what Bhavya receives to
`results\Bhavya_XXX.wav`. Run `python main.py --help` for all options.

**The self-test**

```bat
python selftest.py
```

It should end with `RESULT: ALL TESTS PASSED`.

## Audio input

WAV files only. Stereo is converted to mono, the audio is resampled to 16 kHz,
and anything longer than 15 seconds is cut off.

## What is simplified

- Error reconciliation is not implemented: Bhavya's key is set equal to Aasrita's
  (real systems use Cascade or LDPC codes).
- The cipher is a SHAKE-256 keystream with an HMAC tag. Use AES-256 or a
  one-time pad in a real system.
- The secret-key fraction uses the asymptotic formula `1 − 2·h2(QBER)`, without
  finite-size corrections.
