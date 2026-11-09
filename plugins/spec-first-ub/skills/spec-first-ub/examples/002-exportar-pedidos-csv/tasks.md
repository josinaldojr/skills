---
feature: 002-exportar-pedidos-csv
status: draft
---

# Tasks — Exportar pedidos em CSV por período

- [ ] **TASK-001** [REQ-003] [AC-003] Rejeitar períodos inválidos
  - Depende de: nenhuma
  - RED: fim antes do início e 367 dias passam sem erro.
  - GREEN: tipo de período com as regras, resposta 400.
  - REFACTOR: mensagens de erro em um ponto.
  - Evidência: testes do endpoint verdes.

- [ ] **TASK-002** [REQ-001] [AC-001] Exportar pedidos do período
  - Depende de: TASK-001
  - RED: pedidos de março e abril devolvem também os de abril.
  - GREEN: consulta por período com CSV em streaming, incluindo período vazio.
  - REFACTOR: reaproveitar a consulta da listagem sem duplicar filtros.
  - Evidência: teste do endpoint verde.

- [ ] **TASK-003** [REQ-002] [AC-002] Respeitar permissões por loja
  - Depende de: TASK-002
  - RED: usuário sem acesso à loja B recebe pedidos dela.
  - GREEN: aplicar a permissão na consulta.
  - REFACTOR: regra de permissão num único lugar, compartilhado com a listagem.
  - Evidência: teste de permissão verde.

## Revisão

- Aprovador: responsável técnico.
- Evidência de aprovação: pendente.
