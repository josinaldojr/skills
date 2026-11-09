---
description: spec-first-ub ARCHIVE — arquiva a spec de uma mudança concluída (CONVERGED) em specs/archive/
argument-hint: [slug da spec, opcional]
---

Use a skill `spec-first-ub` na ação **archive** para: $ARGUMENTS

Regras desta ação:
- Só arquive mudança revisada e finalizada: rode antes `scripts/check_spec.py --gate verify` da skill. Se não for `PASS`, pare e diga o que falta (volte ao `/spec-apply`).
- Mostre o destino com `scripts/archive_spec.py specs/<slug> --dry-run` e então mova com `scripts/archive_spec.py specs/<slug>`; copie a linha `ARCHIVE: ...` como evidência.
- Não apague nada, não sobrescreva arquivamento existente e não faça commit, push ou merge sem minha autorização explícita.
