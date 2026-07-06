# Prompt: Reintegrar Actual Budget MCP no Hermes

A configuração do MCP do Actual Budget mudou. Reconfigure o Hermes para usar a nova URL, descubra as ferramentas disponíveis e teste leitura e escrita.

## O que mudou

- **Novo servidor MCP**: `s-stefanov/actual-mcp` (imagem custom `actual-mcp:custom-26.5.0` no `tools`).
- **Nova URL direta**: `https://mcp.local.batistela.tech/actual-budget`
- **Nova URL MCPO**: `https://mcpo.local.batistela.tech/actual-budget`
- **Autenticação**: `Authorization: Bearer <vault.tools.mcp_mcpo_api_key>`
- **Porta interna**: `3010`
- **Escrita habilitada**: `--enable-write` está ativo. Ferramentas de criação/edição/exclusão estão disponíveis.
- As ferramentas antigas (ex: `actual_accounts_list`) não existem mais; os novos nomes devem ser descobertos via `tools/list`.

## Ferramentas conhecidas

### Leitura
- `get-accounts`
- `get-transactions`
- `spending-by-category`
- `monthly-summary`
- `balance-history`
- `get-grouped-categories`
- `get-payees`
- `get-rules`

### Escrita
- `create-category`, `update-category`, `delete-category`
- `create-category-group`, `update-category-group`, `delete-category-group`
- `create-payee`, `update-payee`, `delete-payee`
- `create-rule`, `update-rule`, `delete-rule`
- `create-transaction`, `update-transaction`, `delete-transaction`
- `import-transactions`
- `run-bank-sync`

## Tarefas

1. Atualize a configuração MCP do Hermes para a URL direta:
   ```json
   {
     "mcpServers": {
       "actual-budget": {
         "type": "streamable-http",
         "url": "https://mcp.local.batistela.tech/actual-budget",
         "headers": {
           "Authorization": "Bearer <vault.tools.mcp_mcpo_api_key>"
         }
       }
     }
   }
   ```
2. Reinicie o serviço Hermes:
   ```bash
   ssh root@hermes systemctl restart hermes-webui
   ```
3. Descubra as ferramentas disponíveis (use `tools/list` ou a interface do Hermes).
4. Teste com uma pergunta real, ex:
   - "Liste minhas contas do Actual Budget"
   - "Crie uma categoria chamada Teste MCP"
5. Se falhar, verifique:
   - `ssh root@tools docker logs mcp-actual-budget --tail 50`
   - `ssh root@tools docker logs mcpo --tail 50`
   - `ssh root@hermes journalctl -u hermes-webui -n 100 -f`

## Notas

- Se a imagem `actual-mcp:custom-26.5.0` não existir no `tools`, construa com:
  ```bash
  make build-actual-mcp-image
  ```
- Tenha cuidado com ferramentas de escrita em produção; teste primeiro em dados descartáveis.
