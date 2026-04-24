---
title: "Runtime Security"
slug: runtime
category: security
tags: [runtime-security, seccomp, apparmor, container-hardening, linux-security]
search_keywords: [runtime security, container runtime security, seccomp, apparmor, linux security module, syscall filtering, container hardening]
parent: security/_index
related: [containers/container-runtime/sandboxing-avanzato, security/supply-chain/admission-control]
status: complete
difficulty: advanced
last_updated: 2026-03-25
---

# Runtime Security

La **runtime security** comprende i meccanismi di hardening che operano a livello di kernel Linux durante l'esecuzione dei container. A differenza dell'admission control (che agisce al deploy), la runtime security limita ciò che un container può fare anche se è già in esecuzione.

## Argomenti

<div class="grid cards" markdown>

- **[seccomp e AppArmor](seccomp-apparmor.md)** — Syscall filtering (seccomp) e Mandatory Access Control (AppArmor): i due meccanismi fondamentali di sandboxing a runtime per container Linux.

- **[Falco](falco.md)** — Runtime threat detection: intercetta system call via eBPF e valuta regole in tempo reale per rilevare comportamenti anomali in container e pod Kubernetes.

</div>
