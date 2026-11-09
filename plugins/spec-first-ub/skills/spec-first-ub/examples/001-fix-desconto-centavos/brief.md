---
feature: 001-fix-desconto-centavos
status: draft
risk: small
track: fix
---

# Brief — Desconto percentual perde centavos

## Problema

Em pedidos com desconto percentual, o valor do desconto é truncado em vez de arredondado. Exemplo: item de R$ 19,99 com cupom de 15% gera desconto de R$ 2,99 (esperado R$ 3,00, pois 19,99 × 0,15 = 2,9985) e o total sai R$ 17,00 em vez de R$ 16,99. Causa provável: conversão para centavos com truncamento em `calcularDesconto`.

## Comportamento esperado

- **REQ-001:** O desconto percentual deve ser arredondado para o centavo mais próximo (metade para cima).
- **AC-001** (REQ-001): Dado um item de R$ 19,99 e cupom de 15%, quando o total é calculado, então o desconto é R$ 3,00 e o total é R$ 16,99.

## Abordagem e fora de escopo

Trocar o truncamento por arredondamento no ponto único onde o desconto é calculado. Não alterar regras de cupom, impostos nem o formato da API.

## Tasks

- [ ] **TASK-001** [REQ-001] [AC-001] Arredondar o desconto percentual ao centavo
  - RED: teste com R$ 19,99 e 15% falha, retornando desconto 2,99.
  - GREEN: arredondar com HALF_UP ao converter para centavos.
  - REFACTOR: nenhuma, a função já tem um único ponto de cálculo.

## Aprovação

- Evidência: pendente.

## Verificação

| Critério | Comando executado | Resultado |
|---|---|---|
| AC-001 | suíte do módulo de pedidos | NOT_RUN |

Gates obrigatórios no fix, sobre o código alterado (`calcularDesconto`):

| Gate | Ferramenta | Status | Evidência |
|---|---|---|---|
| Testes | suíte do módulo de pedidos | NOT_MEASURED | pendente |
| Lint/compilação | linter do projeto | NOT_MEASURED | pendente |
| Revisão | checklist de quality-gates.md | NOT_MEASURED | pendente |

Log: nenhuma ação executada ainda.
