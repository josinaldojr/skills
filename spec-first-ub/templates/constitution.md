# Constituição de engenharia (opcional)

1. Specs antes do código; nenhuma feature sem aceites observáveis.
2. Teste de comportamento com RED-GREEN-REFACTOR por fatia quando viável.
3. Preferir simplicidade e baixo acoplamento a arquiteturas antecipatórias.
4. Domínio explícito; entrada validada nas bordas; invariantes protegidas.
5. Falhar de modo rastreável; idempotência e concorrência quando pertinentes.
6. Decisões importantes registradas no plan; tasks pequenas e rastreáveis.
7. Evidências antes de declarar conclusão; qualquer exceção deve ser visível.
8. Sem push, deploy, merge ou destruição sem autorização.
9. Processo proporcional ao risco: trilha `trivial`, `fix`, `standard` ou `high`, sem burocracia além do necessário.
10. Código alterado passa pelos gates de qualidade da trilha (testes, lint, revisão; CRAP, duplicação e mutação em `standard`/`high`).

A constituição deve refletir o projeto; adapte as regras sem contradizer o usuário.
