---
feature: 002-exportar-pedidos-csv
status: draft
---

# Plan — Exportar pedidos em CSV por período

## Abordagem

Reaproveitar a consulta da listagem, com os mesmos filtros e permissões, e escrever o resultado em streaming como CSV. Job assíncrono foi descartado: 50 mil linhas cabem numa resposta em streaming; reavaliar se o volume crescer.

## Domínio e contratos

Um tipo de período valida início ≤ fim e no máximo 366 dias na borda. A permissão é aplicada na consulta, não depois de carregar os dados. É um endpoint novo de leitura; a listagem não muda. As colunas do CSV ficam fixadas na TASK-002, e mudá-las depois é alteração de contrato.

## Testes

Testes de comportamento no endpoint: período, permissão, erro 400 e escape de campos, mais um com volume grande para o streaming. Usar a suíte e o lint já existentes.

## Riscos e rollback

Vazamento entre lojas, mitigado reutilizando a consulta com permissão e coberto por AC-002. Rollback: remover a rota.

## Decisões

- DEC-001: Streaming síncrono reutilizando a consulta da listagem; atende REQ-001 e REQ-002.
- DEC-002: Validar o período em tipo próprio na borda; atende REQ-003.

## Revisão

- Aprovador: responsável técnico.
- Evidência de aprovação: pendente.
