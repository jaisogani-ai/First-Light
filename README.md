# Proof-Carrying Commands (PCC) for NASA core Flight Software (cFS)
## Pre-Execution Safety Verification for Spacecraft Autonomy

**Track:** Aerotech & Aerospace Innovation  
**Event:** International Innovation Challenge 3.0 (IIC 3.0), Manipal University Jaipur  

---

## 🚀 Executive Overview

As space agencies and commercial constellations adopt AI mission planning agents to manage multi-satellite constellations, the time between **command generation** and **spacecraft execution** is shrinking to near zero human review time.

Traditional safety systems rely on **reactive runtime monitors** (R2U2) or **ground-side rule engines** (JPL RP-check). **Proof-Carrying Commands (PCC)** flips the paradigm:
- **Ground / Producer:** Offloads heavy SMT/Z3 solving to derive a mathematical **Farkas Linear Infeasibility Certificate** proving post-maneuver state safety.
- **Spacecraft / NASA cFS Verifier:** Executes a deterministic, 5-step C linear arithmetic check on the cFS Software Bus in **< 2.1 milliseconds** with zero search loops and zero dynamic memory allocation.

---

## 📁 Repository Structure

```
.
├── apps/
│   ├── gate/              # NASA cFS Gate Application (5-step verifier, MID capture & republish)
│   │   └── fsw/src/
│   │       ├── gate_app.h
│   │       ├── gate_app.c
│   │       └── gate_verify.c
│   └── target/            # NASA cFS Target App ("Thruster Control")
│       └── fsw/src/
│           └── target_app.c
├── producer/             # Python Ground Station AI & Z3 SMT Certificate Generator
│   ├── agent.py
│   ├── dynamics_model.py
│   └── certificate.py
├── schema/
│   └── proof-term.schema.json   # JSON Schema v1.1 for proof-term serialization
├── eval/                  # Comprehensive Evaluation & Adversarial Test Suite
│   ├── test_positive.py
│   ├── test_adversarial_mismatch.py
│   ├── test_adversarial_forged.py
│   ├── test_replay.py
│   └── test_boot_order.py
├── docs/
│   └── SAFETY_DISCLAIMER.md
├── index.html             # Glassmorphism Mission Control Dashboard
├── styles.css
├── app.js
├── README.md
└── LICENSE
```

---

## 🛠️ Quick Start & Execution Guide

### 1. Run the Evaluation Test Suite
Execute the full automated test suite covering positive verification, command hash mismatch, forged signature, replay attack, and startup boot order:

```bash
python3 -m unittest discover -s eval
```

### 2. Launch the Mission Control Live Dashboard
Simply open `index.html` in your web browser:

```bash
open index.html
```

Or start a local HTTP server:
```bash
python3 -m http.server 8000
```
Then navigate to `http://localhost:8000` in your web browser.

---

## 🛡️ Key Safety & Security Features

1. **SHA-256 Command Hash Binding:** Prevents attaching valid proofs to arbitrary unsafe commands.
2. **Monotonic Sequence & Window Freshness:** Protects against replay attacks.
3. **Model Versioning:** Explicitly discloses dynamics model provenance (`model_id`).
4. **Boot-Order Race Protection:** `cfe_es_startup.scr` initializes `PCC_GATE_APP` before `TARGET_APP`.

---

## 📜 License

NASA cFS core components are subject to the **NASA Open Source Agreement (NOSA)**. Custom PCC gateway logic, producer engine, schema, and UI dashboard are licensed under the **Apache 2.0 License**.
