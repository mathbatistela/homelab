# Testes de ponta a ponta — caderneta do Seu Jader

Estes testes **não usam dublê nenhum**. Eles falam com o banco de verdade
(`tiao_database`) e com a URL pública de verdade (`https://tiao.batistela.tech`),
passando pelo PIN do Pangolin, pelo túnel e pelo contêiner na VM `hermes`.

Não existe `TestClient` aqui, e nada aponta para `localhost`. Se o Pangolin, o
túnel ou o contêiner estiverem fora do ar, estes testes falham — é exatamente
para isso que eles existem.

## Antes de rodar

**Não rode durante a pesagem.** A suíte escreve quatro animais de mentira
(`e2e-901` a `e2e-904`) e as pesagens do dia deles, e apaga tudo no fim. A
limpeza roda também **antes** de semear, então uma rodada interrompida se
conserta sozinha na rodada seguinte. Mas até lá as linhas ficam na caderneta do
Seu Jader, e se ninguém for rodar a suíte de novo tão cedo, apague à mão:

```sql
DELETE FROM pesagens WHERE animal_id IN (SELECT id FROM animais WHERE brinco LIKE 'e2e-90%');
DELETE FROM animais WHERE brinco LIKE 'e2e-90%';
```

## Variáveis de ambiente

Nenhuma delas está no repositório. Quem roda a suíte junta os valores na hora e
os passa pelo ambiente — nunca por arquivo versionado.

| Variável | O que é | De onde vem |
| --- | --- | --- |
| `TIAO_PIN` | o PIN da borda | `config/fragments/pangolin/tiao.yml`, em `auth.pincode` |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | credenciais do **bot** (`tiao_user`), que escreve | `/root/.hermes/profiles/tiao/.env` na VM `hermes` (`root@hermes-vm.local.batistela.tech`) |
| `TIAO_WEB_PGHOST`, `TIAO_WEB_PGDATABASE`, `TIAO_WEB_PGUSER`, `TIAO_WEB_PGPASSWORD` (e `TIAO_WEB_PGPORT`, se não for 5432) | credenciais do **site** (`tiao_web_user`), que só lê | `vault.database.tiao_web_user_pw` em `ansible/inventories/local/group_vars/all/vault.yml` (`ansible-vault view`); host e base são os mesmos do bot |

`PGPORT` e `TIAO_WEB_PGPORT` são lidos direto pela suíte, com `5432` de padrão
— não dependem mais do libpq pegá-los do ambiente por conta própria.

Opcionais, com o valor certo já embutido no código: `TIAO_URL`
(`https://tiao.batistela.tech`), `PANGOLIN_URL` (`https://pangolin.batistela.tech`)
e `TIAO_RESOURCE_ID` (`285`, o id do recurso no Pangolin).

## O limitador de PIN

O Pangolin só aceita **15 tentativas de PIN a cada 15 minutos** por cliente, e
depois disso responde `429` com um `Retry-After`.

Uma rodada inteira gasta **duas** tentativas: a errada e a certa. A fixture
`sessao` é `scope="session"` de propósito — ela autentica uma vez para a suíte
toda. Se algum dia forem precisas mais que duas autenticações por rodada, o
escopo da fixture está errado, não o limitador.

Então um `429` quer dizer que **alguém testou o portão à mão pouco antes** e
gastou a janela. Não é defeito do portão nem da suíte: espere a janela virar e
rode de novo, uma vez só.

A suíte não tenta de novo sozinha, mas também não engole o `429`: ela para na
hora com essa explicação. É que `test_pin_errado_nao_abre` só verifica que o
portão não respondeu `200`, e um `429` também não é `200` — se passasse batido,
uma janela esgotada deixaria esse teste verde sem ter provado nada sobre PIN
errado.

## O comando

```bash
cd apps/tiao-web && .venv/bin/python -m pytest e2e/ -v -s
```

Precisa de `httpx` e `psycopg[binary]` na `.venv`.

Os testes de `tests/` (unitários, sem rede) continuam rodando sozinhos: um
`pytest` sem argumentos só pega `tests/`, porque o `pyproject.toml` fixa
`testpaths = ["tests"]`. A pasta `e2e/` só roda quando pedida pelo nome — sem as
variáveis acima ela nem chega a carregar.

## O teste que manda parar tudo

`test_sem_pin_a_caderneta_nao_abre`. Se ele falhar, a caderneta está aberta na
internet sem PIN. Não é para consertar mais nada antes disso.
