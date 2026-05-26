# Compiler Backend Experiments

A collection of compiler backend implementations exploring multiple target systems while developing a **fully ISA-driven compilation model**.

---

## 🎯 Core Objective

Design of a compiler capable of:

- Translating high-level code into an intermediate representation (IR)
- Lowering IR through multiple stages (MIR → backend selection)
- Generating assembly based on a **JSON-defined ISA**
- Remaining independent of fixed architectures (x86 / ARM / etc.)

The long-term goal is a fully configurable compilation backend where instruction encoding, operand rules, and architecture constraints are fully data-driven.

---

## 🌐 WebAssembly Backend (WAT)

Initial backend implementation targeting WebAssembly Text Format (WAT) due to its simplicity and accessibility compared to LLVM.

### ✅ Implemented Features

- IR generation
- MIR lowering pipeline
- Temporary variable allocation system
- Basic ABI constraint handling
- Instruction translation layer
- Global variable handling
- Function structure generation
- WASM module emission (text format)

At this stage, the compiler was near completion, requiring mainly debugging and refinement.

---

### ⚠️ Limitations Encountered

WebAssembly introduced architectural constraints that conflicted with low-level flexibility requirements:

- Fixed memory model
- Restricted heap control
- Abstracted address handling
- Limited hardware-level expressiveness

This made WASM unsuitable for a compiler intended to generate **hardware-specific assembly from custom ISA definitions**.

---

## 🧠 LLVM Exploration

After limitations in WASM, LLVM was explored as a more flexible backend system.

---

### 🐍 Python LLVM (llvmlite)

Initial experimentation used `llvmlite`.

#### Outcome:

- Successful IR generation experiments
- Improved understanding of LLVM IR structure
- Increased complexity in mapping custom ISA behavior
- Difficulty integrating flexible instruction encoding logic

---

### 💥 C++ LLVM Attempt

A transition was made to native LLVM in C++.

#### Outcome:

- Full LLVM access and control
- Increased system complexity
- Compiler backend remained incomplete
- No stable backend pipeline achieved

---

## 🧬 Target Architecture Vision

All backend experiments were aligned toward a unified goal:

> A compiler backend capable of generating custom assembly from a JSON-defined ISA specification.

### Example ISA-driven definition:
```json
{
  "instruction": "add",
  "encoding": "rrr",
  "opcode": "0x01"
}
