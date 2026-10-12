"""
Q-NEXUS command-line demo (no browser needed).
Run:   python main.py                              (built-in demo sound)
       python main.py --audio voice.wav --mode noise

Runs every disturbance level and saves what Bhavya receives to the results folder.
"""
import argparse
from pathlib import Path

import qnexus_core as qc


def run(audio_path=None, mode=qc.MODE_EVE, engine="qiskit", n_qubits=qc.DEFAULT_QUBITS, seed=7, out_dir="results"):
    """Run the complete Q-Nexus demonstration at every disturbance level."""
    backend, msg = qc.get_backend(engine)
    audio = qc.load_voice(Path(audio_path).read_bytes()) if audio_path else qc.synthetic_voice()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("Q-NEXUS | QUANTUM SECURE VOICE DEMO (SIMULATION)")
    print("=" * 78)
    print(f"Engine      : {backend.name}  ({msg})")
    print(f"Input audio : {audio_path or 'built-in demo sound'}  ({len(audio) / qc.SAMPLE_RATE:.2f} s)")
    print(f"Disturbance : {qc.MODE_LABELS[mode]}")
    print()
    print(f"{'Level':>6} {'Bell%':>7} {'QBER%':>7} {'Key%':>6} {'Bits':>5}  {'Decision':<12} Bhavya receives")

    for level in qc.LEVELS:
        bell = qc.run_bell(backend, level, mode, seed=seed + level)
        qkd = qc.run_qkd(backend, level, mode, n_qubits, seed=seed + level)
        decision = qc.final_decision(bell, qkd)
        voice = qc.transmit_voice(audio, qkd, decision)
        if voice.sent and voice.verified:
            path = out / f"Bhavya_{level:03d}.wav"
            path.write_bytes(qc.wav_bytes(voice.Bhavya_audio))
            received = str(path)
        else:
            received = "nothing (transmission blocked)"
        print(f"{level:>5}% {bell.correlation:>7.1f} {qkd.qber:>7.2f} {qkd.secret_frac * 100:>6.1f} "
              f"{qkd.n_secret_bits:>5}  {decision['status']:<12} {received}")

    print()
    print(f"Demo complete. Open the WAV files in the {out} folder.")
    print("=" * 78)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Q-Nexus quantum secure voice demonstration (simulation)")
    parser.add_argument("--audio", default=None, help="Path to a WAV file (default: built-in demo sound)")
    parser.add_argument("--mode", choices=[qc.MODE_EVE, qc.MODE_NOISE], default=qc.MODE_EVE,
                        help="Type of disturbance (default: eve)")
    parser.add_argument("--engine", choices=["qiskit", "builtin"], default="qiskit",
                        help="Quantum engine (default: qiskit, falls back to builtin)")
    parser.add_argument("--qubits", type=int, default=qc.DEFAULT_QUBITS, help="Qubits sent in BB84")
    parser.add_argument("--seed", type=int, default=7, help="Random seed (same seed = same result)")
    parser.add_argument("--out", default="results", help="Folder for Bhavya's received audio")
    args = parser.parse_args()

    try:
        run(args.audio, args.mode, args.engine, args.qubits, args.seed, args.out)
    except FileNotFoundError as exc:
        print(f"\nERROR: {exc}")
        print("Tip: check the path given to --audio, or leave it out to use the demo sound.")
    except ValueError as exc:
        print(f"\nERROR: could not read the WAV file: {exc}")
