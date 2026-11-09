# spec-first-ub — SDD com disciplina de engenharia

Plugin/skill independente de agentes de programação, dimensionada pelo risco: serve tanto para um fix de uma linha quanto para uma feature grande. Organiza-se em **explore → propose → apply → archive**, que cobrem Spec → Plan → Tasks → Analyze → Implement (TDD) → Verify/Converge → Archive, com princípios de simplicidade, modelagem do domínio e qualidade de código.

> Projeto original, **não oficial**, inspirado em [unclebob/ub-mode](https://github.com/unclebob/ub-mode) e [github/spec-kit](https://github.com/github/spec-kit). Não reproduz nem substitui nenhum dos dois projetos.

## Estrutura do plugin

```text
plugins/spec-first-ub/
  .claude-plugin/plugin.json      # manifesto do plugin
  commands/                       # /spec-explore, /spec-propose, /spec-apply, /spec-archive
  skills/spec-first-ub/
    SKILL.md                      # instruções da skill
    templates/  references/  scripts/  examples/
  install.sh                      # instalação manual por symlinks (alternativa ao marketplace)
```

## Instalação

**Claude Code (marketplace, recomendado):**

```text
/plugin marketplace add josinaldojr/skills
/plugin install spec-first-ub@josinaldojr-skills
```

Atualize com `/plugin marketplace update josinaldojr-skills`. Os comandos do plugin aparecem como `/spec-first-ub:spec-apply` etc. (ou só `/spec-apply`, se não houver conflito de nome).

**Manual (Claude Code sem marketplace):** `./install.sh` cria symlinks da skill e dos comandos em `~/.claude/` (seguro rodar de novo; `./install.sh --uninstall` remove). Não use junto com o plugin instalado, para não duplicar comandos.

**Outros agentes:** copie `skills/spec-first-ub/` para o diretório de skills do agente (Codex: `~/.agents/skills/spec-first-ub/`; projeto: `.agents/skills/spec-first-ub/`) e, se quiser os comandos, `commands/*.md` para `~/.codex/prompts/` (chamados com `/prompts:spec-explore` etc.; confirme a convenção da sua versão).

O arquivo inicial é `SKILL.md`. Não requer Spec Kit, Node, Python ou ferramentas externas para funcionar como **instrução de agente**. Os scripts são opcionais e requerem Python 3.10+.

## Comandos por fase

Um slash command por ação, em `commands/` (atalhos finos que invocam a skill):

| Comando | Ação | Para quando |
|---|---|---|
| `/spec-explore <tema>` | explore | clareza, ou oferta de `/spec-propose` |
| `/spec-propose <slug>` | propose | `READY FOR REVIEW`, aguardando sua aprovação |
| `/spec-apply [slug]` | apply | `CONVERGED`, `PARTIAL` ou `BLOCKED`; se `CONVERGED`, pergunta se deve arquivar |
| `/spec-archive [slug]` | archive | `ARCHIVED` (spec movida para `specs/archive/`) ou `BLOCKED` |

## Arquivamento

Depois da revisão e finalização da implementação (`apply` em `CONVERGED`), o agente oferece arquivar a spec; com o seu "sim" (ou via `/spec-archive`), ela sai de `specs/<slug>/` e vai para `specs/archive/<AAAA-MM-DD>-<slug>/`. O arquivamento:

- exige `--gate verify` em `PASS` (tasks fechadas, gates obrigatórios em `PASS`/`WAIVED`, `status: converged`);
- não apaga nem altera o conteúdo, e recusa sobrescrever um arquivamento existente;
- não faz commit: a mudança fica no working tree para você revisar;
- tira a mudança da lista de trabalho ativo: `explore` e `apply` ignoram `specs/archive/` ao inferir o slug.

```bash
python3 skills/spec-first-ub/scripts/archive_spec.py specs/002-exportar-pedidos-csv --dry-run
python3 skills/spec-first-ub/scripts/archive_spec.py specs/002-exportar-pedidos-csv
```

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

O ciclo tem quatro ações, no estilo explorar → propor → executar → arquivar:

- `/spec-first-ub explore Exportar pedidos em CSV` — pensar com o agente: lê o código, compara opções, questiona premissas. **Não escreve código** e só grava documentos se você pedir
- `/spec-first-ub propose exportar-pedidos-csv` — dimensiona a trilha e gera de uma vez spec, plan e tasks (ou o `brief.md`), audita a consistência e **para** para sua aprovação
- `/spec-first-ub apply` — **somente** após aprovação explícita: executa as tasks em RED/GREEN/REFACTOR, marca os checkboxes, pausa em bloqueios, roda os gates e verifica a convergência
- `/spec-first-ub archive` — após `CONVERGED`: move a spec para `specs/archive/<data>-<slug>/`

As ações não são fases travadas: `explore` vale a qualquer momento (inclusive no meio do `apply`) e o `apply` pode atualizar os artefatos se a implementação revelar um problema de design (mudança material exige nova aprovação).

Atalhos de granularidade fina, opcionais: `start` (dimensiona e escolhe a próxima ação), `fix` (força a trilha fix), `spec`, `plan`, `tasks`, `analyze` (refazem uma parte do `propose`), `implement` (= `apply`), `verify`, `status`.

Estes são modos textuais da skill; no Codex, substitua o prefixo `/spec-first-ub` por `$spec-first-ub`. Não são executáveis de terminal independentes.

## Artefatos por feature

```text
specs/
  constitution.md                 # opcional, por projeto
  archive/
    2026-11-08-001-nome-antigo/   # mudanças concluídas e arquivadas
  001-nome-da-feature/
    brief.md                      # Trilha fix: tudo em um arquivo
    spec.md                       # O quê e por quê
    plan.md                       # Como
    tasks.md                      # Ordem, rastreabilidade e TDD
    verification.md               # Evidências da entrega
```

O agente adapta-se aos arquivos já presentes. Se o projeto usa GitHub Spec Kit, reutiliza os artefatos existentes em vez de criar um segundo conjunto conflitante.

## Scripts dos gates de qualidade

Equivalentes em Python (stdlib) às ferramentas `crapper`, `dryer` e `mutator` do ub-mode, em `skills/spec-first-ub/scripts/`:

| Script | Gate | Resumo |
|---|---|---|
| `crap.py` | CRAP | `comp² × (1 − cob)³ + comp` por função; lê coverage.py JSON, Istanbul JSON, JaCoCo/Cobertura XML, lcov ou perfil do Go |
| `dry.py` | Duplicação | Pares de funções com similaridade ≥ 0,8 |
| `mutate.py` | Mutação | Muta o código, roda a suite, lista sobreviventes; restaura a fonte ao fim |

Exemplo: `python3 skills/spec-first-ub/scripts/crap.py src --coverage coverage.json --changed`. Detalhes, limitações e códigos de saída em `skills/spec-first-ub/references/quality-gates.md`. Testes: `cd skills/spec-first-ub/scripts && python3 -m unittest`.

## Exemplos

- `skills/spec-first-ub/examples/001-fix-desconto-centavos/` — trilha `fix`: um bug de arredondamento em um único `brief.md`.
- `skills/spec-first-ub/examples/002-exportar-pedidos-csv/` — trilha `standard`: spec, plan e tasks de uma feature pequena.

## Verificador estrutural (opcional)

Comandos a partir de `skills/spec-first-ub/`:

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
- Arquiva a spec só depois de `CONVERGED` e com seu consentimento; move para `specs/archive/`, sem apagar e sem commit.
