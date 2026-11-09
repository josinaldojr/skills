# skills

Marketplace público de plugins/skills para agentes de programação desenvolvidos neste workspace.

## Instalação (Claude Code)

```text
/plugin marketplace add josinaldojr/skills
/plugin install <plugin>@josinaldojr-skills
```

## Plugins

| Plugin | Descrição |
|---|---|
| [`spec-first-ub`](plugins/spec-first-ub/) | Spec-Driven Development proporcional ao risco (explore, propose, apply, archive) com TDD e quality gates |

## Estrutura

```text
.claude-plugin/marketplace.json   # catálogo do marketplace
plugins/<plugin>/
  .claude-plugin/plugin.json      # manifesto do plugin
  commands/                       # slash commands
  skills/<skill>/SKILL.md         # skills
```

Para adicionar um plugin: criar `plugins/<nome>/` com `.claude-plugin/plugin.json` e registrá-lo em `plugins` no `marketplace.json`.
