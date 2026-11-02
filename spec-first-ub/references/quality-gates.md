# Quality gates e exceções

## Intensidade por trilha

| Trilha | Documentação | Gates de código |
|---|---|---|
| `trivial` | Nenhuma | Só build/lint, quando houver |
| `fix` | `brief.md` | Obrigatórios: Testes, Lint/compilação e Revisão. CRAP, duplicação e mutação opcionais (sem `FAIL`) |
| `standard` | spec, plan, tasks, verification | Os seis gates, sobre o código alterado |
| `high` | Idem, com riscos e rollback | Os seis gates, mais análise de segurança nas áreas críticas |

## Portões

A tabela descreve o fluxo `standard`/`high`. No `fix`, SPEC, PLAN e TASKS colapsam nas seções do `brief.md` e CONVERGE vira a seção Verificação; os critérios de bloqueio continuam os mesmos.

| Estágio | Evidência requerida | Bloqueador |
|---|---|---|
| SPEC | REQ e AC observáveis; escopo/fora de escopo; dúvidas materiais resolvidas | Aceite não testável ou contradição |
| PLAN | Decisões coerentes com REQ, risco e stack real | Solução sem aderência ou risco material ignorado |
| TASKS | Toda REQ e AC ligada a task vertical e verificável | Requisito órfão ou tasks sem resultado |
| IMPLEMENT | Aprovação humana explícita e documentos aprovados | Ausência de autorização |
| RED | Teste falha pela razão esperada | Teste verde antes da mudança sem justificativa |
| GREEN | Teste da fatia passou | Comportamento não verificado |
| REFACTOR | Testes relevantes continuam verdes | Regressão |
| CONVERGE | Todos os AC têm evidência real, e nenhuma regressão bloqueadora | Critério sem evidência ou falhando |

## Gates de qualidade do código

Seis gates, cada um com status `PASS`, `FAIL`, `NOT_MEASURED` ou `WAIVED`. `CONVERGED` exige `PASS` ou `WAIVED` em todos os obrigatórios da trilha: os seis em `standard`/`high`; só Testes, Lint/compilação e Revisão em `fix`. Escopo: funções e arquivos alterados.

| Gate | Meta | Como medir |
|---|---|---|
| Testes | Suite pertinente verde; testes de comportamento | Comando de teste do projeto |
| Lint/compilação | Sem erro novo, nada silenciado | Compilador e linters do projeto |
| CRAP | Cada função < 10 | `crapper` ou equivalente (abaixo) |
| Duplicação | Nenhuma com similaridade ≥ 0,8 sem justificativa | `dryer` ou equivalente |
| Mutação | Cobertura do não coberto, sobreviventes mortos, código morto removido | `mutator` ou equivalente |
| Revisão | Checklist abaixo todo marcado | Leitura do diff |

**CRAP** de uma função: `comp² × (1 − cobertura)³ + comp`, com `comp` a complexidade ciclomática e `cobertura` entre 0 e 1. Reduzir dividindo a função, testando-a, ou ambos. Avaliar se vale reduzir `case`/`switch` simples.

**Scripts desta skill** (Python 3.9+, stdlib; rodar a partir da raiz do projeto, `S` = caminho de `scripts/`). Todos aceitam `--changed` (só o que o `git diff HEAD` tocou), imprimem `GATE <nome>: PASS|FAIL|NOT_MEASURED` e saem com 0/1/2.

```bash
# CRAP: precisa de cobertura (coverage json | lcov | go test -coverprofile)
python3 S/crap.py src --coverage coverage.json --changed          # limite 10 (--threshold)
# Duplicação: pares de funções com similaridade >= 0,8 (--threshold, --min-tokens)
python3 S/dry.py src --changed
# Mutação: reescreve a fonte no lugar e restaura; suite precisa estar verde antes
python3 S/mutate.py src --test-cmd "python3 -m pytest -q" --changed --max 60
```

Limitações a registrar na evidência: nenhum script usa regex. Python é analisado por `ast`/`tokenize`; JS/TS, Go e Java por um lexer próprio (strings, comentários e literais regex reconhecidos) com casamento de chaves, então complexidade e fronteiras de função são aproximadas, sem parser de gramática completa. `dry.py` compara tokens com identificadores intactos por padrão; `--normalize` compara só a estrutura (detecta clones com variáveis renomeadas). `mutate.py` muta a AST em Python (regravando com `ast.unparse`) e tokens nas demais linguagens, amostra no máximo `--max` mutantes (reprodutível por `--seed`) e, fora de Python, mutante que não compila conta como morto. Se `.mutate-backup/` existir, uma execução anterior foi interrompida: restaure a fonte a partir dele antes de rodar de novo. Cobertura aceita: coverage.py JSON, Istanbul JSON, JaCoCo XML, Cobertura XML, lcov e perfil do Go. Sem arquivo de cobertura o CRAP é `NOT_MEASURED`, nunca 0% ou 100%. Alvo inexistente também é `NOT_MEASURED`.

**Ferramentas.** Primeiro `command -v crapper dryer mutator`; depois os scripts acima. Se ainda faltar, usar equivalentes que o projeto já tenha. Exemplos, não exaustivos:

| Stack | Cobertura + complexidade (CRAP) | Duplicação | Mutação |
|---|---|---|---|
| Java | JaCoCo + PMD/Checkstyle | PMD CPD | PIT |
| JavaScript/TypeScript | c8/Istanbul + regra `complexity` do ESLint | jscpd | Stryker |
| Python | coverage + radon | jscpd | mutmut |
| Go | `go test -cover` + gocyclo | dupl | go-mutesting |

Equivalente que não mede exatamente a meta (por exemplo, duplicação textual no lugar de estrutural) vale como medição, mas a limitação vai na coluna de evidência. Não instalar ferramentas sem autorização; sem ferramenta, o gate é `NOT_MEASURED`.

**`NOT_MEASURED` não é sucesso** e bloqueia `CONVERGED`. **`WAIVED`** exige justificativa escrita e aprovação explícita do usuário para aquele gate. O agente nunca dispensa por conta própria e nunca inventa resultado.

**Checklist de revisão do código gerado**

- [ ] A causa raiz foi tratada; nenhuma guarda só esconde o erro.
- [ ] Dados externos são validados uma vez, na borda; a regra de negócio fica em função pura.
- [ ] Estados ilegais são inviáveis pelos tipos; compilador e linter não foram silenciados.
- [ ] Repetir a operação, ou retomá-la após falha no meio, termina no mesmo estado.
- [ ] Nada fora do escopo da spec mudou; sem código especulativo nem morto.
- [ ] Cada teste falharia se a função não fizesse nada; nenhum depende de detalhe interno.
- [ ] Uma decisão vive em um lugar só.

Não usar "100% de cobertura" como substituto de confiança no comportamento.

## Exceção legítima de TDD

Em mudanças onde teste automatizado honesto é impraticável (ex.: configuração de infraestrutura efêmera), registrar antes da alteração: causa, alternativa (validação de schema, smoke test, migração reversível etc.), comando de verificação possível e risco residual. Não criar teste artificial só para marcar RED.

## Script de gate

Na trilha `fix`, o diretório contém só `brief.md`; o verificador trata o arquivo como spec, plan, tasks e verificação ao mesmo tempo, e `--gate verify` exige `status: converged`, a seção `## Verificação` citando cada AC e a tabela com Testes, Lint/compilação e Revisão em `PASS`/`WAIVED` (os demais gates, se presentes, não podem estar `FAIL`).

Execute `python3 /caminho/da/skill/scripts/check_spec.py /projeto/specs/<feature> --gate check` para verificar estrutura e rastreabilidade. `--gate implement` também exige frontmatter `status: approved` em spec, plan e tasks. `--gate verify` exige tasks concluídas, `verification.md` com status `converged` e a tabela de gates com os seis gates em `PASS` ou `WAIVED` (`WAIVED` com justificativa).

O verificador confere que os gates foram registrados e estão `PASS`/`WAIVED`, mas **não** executa as ferramentas, não confirma que os números são verdadeiros, não faz revisão semântica e não confirma autorização humana, inclusive de `WAIVED`. O agente deve validar esses pontos separadamente.
