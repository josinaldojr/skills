---
feature: 002-exportar-pedidos-csv
status: draft
risk: standard
---

# Spec — Exportar pedidos em CSV por período

## Problema e resultado

A equipe de operações copia pedidos da tela para planilhas na conciliação mensal. Precisa baixar um CSV dos pedidos de um período. A exportação deve mostrar os mesmos pedidos que a listagem atual, que já filtra por período e respeita permissões.

## Escopo

- Inclui: endpoint autenticado que devolve os pedidos de um período em CSV.
- Não inclui: outros formatos, agendamento e envio por e-mail.

## Requisitos e aceites

- **REQ-001:** O usuário autorizado exporta em CSV os pedidos criados entre duas datas (inclusive).
- **AC-001** (REQ-001): Dado 3 pedidos em 10/03, 15/03 e 20/04, quando exporta de 01/03 a 31/03, então o CSV tem o cabeçalho e as linhas de 10/03 e 15/03.
- **REQ-002:** O CSV contém só pedidos que o usuário tem permissão de ver.
- **AC-002** (REQ-002): Dado um usuário sem acesso à loja B, quando exporta, então nenhum pedido da loja B aparece.
- **REQ-003:** Períodos inválidos ou acima de 366 dias são rejeitados com erro claro.
- **AC-003** (REQ-003): Dado data final anterior à inicial ou intervalo de 367 dias, quando exporta, então a resposta é 400 com o motivo e nenhum CSV é gerado.

## Bordas e restrições

Período sem pedidos devolve só o cabeçalho. Vírgula, aspas e quebra de linha nos campos devem ser escapadas. Deve funcionar com 50 mil pedidos sem carregar tudo em memória.

## Dúvidas abertas

Premissa: o fuso das datas é o da conta. Confirmar com operações.

## Revisão

- Aprovador: responsável pelo produto.
- Evidência de aprovação: pendente.
