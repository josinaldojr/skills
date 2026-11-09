---
feature: <slug-da-feature>
status: pending
---

# Verification — <nome da feature>

## Critérios de aceitação

| Critério | Comando executado | Resultado | Evidência |
|---|---|---|---|
| AC-001 | <comando> | NOT_RUN | <log ou arquivo> |

## Gates de qualidade (código alterado)

Status: `PASS`, `FAIL`, `NOT_MEASURED` ou `WAIVED` (só com aprovação do usuário e justificativa na evidência).

| Gate | Ferramenta | Status | Evidência |
|---|---|---|---|
| Testes | <comando> | NOT_MEASURED | <saída resumida> |
| Lint/compilação | <comando> | NOT_MEASURED | <saída resumida> |
| CRAP | <crapper ou equivalente> | NOT_MEASURED | <maior CRAP e função> |
| Duplicação | <dryer ou equivalente> | NOT_MEASURED | <pares ≥ 0,8 tratados> |
| Mutação | <mutator ou equivalente> | NOT_MEASURED | <sobreviventes e código morto> |
| Revisão | checklist de quality-gates.md | NOT_MEASURED | <itens marcados> |

## Log de ações

<Cada ação relevante e o motivo, em uma linha.>

## Riscos residuais

<"Nenhum" ou lista, sem ocultar ausência de evidência.>

## Conclusão

`PARTIAL` / `BLOCKED` / `CONVERGED` (só com evidência real de todos os aceites e os seis gates em PASS ou WAIVED).
