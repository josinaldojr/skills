---
description: spec-first-ub APPLY — implementa as tasks aprovadas em RED/GREEN/REFACTOR, roda os gates e verifica
argument-hint: [slug da spec, opcional]
---

Use a skill `spec-first-ub` na ação **apply** para: $ARGUMENTS

Regras desta ação:
- Antes de qualquer código, confirme que os artefatos foram aprovados explicitamente por mim (`scripts/check_spec.py --gate apply`). Sem aprovação, pare e peça.
- Execute as tasks em loop RED → GREEN → REFACTOR, marcando os checkboxes; pause em bloqueios.
- Ao concluir, rode os gates da trilha e o VERIFY. Termine em `CONVERGED`, `PARTIAL` ou `BLOCKED`, com evidência real.
- Sem commit, push, merge ou deploy sem minha autorização explícita.
