---
description: spec-first-ub PROPOSE — dimensiona a trilha e gera spec, plan e tasks (ou brief) e para para aprovação
argument-hint: <slug-ou-descrição da mudança>
---

Use a skill `spec-first-ub` na ação **propose** para: $ARGUMENTS

Regras desta ação:
- Dimensione a trilha (trivial, fix, standard, high) e informe a escolha em uma linha.
- Gere de uma vez os artefatos da trilha (SPEC → PLAN → TASKS → ANALYZE, ou `brief.md` no fix).
- Rode `scripts/check_spec.py --gate propose` quando houver artefatos em disco.
- Não escreva código de produção. Termine em `READY FOR REVIEW` e **pare**: não marque nada como `approved` por conta própria.
