"""
Quick check that everything works on your laptop (no browser needed).
Run:  python selftest.py
"""
import numpy as np
import qnexus_core as qc

backend, msg = qc.get_backend("qiskit")
print("Engine :", backend.name)
print("Message:", msg, "\n")

failures = 0
for mode in (qc.MODE_EVE, qc.MODE_NOISE):
    print("=" * 78)
    print("Disturbance type:", qc.MODE_LABELS[mode])
    print("=" * 78)
    print(f"{'Level':>6} {'Bell%':>7} {'QBER%':>7} {'Key%':>6} {'Bits':>5}  Decision")
    for r in qc.run_all_levels(backend, mode):
        print(f"{r['Level (%)']:>5}% {r['Bell correlation (%)']:>7} {r['QBER (%)']:>7} "
              f"{r['Secret key (%)']:>6} {r['Secret bits']:>5}  {r['Decision']}")
    print()

print("Voice round-trip test (10% eavesdropper)...")
audio = qc.synthetic_voice()
bell = qc.run_bell(backend, 10, qc.MODE_EVE)
qkd = qc.run_qkd(backend, 10, qc.MODE_EVE)
dec = qc.final_decision(bell, qkd)
voice = qc.transmit_voice(audio, qkd, dec)
same = voice.sent and voice.verified and np.allclose(voice.Bhavya_audio, qc.to_pcm16(audio) / 32768.0, atol=1e-4)
print("  Bhavya receives Aasrita's exact voice :", "PASS" if same else "FAIL")
failures += 0 if same else 1
print("  Eve's key differs from the real key:", "PASS" if qkd.eve_key != qkd.session_key else "FAIL")
failures += 0 if qkd.eve_key != qkd.session_key else 1

blocked_q = qc.run_qkd(backend, 100, qc.MODE_EVE)
blocked_d = qc.final_decision(qc.run_bell(backend, 100, qc.MODE_EVE), blocked_q)
blocked = not qc.transmit_voice(audio, blocked_q, blocked_d).sent
print("  100% disturbance blocks the voice  :", "PASS" if blocked else "FAIL")
failures += 0 if blocked else 1

print("\nRESULT:", "ALL TESTS PASSED" if failures == 0 else f"{failures} TEST(S) FAILED")
