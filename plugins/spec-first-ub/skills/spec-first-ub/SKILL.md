---
name: spec-first-ub
description: "Spec-Driven Development proporcional ao risco, em quatro ações (explore, propose, apply, archive): brief de uma página para fixes pequenos; spec, plan, tasks, análise e convergência para features maiores. Une TDD red-green-refactor, simplicidade, modelagem de domínio e quality gates (CRAP, duplicação, mutação, revisão) inspirados no ub-mode. Use quando o usuário pedir SDD, planejar antes de codar, arquivar uma spec concluída, ou invocar /spec-first-ub."
metadata:
  version: "0.2.0"
  origin: "Original, inspirada em unclebob/ub-mode e github/spec-kit; não é oficial"
---

# Spec First, Make it Work, Make it Right

## Contrato inegociável

1. **Antes do código:** compreender o problema e registrar o comportamento esperado de forma testável, com plano e tasks na profundidade que o risco pede (ver "Dimensionar o trabalho"). Nunca escrever ou alterar código de produção antes da autorização para implementar. Pode ler código, executar testes existentes e estudar o sistema durante discovery.
2. **Uma decisão, um lugar:** a spec guarda requisitos e comportamentos; o plan guarda escolhas técnicas; tasks guardam execução. Não duplicar decisões em documentos divergentes.
3. **Menor solução suficiente:** questionar a premissa e buscar subtração antes de adicionar camadas, abstrações, dependências ou ferramentas.
4. **TDD no desenvolvimento:** para cada tarefa comportamental, observar um teste falhar pelo motivo esperado (RED), aplicar a menor mudança (GREEN), melhorar estrutura com testes passando (REFACTOR). Não escrever testes desonestos; quando inviável, justificar a estratégia de verificação alternativa.
5. **Não confundir documento com evidência:** aprovação de spec não comprova implementação. Teste não executado não é teste aprovado. Um script pode verificar a estrutura dos artefatos, não a verdade de suas decisões.
6. **Proporcionalidade:** o processo cresce com o risco, nunca além. Um fix pequeno não gera três documentos, e uma mudança de alto risco não cabe em um brief.
7. **Autorização importa:** não fazer push, merge, deploy, exclusões destrutivas ou commits sem autorização explícita. Não marcar um documento como `approved` por conta própria.

## Contexto e ativação

No Claude Code, `/spec-first-ub <modo> <descrição>`; no Codex, `$spec-first-ub <modo> <descrição>`. O ciclo tem **quatro ações**, no estilo explorar → propor → executar → arquivar:

| Ação | O que faz | Escreve arquivos? | Termina em |
|---|---|---|---|
| `explore` | Postura de parceiro de pensamento: investiga o código, compara opções, questiona premissas. Não é fluxo, não tem etapas nem saída obrigatória | Só se o usuário pedir para capturar | Clareza, ou oferta de `propose` |
| `propose` | Dimensiona a trilha e gera **de uma vez** todos os artefatos até ficar pronto para implementar (SPEC → PLAN → TASKS → ANALYZE) | Sim, artefatos de documentação | `READY FOR REVIEW` e **parada** para aprovação |
| `apply` | Executa as tasks aprovadas em loop RED/GREEN/REFACTOR, até concluir ou bloquear; depois roda os gates e o VERIFY | Sim, código e checkboxes | `CONVERGED`, `PARTIAL` ou `BLOCKED`; se `CONVERGED`, oferta de `archive` |
| `archive` | Depois da revisão e finalização (`CONVERGED`), move `specs/<slug>/` para `specs/archive/<AAAA-MM-DD>-<slug>/` | Só move a pasta da spec | `ARCHIVED` ou `BLOCKED` |

Atalhos e granularidade fina (opcionais, são só instruções de conversação **dentro desta skill**, e não comandos CLI): `start` (= dimensionar e escolher a próxima ação), `fix` (força a trilha `fix`), `spec`, `plan`, `tasks`, `analyze` (refazem uma parte de `propose`), `implement` (= `apply`), `verify`, `status`. Instalada como plugin, cada ação também tem um slash command: `/spec-explore`, `/spec-propose`, `/spec-apply`, `/spec-archive`.

Se nenhum modo for indicado, dimensionar o trabalho, identificar o estágio existente, escolher a próxima ação segura e informar o que será produzido. Se o pedido for ambíguo, tomar decisões reversíveis e sinalizar premissas; perguntar apenas se o bloqueio for material. Nunca presumir autorização para implementar a partir da simples vontade de construir uma feature.

**As ações não são fases travadas.** `explore` pode ser invocado a qualquer momento (inclusive no meio do `apply`, quando uma task se mostra mais complexa que o previsto), e `apply` pode atualizar artefatos quando a implementação revelar um problema de design, desde que a mudança material seja reaprovada.

Reaproveitar arquivos existentes do repositório. Para trabalho `standard` ou `high`, usar `specs/<slug>/spec.md`, `plan.md`, `tasks.md`, `verification.md`. Mudanças concluídas ficam em `specs/archive/`, que **não conta como trabalho ativo**: ignorá-la ao inferir o slug ou procurar mudanças em andamento (pode ser lida como histórico). Se o projeto já usa Spec Kit, **não duplicar estrutura nem sobrescrever seus arquivos**; adaptar-se ao diretório ativo e respeitar a constituição já existente em `.specify/memory/constitution.md`. Caso contrário, adotar `specs/constitution.md` opcionalmente. Templates desta skill em `templates/`.

## Dimensionar o trabalho

Classificar antes de escrever qualquer documento e informar a trilha escolhida em uma linha. Na dúvida entre duas trilhas, escolher a menor e escalar se surgir risco.

| Trilha | Quando | Artefatos | Autorização para implementar |
|---|---|---|---|
| `trivial` | Sem mudança de comportamento (só build/lint, sem os demais gates): typo, texto, comentário, renomeação local, ajuste de config sem efeito funcional | Nenhum arquivo. Uma frase no chat com o que será feito e como será verificado | A instrução do usuário já basta |
| `fix` (risk `small`) | Bug ou ajuste pequeno, local, causa identificável, sem mudar contrato público, dados persistidos, segurança ou concorrência | `specs/<slug>/brief.md` (ou o mesmo conteúdo no chat se o projeto não versiona specs): problema, REQ/AC, abordagem, uma ou poucas tasks RED/GREEN/REFACTOR, verificação | Aprovação explícita do brief, como nas demais trilhas. Apresentar o brief, parar e só implementar depois do "pode seguir" do usuário |
| `standard` | Feature nova ou mudança com mais de um comportamento, módulos ou decisões de design | `spec.md`, `plan.md`, `tasks.md`, `verification.md`, cada um conciso | Aprovação explícita após ANALYZE |
| `high` | Segurança, dinheiro, dados, migração, concorrência, contrato público ou difícil de reverter | Os mesmos de `standard`, com riscos, rollback e observabilidade explícitos | Aprovação explícita e registrada, por documento |

**Sinais de escalada.** Se durante um `fix` aparecer mudança de contrato, de schema, de permissão, mais de um comportamento independente ou causa incerta, parar, dizer por quê e promover para `standard` ou `high`. Reaproveitar o texto do brief como ponto de partida da spec.

**O que nunca se reduz, em nenhuma trilha (exceto `trivial`, sem mudança de comportamento):** aprovação explícita antes de implementar e os gates de qualidade da trilha sobre o código alterado (Testes, Lint e Revisão no `fix`; os seis em `standard` e `high`). Além disso: comportamento esperado verificável, teste que falha antes da correção (ou justificativa), evidência real antes de declarar concluído, e honestidade sobre o que não foi executado.

## Fluxo / gates

As fases abaixo descrevem a trilha `standard`/`high`. Agrupamento: **EXPLORE** = fase 0; **PROPOSE** = fases 1 a 4; **APPLY** = fases 5 e 6; **ARCHIVE** = fase 7. Na trilha `fix`, SPEC, PLAN e TASKS colapsam nas seções do `brief.md` (Problema, Comportamento esperado, Abordagem, Tasks) e VERIFY vira a seção "Verificação" do mesmo arquivo. Os gates continuam valendo, só com menos texto.

### 0. EXPLORE — pensar antes de desenhar

**É uma postura, não um fluxo.** Sem etapas fixas, sem sequência obrigatória, sem artefato obrigatório. Explorar é tempo de pensar, não de executar.

- **Não implementar.** Pode ler arquivos, buscar no código e rodar comandos de leitura (incluindo testes existentes); nunca escreve código de produção. Se o usuário pedir para implementar, lembrar que isso vem depois de `propose` e aprovação.
- **Fundamentar no código real.** Mapear arquitetura relevante, pontos de integração, padrões em uso, complexidade escondida, contratos, testes e restrições. Não teorizar no vazio.
- **Curioso, não prescritivo.** Levantar várias direções e deixar o usuário seguir a que fizer sentido, em vez de um funil de perguntas. Não fingir entendimento: se algo está nebuloso, aprofundar.
- **Questionar premissas, inclusive as próprias.** É possível **não** criar esta funcionalidade? O que pode ser removido? Qual mudança mínima resolve a causa? Comparar opções com tabelas e trade-offs; recomendar um caminho se pedido. Diagramas ASCII quando ajudarem.
- **Mapear riscos e incógnitas.** Identificar resultado observável, atores, domínio, invariantes e comportamentos a preservar; sugerir spikes para o que não se sabe. Em `high`, explicitar segurança, dados, concorrência, migração, rollback e observabilidade.
- **Ver o que já existe.** Checar `specs/` (fora de `specs/archive/`) por trabalho em andamento; o arquivo serve de histórico de decisões passadas. Se houver mudança ativa, ler seus artefatos e referenciá-los na conversa.
- **Oferecer, não capturar sozinho.** Quando uma decisão se firmar, oferecer registrá-la no documento certo (requisito novo ou alterado → `spec.md`; decisão de design → `plan.md`; escopo → `spec.md`; trabalho novo → `tasks.md`; premissa invalidada → o artefato afetado). O usuário decide. Responder perguntas ou esclarecer dúvidas nunca é consentimento para escrever arquivos.
- **Fechar sem pressão.** Pode terminar em clareza, em artefato atualizado, ou em "pronto para propor?". Um resumo (problema, abordagem que emergiu, perguntas abertas, próximos passos) é opcional.
- Ao final, informar a trilha sugerida (`trivial`, `fix`, `standard`, `high`) conforme "Dimensionar o trabalho". O risco ajusta a profundidade, não elimina o comportamento verificável.

### PROPOSE — fases 1 a 4

Entrada: nome em kebab-case ou descrição do que construir. Se não houver entrada clara, perguntar o que o usuário quer construir e **não prosseguir sem entender**. Derivar o slug (ex.: "exportar pedidos em CSV" → `exportar-pedidos-csv`). Se já existir `specs/<slug>/`, perguntar se é para continuar o existente ou criar outro.

Gerar os artefatos **em ordem de dependência, numa única passada**, até que tudo o que o `apply` exige esteja pronto: ler os artefatos anteriores antes de escrever o próximo, confirmar que cada arquivo foi realmente escrito, e mostrar uma linha de progresso por artefato ("Criado spec.md"). Se uma informação for criticamente incerta, perguntar; caso contrário, preferir decisões razoáveis e sinalizar premissas para manter o ritmo. Ao terminar, resumir: slug e local, artefatos criados com uma linha cada, pendências, e o convite para aprovar e rodar `apply`.

### 1. SPEC — definir O QUÊ e POR QUÊ

Criar/atualizar `spec.md` usando `templates/spec.md`.

- Problema, resultado esperado, cenários de uso, requisitos `REQ-###`, aceites `AC-###` vinculados a requisitos, negativos/bordas, regras de domínio, limites e fora de escopo.
- Critérios observáveis: Given/When/Then ou entrada/ação/saída; incluir caminho feliz, falhas, idempotência e concorrência quando aplicável.
- Sem escolher framework, padrões de classe ou detalhes prematuros de implementação.
- Se houver dúvidas críticas, apontar o bloqueio; não inventar contrato.
- Gate SPEC: requisitos sem contradições evidentes, comportamentos testáveis, fora de escopo expresso; solicitar revisão do usuário antes de seguir para plan quando exigido pelo usuário ou por mudança de domínio/risco alto.

### 2. PLAN — decidir COMO com design responsável

Criar/atualizar `plan.md` usando `templates/plan.md`.

- Levantar solução mais simples, ao menos uma alternativa real quando trade-off não for óbvio, e decisões com justificativas.
- Modelar domínio e tipos de modo a desencorajar estados inválidos; validar entrada nas bordas; manter regras de negócio separadas de I/O; respeitar dependência entre camadas.
- Considerar formato dos dados antes do algoritmo, contratos, compatibilidade, segurança, observabilidade, migração, concorrência e idempotência conforme relevância.
- Planejar testes de comportamento, integração/contrato e rollback. Não criar arquitetura especulativa.
- Gate PLAN: toda decisão técnica deriva de requisito/riscos; não há sobreengenharia sem justificativa.

### 3. TASKS — fatiar verticalmente

Criar/atualizar `tasks.md` usando `templates/tasks.md`.

- Cada `TASK-###` deve citar `REQ-###` e `AC-###`, possuir entrega verificável e evidência esperada.
- Ordenar por dependência e valor; preferir unidade vertical pequena a "criar todas as entidades, depois todos os testes".
- Cada task comportamental contém microciclo RED / GREEN / REFACTOR. Tasks não comportamentais devem indicar uma checagem observável.
- Gate TASKS: todo requisito e aceite devem estar cobertos, sem tasks órfãs, com condições de conclusão claras.

### 4. ANALYZE — auditar antes de desenvolver (fecha o PROPOSE)

- Revisar `spec.md`, `plan.md`, `tasks.md` juntos. Procurar lacunas, escopo não pedido, duplicação, critérios não testáveis, risco não mitigado e tasks sem rastreabilidade.
- Corrigir **no documento fonte**; nunca silenciar inconsistências em resumo.
- Se Python estiver disponível, rodar `python3 <skill-root>/scripts/check_spec.py specs/<slug> --gate propose` (ver `references/quality-gates.md`). O script é só uma verificação estrutural.
- Obter autorização humana explícita para implementar; somente então registrar `status: approved` em spec, plan e tasks. Verificar `--gate apply` se o script estiver disponível.
- **STOP:** sem autorização explícita, entregar apenas os artefatos, próximos passos e pendências. Não avançar silenciosamente ao código.

### APPLY — fases 5 e 6

Entrada: slug opcional. Se omitido, inferir da conversa; se houver só uma mudança ativa em `specs/` (excluindo `specs/archive/`), usá-la; se ambíguo, perguntar. **Anunciar sempre** "Usando: <slug>" e como trocar.

1. **Verificar estado.** Rodar `--gate apply` se o script existir. Sem `status: approved` registrado pelo humano, não editar código: voltar a `propose`/ANALYZE e parar. Se todas as tasks já estiverem concluídas, ir direto aos gates e ao VERIFY.
2. **Ler o contexto**: spec, plan e tasks (ou o brief) por inteiro antes da primeira edição, e mostrar o progresso "N/M tasks concluídas" com as pendentes.
3. **Laço**: executar as tasks pendentes em ordem, uma por vez, com o microciclo da fase 5, até concluir tudo ou bloquear. Anunciar "Task 3/7: <descrição>"; manter as mudanças mínimas e restritas à task; marcar o checkbox **imediatamente** após a evidência.
4. **Pausar e perguntar quando**: a task for ambígua; a implementação revelar problema de design (sugerir atualizar os artefatos); houver erro, bloqueio ou teste que não falha pelo motivo esperado; ou o usuário interromper. **Não adivinhar.** Ao pausar, informar: progresso, o problema encontrado e 2 a 3 opções (a última sempre "outra abordagem"), e esperar a decisão.
5. **Ao concluir as tasks**: rodar os gates de qualidade e o VERIFY (fase 6) no mesmo `apply`, e encerrar com o estado `CONVERGED`, `PARTIAL` ou `BLOCKED`.

Saída durante o laço: `## Aplicando: <slug>` e, por task, `✓ Task N/M concluída`. Na pausa: `## Aplicação pausada` com progresso, problema e opções.

### 5. IMPLEMENT — make it work, then make it right

Para cada task aprovada, em ordem:

1. Confirmar objetivo e aceite referenciado. Ler código circundante; preservar comportamento não solicitado.
2. **RED:** criar teste focado em comportamento observável e executar para confirmar falha pelo motivo correto. Para bug, reproduzir causa antes de corrigir. Se o teste honesto for inviável, registrar motivo e verificação alternativa antes de mudar código.
3. **GREEN:** fazer a menor mudança que satisfaz o teste. Resolver a causa, não mascarar o sintoma; preservar fronteiras, contratos e idempotência relevante.
4. **REFACTOR:** reduzir duplicação, complexidade e acoplamento, com os mesmos testes passando. Extrair abstração só se houver pressão real.
5. **CHECK:** rodar testes pertinentes e lint/compilação, e registrar comando e resultado reais. Os gates de CRAP, duplicação, mutação e revisão rodam ao concluir o conjunto de tasks, antes de VERIFY (ver "Gates de qualidade do código").
6. Atualizar checkbox da task só após evidência; se descobre nova exigência, parar a execução do escopo afetado, atualizar spec/plan/tasks e obter nova aprovação para alteração material.

### Gates de qualidade do código (ao concluir IMPLEMENT)

O código gerado é controlado e validado, não só testado. Os seis gates abaixo valem em `standard` e `high`. Na trilha `fix` são obrigatórios só **Testes, Lint/compilação e Revisão**; CRAP, duplicação e mutação são opcionais (rodar se for barato ou o código alterado for sensível, e então não podem terminar em `FAIL`). Todos se aplicam ao código alterado, e cada um termina em `PASS`, `FAIL`, `NOT_MEASURED` ou `WAIVED`:

| Gate | Critério (inspirado no `ub-mode`) |
|---|---|
| Testes | Suite pertinente verde. Testes chamam o código como o usuário e checam o resultado visível. Um teste que passaria com toda função retornando nada é descartado |
| Lint/compilação | Sem erro novo; compilador e linters não silenciados |
| CRAP | Cada função alterada com CRAP < 10, reduzindo por divisão, por teste ou ambos. `case`/`switch` só se reduz se valer a pena |
| Duplicação | Nenhuma duplicação com similaridade ≥ 0,8 sem justificativa. Eliminar sem abstrair por capricho |
| Mutação | Cobrir o não coberto, matar os sobreviventes e apagar código morto |
| Revisão | Checklist em `references/quality-gates.md`: causa raiz tratada, validação nas bordas, ilegais inviáveis no tipo, idempotência, sem comportamento fora do escopo |

**Obtendo as ferramentas.** Ordem: (1) `crapper`, `dryer` e `mutator` do unclebob, se estiverem no PATH (`command -v`); (2) os scripts desta skill, `scripts/crap.py`, `scripts/dry.py` e `scripts/mutate.py`, equivalentes em Python stdlib (uso em `references/quality-gates.md`); (3) o equivalente do stack indicado lá. Cada script imprime `GATE <nome>: PASS|FAIL|NOT_MEASURED` e sai com 0/1/2; copiar essa linha como evidência. Sem nenhuma opção, não instalar nada sem autorização: o gate fica `NOT_MEASURED`. `mutate.py` reescreve arquivos no lugar (e restaura): rodar só com a árvore commitada ou stash disponível.

**Regra de convergência.** `CONVERGED` exige em `PASS` ou `WAIVED` todos os gates obrigatórios da trilha (seis em `standard`/`high`, três em `fix`). `NOT_MEASURED` e `FAIL` bloqueiam. `WAIVED` só existe com justificativa escrita e **aprovação explícita do usuário** para dispensar aquele gate; o agente não se concede dispensa. Nunca inventar resultado nem threshold.

**Brief só no chat.** Sem `specs/` versionado, o `--gate verify` não se aplica: a resposta final traz a tabela dos gates obrigatórios com status e evidência reais, e o log.

**Log.** Manter na seção de verificação um log curto de cada ação relevante e do motivo, e reportá-lo ao concluir.

### 6. VERIFY / CONVERGE — spec como contrato de entrega

- Comparar cada `AC-###` com código, teste e resultado observado; considerar falhas, compatibilidade, segurança e regressão.
- Executar a suite e os gates de qualidade da trilha; preencher `verification.md` (ou a seção Verificação do brief) com evidências, status de cada gate, log e riscos residuais.
- Se houver gap, adicionar task(s) e completar outro ciclo RED/GREEN/REFACTOR; nunca declarar `Converged` com gap bloqueador.
- Sinalizar estado: `CONVERGED` somente se todos aceites comprovados, os gates obrigatórios da trilha em `PASS`/`WAIVED` e sem bloqueio; `PARTIAL` ou `BLOCKED` caso contrário.
- Encerrar com changelog curto: *o quê*, *por quê*, *testes realmente executados*, *pendências*, *arquivos alterados*.
- Se `CONVERGED` e a mudança vive em `specs/<slug>/`, perguntar se deve arquivá-la agora (ação `archive`). Arquivar só com o "sim" do usuário; sem resposta, deixar como próximo passo.

### 7. ARCHIVE — fechar a mudança depois da revisão

Entrada: slug opcional, resolvido como no `apply` (anunciar "Usando: <slug>"). Só existe para mudanças com artefatos em `specs/`; `trivial` e brief só no chat não têm o que arquivar.

1. **Confirmar que acabou.** Rodar `--gate verify`; sem `PASS` (tasks abertas, gate sem `PASS`/`WAIVED`, `status` diferente de `converged`), não arquivar: listar o que falta e indicar `apply`. Sem Python, conferir à mão os mesmos itens e dizer que a checagem foi manual.
2. **Arquivar.** `python3 <skill-root>/scripts/archive_spec.py specs/<slug> --dry-run` mostra o destino; sem `--dry-run`, move `specs/<slug>/` para `specs/archive/<AAAA-MM-DD>-<slug>/` (data de hoje, `--date` para outra). O script recusa destino existente e pasta já arquivada; não apaga nem altera o conteúdo. Sem Python, mover a pasta para o mesmo destino (`git mv` se versionado).
3. **Relatar.** Copiar a linha `ARCHIVE: ...`, informar origem e destino e lembrar que a mudança ainda não foi commitada. Commit, push e merge seguem a regra 7 do contrato.

Se o projeto usa Spec Kit, não mover os diretórios dele: perguntar ao usuário qual convenção de arquivamento seguir.

## Regras de tomada de decisão

- **Bugs:** reproduzir, isolar causa, especificar o comportamento esperado e o caso de regressão antes da correção.
- **Código legado:** fazer uma caracterização do comportamento existente quando necessário; não reescrever módulos adjacentes sem relação.
- **Mudança urgente:** a urgência não muda a trilha. O risco real define a profundidade; aprovação, teste que falha antes e evidência continuam valendo.
- **Refatoração pura:** especificar invariantes de comportamento, baseline e evidência de equivalência; a spec não deve inventar feature nova.
- **Restrições de ferramentas:** nunca inventar execução, resultados ou thresholds. Gate sem medição é `NOT_MEASURED` e bloqueia a convergência até medir ou ser dispensado pelo usuário.
- **Trabalho paralelo:** tasks independentes podem ser delegadas somente quando não compartilham o mesmo estado mutável nem geram conflitos de integração.
- **Logs e contexto:** manter registro enxuto das decisões, comandos e evidências. Não despejar histórico irrelevante no contexto principal.

## Formato da resposta em cada fase

`Ação | Feature | Artefatos escritos | Decisões | Riscos/pendências | Gate | Próximo passo`

`explore` não usa esse formato: é conversa livre. Na trilha `fix` e `trivial`, usar uma versão em duas ou três linhas (o que mudou, o que foi verificado, o que ficou pendente). Terminar `propose` com uma indicação inequívoca: `READY FOR REVIEW`, `APPROVED FOR IMPLEMENTATION` (somente se autorizado) ou `BLOCKED`. Terminar `apply` com `CONVERGED`, `PARTIAL` ou `BLOCKED`, e `archive` com `ARCHIVED` ou `BLOCKED`.

## Recursos

- `templates/brief.md` — trilha fix, arquivo único
- `templates/spec.md` — requisitos e critérios testáveis
- `templates/plan.md` — arquitetura mínima, riscos e testes
- `templates/tasks.md` — rastreabilidade e microciclos TDD
- `templates/verification.md` — evidências de convergência
- `templates/constitution.md` — princípios de projeto (opcional)
- `references/quality-gates.md` — política dos gates e exceções
- `scripts/check_spec.py` — verificação determinística e limitada dos artefatos
- `scripts/archive_spec.py` — move uma mudança `CONVERGED` para `specs/archive/<data>-<slug>/`
- `scripts/crap.py`, `scripts/dry.py`, `scripts/mutate.py` — gates CRAP, duplicação e mutação (equivalentes a `crapper`, `dryer`, `mutator`); `scripts/gatelib.py` é código compartilhado
