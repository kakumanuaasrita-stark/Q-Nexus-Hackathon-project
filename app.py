"""
Q-NEXUS  -  Quantum Secure Voice Communication (SIMULATION PROTOTYPE)
Run with:   streamlit run app.py
"""
import hashlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import qnexus_core as qc

st.set_page_config(page_title="Q-Nexus | Quantum Secure Voice", page_icon="🔐", layout="wide")

COLORS = {"ok": "#16a34a", "warn": "#d9b206", "bad": "#dc2626", "idle": "#64748b"}
STATUS_STATE = {"SECURE": "ok", "GOOD": "ok", "WARNING": "warn", "COMPROMISED": "bad", "CRITICAL": "bad"}
STATUS_EMOJI = {"SECURE": "🟢", "WARNING": "🟠", "COMPROMISED": "🔴"}

st.markdown(
    """
<style>
.block-container {padding-top: 1.2rem;}
.hero {background: linear-gradient(120deg,#0f172a,#1e3a8a 60%,#6d28d9); color:#fff; padding:18px 24px;
       border-radius:14px; margin-bottom:10px;}
.hero h1 {margin:0; font-size:2rem;} .hero p {margin:4px 0 0 0; opacity:.9;}
.sim-note {background:#fef3c7; color:#78350f; padding:8px 14px; border-radius:8px; font-size:.9rem; margin-bottom:10px;}
.flow {display:flex; flex-wrap:wrap; align-items:stretch; gap:6px; margin:8px 0 14px 0;}
.node {flex:1 1 112px; min-width:104px; border-radius:10px; padding:8px 6px; text-align:center; color:#fff;
       font-size:.78rem; line-height:1.25;}
.node b {display:block; font-size:.86rem;} .node span {opacity:.92;}
.arrow {align-self:center; color:#94a3b8; font-size:1.1rem;}
.banner {padding:14px 18px; border-radius:12px; color:#fff; margin:6px 0 12px 0;}
.banner h3 {margin:0; color:#fff;} .banner p {margin:4px 0 0 0;}
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Starting the quantum simulator...")
def load_backend(pref):
    return qc.get_backend(pref)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def qber_chart(qber):
    fig, ax = plt.subplots(figsize=(4.2, 2.6))
    color = COLORS["ok"] if qber <= qc.QBER_ALERT else (COLORS["warn"] if qber < qc.QBER_ABORT else COLORS["bad"])
    ax.bar(["This run"], [qber], color=color, width=0.4)
    ax.axhline(qc.QBER_ALERT, color="#16a34a", ls="--", lw=1)
    ax.axhline(qc.QBER_ABORT, color="#dc2626", ls="--", lw=1)
    ax.text(0.42, qc.QBER_ALERT, " alert 0.5%", va="bottom", fontsize=7, color="#16a34a")
    ax.text(0.42, qc.QBER_ABORT, " abort 11%", va="bottom", fontsize=7, color="#dc2626")
    ax.set_ylim(0, max(30, qber + 5))
    ax.set_xlim(-0.5, 1.2)
    ax.set_ylabel("QBER (%)")
    ax.set_title("Quantum Bit Error Rate", fontsize=9)
    fig.tight_layout()
    return fig


def fingerprint(key):
    return hashlib.sha256(key).hexdigest()[:12] if key else "-"


def qubit_table(qkd, n=14):
    names = {0: "Z", 1: "X"}
    rows = []
    for i in range(n):
        match = qkd.a_bases[i] == qkd.b_bases[i]
        row = {"#": i + 1, "Aasrita bit": int(qkd.a_bits[i]), "Aasrita basis": names[int(qkd.a_bases[i])],
               "Bhavya basis": names[int(qkd.b_bases[i])], "Bhavya result": int(qkd.Bhavya_bits[i]),
               "Bases match?": "yes" if match else "no (discard)"}
        if qkd.mode == qc.MODE_EVE:
            row["Eve intercepted?"] = "yes" if qkd.eve_mask[i] else "no"
        row["Error?"] = ("ERROR" if qkd.a_bits[i] != qkd.Bhavya_bits[i] else "ok") if match else "-"
        rows.append(row)
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# ============================ EIGHT-SLIDE DEMONSTRATION ============================

SLIDE_COUNT = 8


def run_simulation(audio, backend, level, mode, engine_pref, n_qubits, seed):
    bell = qc.run_bell(backend, level, mode, seed=seed + level)
    qkd = qc.run_qkd(backend, level, mode, n_qubits, seed=seed + level)
    decision = qc.final_decision(bell, qkd)
    voice = qc.transmit_voice(audio, qkd, decision)
    return {
        "level": level,
        "mode": mode,
        "engine_pref": engine_pref,
        "n_qubits": n_qubits,
        "seed": seed,
        "bell": bell,
        "qkd": qkd,
        "decision": decision,
        "voice": voice,
        "original": audio,
        "engine": backend.name,
    }


def slide_header(number, title, subtitle):
    st.markdown(
        f"""
        <div class="hero" style="padding:16px 20px; margin-bottom:10px;">
            <h1 style="font-size:1.7rem; margin:0;">Slide {number} of {SLIDE_COUNT}</h1>
            <p style="margin:3px 0 0 0; font-size:1.15rem;">{title}</p>
            <p style="margin:2px 0 0 0; opacity:.9;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def navigation():
    slide = st.session_state.slide
    nav_cols = st.columns(8)
    labels = ["Setup", "Aasrita", "Secure channel", "Detection", "BB84", "QBER", "Bhavya", "Eve"]
    for i, col in enumerate(nav_cols):
        with col:
            if st.button(f"S{i + 1} · {labels[i]}", key=f"slide{i}", use_container_width=True):
                st.session_state.slide = i
                st.rerun()
    prev_col, next_col = st.columns(2)
    with prev_col:
        if st.button("← Previous", use_container_width=True, disabled=slide == 0):
            st.session_state.slide = max(0, slide - 1)
            st.rerun()
    with next_col:
        if st.button("Next →", use_container_width=True, disabled=slide == SLIDE_COUNT - 1):
            st.session_state.slide = min(SLIDE_COUNT - 1, slide + 1)
            st.rerun()
    return st.session_state.slide


def stale_notice(run):
    """Warn when the setup or Aasrita's audio no longer matches the run being displayed."""
    state = st.session_state
    changed = ((run["level"], run["mode"], run["engine_pref"], run["n_qubits"], run["seed"])
               != (state.level, state.mode, state.engine_pref, state.n_qubits, state.seed))
    audio = state.get("audio")
    if not changed and audio is not None:
        changed = not np.array_equal(audio, run["original"])
    if changed:
        st.warning(
            f"The setup or Aasrita's audio has changed since this run. These results are from the earlier run "
            f"({run['level']}% disturbance, {qc.MODE_LABELS[run['mode']].lower()}). "
            f"Press Send on Slide 3 to refresh them."
        )


def render_slide_1(level, mode, engine_pref, n_qubits, seed):
    slide_header(1, "Set the quantum channel", "Choose the disturbance, engine, qubit count, and reproducible random seed.")
    c1, c2, c3 = st.columns([1.2, 1.1, 1.1])
    with c1:
        st.markdown("### Disturbance controls")
        level = st.slider("Disturbance level (%)", min_value=0, max_value=100, value=level, step=5,
                           help="0% is clean; 100% creates maximum simulated disturbance.")
        mode = st.radio("Type of disturbance", [qc.MODE_EVE, qc.MODE_NOISE],
                         index=0 if mode == qc.MODE_EVE else 1,
                         format_func=lambda value: qc.MODE_LABELS[value])
        st.caption("Eve intercepts qubits; channel noise disturbs qubits without an eavesdropper.")
    with c2:
        st.markdown("### Quantum engine")
        engine_pref = st.radio("Quantum engine", ["qiskit", "builtin"],
                                index=0 if engine_pref == "qiskit" else 1,
                                format_func=lambda value: "Qiskit Aer (recommended)" if value == "qiskit" else "Built-in NumPy simulator")
        backend, backend_msg = load_backend(engine_pref)
        st.caption(f"Active engine: **{backend.name}**")
        if "not usable" in backend_msg:
            st.warning(backend_msg)
    with c3:
        st.markdown("### BB84 setup")
        n_qubits = st.slider("Qubits sent in BB84", min_value=1000, max_value=8000, value=n_qubits, step=1000,
                             help="More qubits create a larger key and a more stable QBER estimate.")
        seed = st.number_input("Random seed", min_value=0, max_value=999999, value=seed, step=1,
                               help="The same seed reproduces the same quantum results.")
        st.markdown(f"**Current setup:** {n_qubits:,} qubits · {level}% disturbance · {qc.MODE_LABELS[mode]}")
    st.session_state.level = level
    st.session_state.mode = mode
    st.session_state.engine_pref = engine_pref
    st.session_state.n_qubits = n_qubits
    st.session_state.seed = int(seed)
    st.info("These settings are saved for the complete eight-slide run. Press Next to begin the audio flow.")


def render_slide_2(audio_source, previous_audio):
    slide_header(2, "Aasrita chooses how to send the voice", "There are three ways to provide Aasrita's audio.")
    source = st.radio("Aasrita's audio source", ["record", "upload", "demo"],
                       index={"record": 0, "upload": 1, "demo": 2}[audio_source],
                       format_func=lambda value: {
                           "record": "🎙️ Record with microphone",
                           "upload": "⬆️ Upload a WAV file",
                           "demo": "🎵 Use built-in demo sound",
                       }[value], horizontal=True)
    audio = None
    if source == "record":
        if hasattr(st, "audio_input"):
            recording = st.audio_input("Record a short voice message", key="Aasrita_recording")
            if recording is not None:
                try:
                    audio = qc.load_voice(recording.getvalue())
                except Exception as exc:
                    st.error(f"Could not read the recording: {exc}")
        else:
            st.warning("Microphone recording is unavailable in this Streamlit version. Use upload or demo.")
    elif source == "upload":
        uploaded = st.file_uploader("Choose a WAV file", type=["wav"], key="Aasrita_upload")
        if uploaded is not None:
            try:
                audio = qc.load_voice(uploaded.getvalue())
            except Exception as exc:
                st.error(f"Could not read that WAV file: {exc}")
    else:
        audio = qc.synthetic_voice()
    if audio is None and source == audio_source:
        audio = previous_audio                      # keep the recording/file when returning to this slide
    if audio is not None and len(audio) > 0:
        st.success(f"Aasrita's voice is ready: {len(audio) / qc.SAMPLE_RATE:.2f} seconds, {len(audio):,} samples.")
        st.audio(qc.wav_bytes(audio), format="audio/wav")
    else:
        st.warning("Choose a recording or file before continuing.")
    st.session_state.audio_source = source
    st.session_state.audio = audio


def render_slide_3(run, backend, level, mode, engine_pref, n_qubits, seed, audio):
    slide_header(3, "Send Aasrita's voice through the quantum-secure channel",
                 "The quantum key protects the audio while the classical channel carries encrypted data.")
    if audio is None or len(audio) == 0:
        st.warning("Aasrita's audio is missing. Return to Slide 2 and choose a valid source.")
    else:
        st.markdown(
            """
            <div class="flow" style="margin-bottom:12px;">
            <div class="node" style="background:#2563eb"><b>👩 Aasrita</b><span>Voice input</span></div>
            <div class="arrow">➜</div>
            <div class="node" style="background:#7c3aed"><b>🔗 Quantum channel</b><span>Bell + BB84</span></div>
            <div class="arrow">➜</div>
            <div class="node" style="background:#059669"><b>🔑 Quantum key</b><span>Privacy amplified</span></div>
            <div class="arrow">➜</div>
            <div class="node" style="background:#0f766e"><b>📡 Encrypted voice</b><span>Classical line</span></div>
            <div class="arrow">➜</div>
            <div class="node" style="background:#475569"><b>👨 Bhavya</b><span>Decrypts + verifies</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info(f"Using {backend.name}, {n_qubits:,} BB84 qubits, {level}% disturbance, and {qc.MODE_LABELS[mode].lower()}.")
        if st.button("🚀 Send through Q-Nexus", type="primary", use_container_width=True):
            with st.spinner("Running Bell-state check, BB84 exchange, QBER analysis, and encryption..."):
                result = run_simulation(audio, backend, level, mode, engine_pref, n_qubits, seed)
            st.session_state.run = result
            st.rerun()
        if run is not None:
            stale_notice(run)
            st.success(f"Last run: {run['decision']['status']} · {run['qkd'].n_secret_bits:,} secret bits")
            st.caption("The result is stored in this session and remains available on later slides.")


def render_slide_4(run):
    slide_header(4, "Disturbance detection and channel security",
                 "Compare Bell correlation, BB84 QBER, secret-key fraction, and the selected engine.")
    if run is None:
        st.info("Run the secure-channel step first to display the channel metrics.")
        return
    stale_notice(run)
    bell = run["bell"]
    qkd = run["qkd"]
    decision = run["decision"]
    status_color = COLORS[STATUS_STATE[decision["status"]]]
    st.markdown(
        f'<div class="banner" style="background:{status_color}; border-radius:14px; padding:18px; color:white;">'
        f'<h3 style="margin:0 0 5px 0;">{STATUS_EMOJI[decision["status"]]} {decision["title"]}</h3>'
        f'<p style="margin:0;">{decision["action"]}</p></div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Entanglement (Bell) correlation", f"{bell.correlation:.1f}%", f"{bell.status} status")
    with c2:
        st.metric("QBER (BB84)", f"{qkd.qber:.2f}%", f"Alert {qc.QBER_ALERT:.1f}% · abort {qc.QBER_ABORT:.1f}%")
    with c3:
        st.metric("Secret-key fraction", f"{qkd.secret_frac * 100:.1f}%", f"{qkd.n_secret_bits:,} secret bits")
    with c4:
        st.metric("Engine", "Qiskit" if "Qiskit" in run["engine"] else "NumPy", run["engine"])
    st.warning(qkd.reason)
    st.caption(f"Disturbance mode: {qc.MODE_LABELS[run['mode']]} · level: {run['level']}% · engine: {run['engine']}")


def render_slide_5(run):
    slide_header(5, "BB84 key exchange", "Aasrita and Bhavya compare bases, sift matching qubits, and keep the surviving key.")
    if run is None:
        st.info("Run the secure-channel step first to display the BB84 key table.")
        return
    stale_notice(run)
    qkd = run["qkd"]
    st.markdown(
        f"Aasrita sent **{qkd.n_qubits:,} qubits**. Basis matching produced **{qkd.n_sifted:,} sifted qubits**, "
        f"**{qkd.n_test:,} test qubits**, and **{len(qkd.key_idx):,} raw key bits**."
    )
    st.dataframe(qubit_table(qkd), hide_index=True, use_container_width=True)
    st.caption("Only matching bases are kept. A mismatch or recorded error is treated as disturbance.")


def render_slide_6(run):
    slide_header(6, "QBER analysis", "The error rate reveals whether the quantum channel has been disturbed.")
    if run is None:
        st.info("Run the secure-channel step first to display the QBER chart.")
        return
    stale_notice(run)
    qkd = run["qkd"]
    fig = qber_chart(qkd.qber)
    st.pyplot(fig)
    plt.close(fig)
    st.markdown(
        f"**Measured QBER:** {qkd.qber:.2f}%  ·  **Alert:** {qc.QBER_ALERT:.1f}%  ·  "
        f"**Abort limit:** {qc.QBER_ABORT:.1f}%"
    )
    st.caption("QBER is calculated from the publicly revealed test subset. A higher QBER means more errors, often caused by noise or an eavesdropper.")


def render_slide_7(run):
    slide_header(7, "Bhavya's side", "Bhavya receives the encrypted voice, verifies its integrity, and decrypts it.")
    if run is None:
        st.info("Run the secure-channel step first to display Bhavya's result.")
        return
    stale_notice(run)
    voice = run["voice"]
    qkd = run["qkd"]
    if voice.sent and voice.verified:
        st.success(f"✅ {voice.note}")
        st.markdown(f"Session-key fingerprint: `{fingerprint(qkd.session_key)}`")
        st.caption(f"Encrypted payload: {voice.cipher_bytes:,} bytes on the classical channel.")
        st.audio(qc.wav_bytes(voice.Bhavya_audio), format="audio/wav")
        st.caption("This is Aasrita's recovered voice received by Bhavya after decryption.")
    else:
        st.error(f"⛔ {voice.note}")
        st.caption("For comparison, this is the same voice on a plain unprotected channel at this disturbance level.")
        st.audio(qc.wav_bytes(qc.classical_noisy(run["original"], run["level"])), format="audio/wav")


def render_slide_8(run):
    slide_header(8, "What would an eavesdropper hear?", "Compare Eve's best attempt with the plain unprotected channel.")
    if run is None:
        st.info("Run the secure-channel step first to compare the protected and unprotected audio.")
        return
    stale_notice(run)
    voice = run["voice"]
    qkd = run["qkd"]
    st.subheader("🔒 Q-Nexus encrypted channel")
    if voice.sent:
        st.write("The classical channel carries only encrypted bytes. A listener hears static rather than Aasrita's voice.")
        st.audio(qc.wav_bytes(voice.cipher_audio), format="audio/wav")
    else:
        st.info("No encrypted payload was sent because the channel was compromised.")

    st.subheader("🕵️ Eve's best attempt")
    if voice.eve_attempt_audio is not None:
        st.write(
            f"Eve guessed the key from the measured qubits. Her key matches Aasrita's only "
            f"**{qkd.eve_match_percent:.0f}%** of the time. Privacy amplification makes the final key different."
        )
        st.audio(qc.wav_bytes(voice.eve_attempt_audio), format="audio/wav")
    else:
        st.info("Eve's attempt is shown only when an eavesdropper mode was selected.")

    st.subheader("⚠️ Without Q-Nexus")
    st.write("A plain, unprotected channel sends Aasrita's voice directly. An eavesdropper hears the voice, and channel noise degrades it.")
    st.audio(qc.wav_bytes(qc.classical_noisy(run["original"], run["level"])), format="audio/wav")


# The controls are defined on Slide 1 and persisted for the rest of the presentation.
for name, default in {"slide": 0, "level": 0, "mode": qc.MODE_EVE, "engine_pref": "qiskit",
                      "n_qubits": qc.DEFAULT_QUBITS, "seed": 7, "audio_source": "demo"}.items():
    st.session_state.setdefault(name, default)
if "audio" not in st.session_state:
    st.session_state.audio = qc.synthetic_voice()   # matches the default "demo" source

st.markdown(
    """
    <div class="hero">
        <h1>🔐 Q-NEXUS</h1>
        <p>Quantum secure voice communication · Bell correlations · BB84 key distribution · QBER detection</p>
    </div>
    <div class="sim-note">This is a <b>simulation / prototype</b>: quantum behaviour is simulated on a normal computer
    using Qiskit Aer or the built-in NumPy engine. No real photons or quantum hardware are used.</div>
    """,
    unsafe_allow_html=True,
)

slide = navigation()
state = st.session_state
run = state.get("run")
audio = state.get("audio")

if slide == 0:
    render_slide_1(state.level, state.mode, state.engine_pref, state.n_qubits, state.seed)
elif slide == 1:
    render_slide_2(state.audio_source, audio)
elif slide == 2:
    backend, _ = load_backend(state.engine_pref)
    render_slide_3(run, backend, state.level, state.mode, state.engine_pref, state.n_qubits, state.seed, audio)
elif slide == 3:
    render_slide_4(run)
elif slide == 4:
    render_slide_5(run)
elif slide == 5:
    render_slide_6(run)
elif slide == 6:
    render_slide_7(run)
else:
    render_slide_8(run)

# Drawn last so it reflects any change made on Slide 1 during this rerun.
with st.sidebar:
    backend, backend_msg = load_backend(state.engine_pref)
    st.markdown("## ⚙️ Q-Nexus setup")
    st.caption(f"Engine in use: **{backend.name}**")
    if "not usable" in backend_msg:
        st.warning(backend_msg)
    st.caption(f"{state.n_qubits:,} qubits · {state.level}% disturbance · {qc.MODE_LABELS[state.mode]}")
    st.caption("Controls are configured on Slide 1 and saved for the full run.")
    st.markdown("---")
    st.caption("⚠️ Simulation only. This runs on a normal computer and is **not** a physical quantum network.")


