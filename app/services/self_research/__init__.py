"""
CipherResearch — Autonomous Self-Improvement Engine

Inspired by Karpathy's autoresearch, adapted for Cipher's multi-agent system.
Instead of optimizing val_bpb on a neural net training script, Cipher optimizes
its own agents, prompts, and capabilities against a self-test suite.

The Loop:
  1. Read research_program.md for operator directives
  2. Pick an experiment (improve agent, fix bug, add capability)
  3. Snapshot current state (git-like versioning)
  4. Apply the modification
  5. Run self-tests to measure impact
  6. Keep (commit) if improved, discard (rollback) if not
  7. Log everything
  8. Repeat until stopped

Like autoresearch, once started, the loop runs autonomously.
The operator may be asleep. Don't ask. Just iterate.
"""
