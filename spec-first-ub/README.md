# spec-first-ub — SDD com disciplina de engenharia

Skill independente de agentes de programação, dimensionada pelo risco: serve tanto para um fix de uma linha quanto para uma feature grande. Organiza-se em **explore → propose → apply**, que cobrem Spec → Plan → Tasks → Analyze → Implement (TDD) → Verify/Converge, com princípios de simplicidade, modelagem do domínio e qualidade de código.

> Projeto original, **não oficial**, inspirado em [unclebob/ub-mode](https://github.com/unclebob/ub-mode) e [github/spec-kit](https://github.com/github/spec-kit). Não reproduz nem substitui nenhum dos dois projetos.

## Instalação

Copie a pasta `spec-first-ub` para o diretório de skills suportado pelo seu agente. Exemplos comuns (confirme a convenção da sua versão):

- Claude Code (usuário): `~/.claude/skills/spec-first-ub/`
- Codex (usuário): `~/.agents/skills/spec-first-ub/`
- Skill local de projeto: `.agents/skills/spec-first-ub/` em clientes que suportam o padrão Agent Skills.

O arquivo inicial é `SKILL.md`. Não requer Spec Kit, Node, Python ou ferramentas externas para funcionar como **instrução de agente**. O script de validação é opcional e requer Python 3.10+.

## Comandos por fase

Um slash command por ação, em `commands/` (atalhos finos que invocam a skill):

| Comando | Ação | Para quando |
|---|---|---|
| `/spec-explore <tema>` | explore | clareza, ou oferta de `/spec-propose` |
| `/spec-propose <slug>` | propose | `READY FOR REVIEW`, aguardando sua aprovação |
| `/spec-apply [slug]` | apply | `CONVERGED`, `PARTIAL` ou `BLOCKED` |

Instalação (Claude Code): `./install.sh` cria symlinks da skill e dos comandos em `~/.claude/` (seguro rodar de novo ao adicionar comandos; `./install.sh --uninstall` remove). Como são links, um `git pull` já atualiza tudo. Manualmente: `cp commands/*.md ~/.claude/commands/`. No Codex, copie para `~/.codex/prompts/` e chame com `/prompts:spec-explore` etc. (confirme a convenção da sua versão).

## Trilhas por tamanho

| Trilha | Quando | O que se escreve |
|---|---|---|
| `trivial` | Typo, texto, config sem efeito funcional | Nada, só uma frase no chat |
| `fix` | Bug ou ajuste pequeno e local | Um `brief.md` (uma página) |
| `standard` | Feature com vários comportamentos | `spec.md`, `plan.md`, `tasks.md`, `verification.md` concisos |
| `high` | Segurança, dados, dinheiro, migração, contrato público | Os mesmos, com riscos, rollback e observabilidade |

Se um `fix` revelar risco maior, o agente para e promove o trabalho para `standard` ou `high`.

## Uso conversacional

No Claude Code, invocar com `/spec-first-ub`. No Codex, mencionar a skill com `$spec-first-ub` (ou selecioná-la em `/skills`). Os modos abaixo são argumentos textuais, não comandos independentes.

O ciclo tem três ações, no estilo explorar → propor → executar:

- `/spec-first-ub explore Exportar pedidos em CSV` — pensar com o agente: lê o código, compara opções, questiona premissas. **Não escreve código** e só grava documentos se você pedir
- `/spec-first-ub propose exportar-pedidos-csv` — dimensiona a trilha e gera de uma vez spec, plan e tasks (ou o `brief.md`), audita a consistência e **para** para sua aprovação
- `/spec-first-ub apply` — **somente** após aprovação explícita: executa as tasks em RED/GREEN/REFACTOR, marca os checkboxes, pausa em bloqueios, roda os gates e verifica a convergência

As ações não são fases travadas: `explore` vale a qualquer momento (inclusive no meio do `apply`) e o `apply` pode atualizar os artefatos se a implementação revelar um problema de design (mudança material exige nova aprovação).

Atalhos de granularidade fina, opcionais: `start` (dimensiona e escolhe a próxima ação), `fix` (força a trilha fix), `spec`, `plan`, `tasks`, `analyze` (refazem uma parte do `propose`), `implement` (= `apply`), `verify`, `status`.

Estes são modos textuais da skill; no Codex, substitua o prefixo `/spec-first-ub` por `$spec-first-ub`. Não são executáveis de terminal independentes.

## Artefatos por feature

```text
specs/
  constitution.md                 # opcional, por projeto
  001-nome-da-feature/
    brief.md                      # Trilha fix: tudo em um arquivo
    spec.md                       # O quê e por quê
    plan.md                       # Como
    tasks.md                      # Ordem, rastreabilidade e TDD
    verification.md               # Evidências da entrega
```

O agente adapta-se aos arquivos já presentes. Se o projeto usa GitHub Spec Kit, reutiliza os artefatos existentes em vez de criar um segundo conjunto conflitante.

## Scripts dos gates de qualidade

Equivalentes em Python (stdlib) às ferramentas `crapper`, `dryer` e `mutator` do ub-mode, em `scripts/`:

| Script | Gate | Resumo |
|---|---|---|
| `crap.py` | CRAP | `comp² × (1 − cob)³ + comp` por função; lê coverage.py JSON, Istanbul JSON, JaCoCo/Cobertura XML, lcov ou perfil do Go |
| `dry.py` | Duplicação | Pares de funções com similaridade ≥ 0,8 |
| `mutate.py` | Mutação | Muta o código, roda a suite, lista sobreviventes; restaura a fonte ao fim |

Exemplo: `python3 scripts/crap.py src --coverage coverage.json --changed`. Detalhes, limitações e códigos de saída em `references/quality-gates.md`. Testes: `cd scripts && python3 -m unittest`.

## Exemplos

- `examples/001-fix-desconto-centavos/` — trilha `fix`: um bug de arredondamento em um único `brief.md`.
- `examples/002-exportar-pedidos-csv/` — trilha `standard`: spec, plan e tasks de uma feature pequena.

## Verificador estrutural (opcional)

```bash
python3 scripts/check_spec.py examples/002-exportar-pedidos-csv --gate propose
# Trilha fix (brief.md único):
python3 scripts/check_spec.py examples/001-fix-desconto-centavos --gate propose
# Gate do início do apply (alias antigo: implement). Sairá com erro até que o humano aprove a documentação.
python3 scripts/check_spec.py examples/002-exportar-pedidos-csv --gate apply
python3 -m unittest discover -s scripts -p 'test_*.py'
```

`--gate verify` confere que os gates obrigatórios da trilha (seis em `standard`/`high`, três em `fix`) estão `PASS` ou `WAIVED` com evidência; não executa as ferramentas nem comprova que os números são reais.

`--gate propose` (fim do `propose`; alias `check`) valida presença de arquivos, identificadores únicos, vínculos REQ/AC/TASK e cobertura estrutural. Não substitui uma revisão de qualidade do conteúdo.

## Comportamento deliberado

- Não altera código antes da revisão/aprovação, salvo tarefas de observação (ler código, testes existentes).
- Não faz push, deploy ou merge automaticamente.
- Não afirma sucesso de testes que não foram executados.
- Gera documentação curta para tarefas pequenas e aumenta rigor proporcional ao risco.
- Em `fix`, `standard` e `high`, só implementa após aprovação explícita; apenas `trivial` (sem mudança de comportamento) dispensa essa pausa.
- Valida o código gerado com seis gates (testes, lint/compilação, CRAP < 10, duplicação ≥ 0,8, mutação e checklist de revisão), como o `ub-mode`. No `fix` são obrigatórios só testes, lint e revisão; `standard` e `high` exigem os seis. Usa `crapper`, `dryer` e `mutator` se instalados; senão, o equivalente do stack (tabela em `references/quality-gates.md`).
- Gate sem medição fica `NOT_MEASURED` e bloqueia `CONVERGED`. Só o usuário pode dispensar um gate (`WAIVED`), com justificativa.
