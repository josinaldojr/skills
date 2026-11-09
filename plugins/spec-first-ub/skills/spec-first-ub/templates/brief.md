---
feature: <slug-do-fix>
status: draft
risk: small
track: fix
---

# Brief — <nome do fix>

<Trilha fix: um único arquivo substitui spec, plan, tasks e verification. Use quando a mudança é pequena, local e sem impacto em contrato, dados, segurança ou concorrência. Se algo disso aparecer, escale para spec/plan/tasks.>

## Problema

<Comportamento observado x esperado. Para bug: passos de reprodução e causa provável.>

## Comportamento esperado

- **REQ-001:** <O que deve passar a valer, em uma frase.>
- **AC-001** (REQ-001): Dado <contexto>, quando <evento>, então <resultado observável>.

## Abordagem e fora de escopo

<Menor mudança que resolve a causa. O que não será tocado.>

## Tasks

- [ ] **TASK-001** [REQ-001] [AC-001] <Resultado verificável>
  - RED: <teste que reproduz e motivo esperado da falha>
  - GREEN: <menor mudança>
  - REFACTOR: <limpeza opcional, ou "nenhuma">

## Aprovação

- Evidência: <mensagem do usuário aprovando o brief; só preencher após a aprovação>

## Verificação

| Critério | Comando executado | Resultado |
|---|---|---|
| AC-001 | <comando> | NOT_RUN |

Gates obrigatórios no fix, sobre o código alterado (`PASS`, `FAIL`, `NOT_MEASURED` ou `WAIVED` com aprovação do usuário). CRAP, duplicação e mutação são opcionais aqui: adicione linhas se medir, e elas não podem estar em `FAIL`.

| Gate | Ferramenta | Status | Evidência |
|---|---|---|---|
| Testes | <comando> | NOT_MEASURED | <saída resumida> |
| Lint/compilação | <comando> | NOT_MEASURED | <saída resumida> |
| Revisão | checklist de quality-gates.md | NOT_MEASURED | <itens marcados> |

Log: <ações e motivos, uma linha cada>
