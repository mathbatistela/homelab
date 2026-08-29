# Testes de ponta a ponta — caderneta do Seu Jader

Estes testes **não usam dublê nenhum**. Eles falam com o banco de verdade
(`tiao_database`) e com a URL pública de verdade (`https://tiao.batistela.tech`),
passando pelo PIN do Pangolin, pelo túnel e pelo contêiner na VM `hermes`.

Não existe `TestClient` aqui, e nada aponta para `localhost`. Se o Pangolin, o
túnel ou o contêiner estiverem fora do ar, estes testes falham — é exatamente
para isso que eles existem.

## Antes de rodar

**Não rode durante a pesagem.** A suíte escreve quatro animais de mentira
(`e2e-901` a `e2e-904`), as pesagens do dia deles e mais uma pesagem de ontem
para o `e2e-901` — é ela que prova que cada dia mostra o peso daquele dia. Apaga
tudo no fim. A limpeza roda também **antes** de semear, então uma rodada
interrompida se conserta sozinha na rodada seguinte. Mas até lá as linhas ficam
na caderneta do Seu Jader, e se ninguém for rodar a suíte de novo tão cedo,
apague à mão:

```sql
DELETE FROM pesagens WHERE animal_id IN (
  SELECT id FROM animais
  WHERE brinco IN ('e2e-901', 'e2e-902', 'e2e-903', 'e2e-904', 'e2e-909-sonda')
);
DELETE FROM animais
WHERE brinco IN ('e2e-901', 'e2e-902', 'e2e-903', 'e2e-904', 'e2e-909-sonda');
```

Os brincos vão nomeados um a um, aqui e no `_limpar()` da suíte. Um `LIKE
'e2e-90%'` faria a mesma coisa hoje e é um `DELETE` com curinga rodando como o
bot, nas tabelas de verdade: bastaria alguém apertar o padrão, ou um animal do
Seu Jader ganhar um brinco parecido, para as linhas dele irem junto sem ninguém
perceber. A lista exata não tem esse jeito de dar errado.

O `e2e-909-sonda` nunca chega a ser gravado — ele é o `INSERT` que
`test_o_bot_continua_dono_da_caderneta` faz e desfaz com `ROLLBACK` para provar
que o bot ainda escreve. Está na lista só para o caso de um `ROLLBACK` falhar.

## Variáveis de ambiente

Quem roda a suíte junta os valores na hora e os passa pelo ambiente — nunca por
arquivo versionado. Isso vale para as duas credenciais de banco: elas moram
fora deste repositório, uma no `.env` da VM, outra cofrada com
`ansible-vault`.

**Não vale para o PIN.** `TIAO_PIN` está commitado em texto puro em
`config/fragments/pangolin/tiao.yml`, em `auth.pincode` — não há indireção de
vault ali. Ele está no histórico do git, então trocá-lo é um commit novo, e
qualquer um com acesso ao repositório tem a página. Foi decisão, não descuido:
um `{{ vault.* }}` ali foi considerado e rejeitado porque `make
play-pangolin` carrega o inventário local **e** o da nuvem, cada um com seu
próprio `group_vars/all/vault.yml` cifrado, e o comportamento padrão do
Ansible para merge de hash (`replace`) faz uma chave `vault` de nível
superior num deles sobrescrever silenciosamente a do outro — vale revisitar
essa escolha. É por isso que o limitador de tentativas do Pangolin (abaixo)
não é só conveniência: é ele que segura a porta enquanto o PIN estiver em
texto puro no repositório.

| Variável | O que é | De onde vem |
| --- | --- | --- |
| `TIAO_PIN` | o PIN da borda | commitado em texto puro em `config/fragments/pangolin/tiao.yml`, em `auth.pincode` — **não** está fora do repositório |
| `PGHOST`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | credenciais do **bot** (`tiao_user`), que escreve | `/root/.hermes/profiles/tiao/.env` na VM `hermes` (`root@hermes-vm.local.batistela.tech`) — fora do repositório |
| `TIAO_WEB_PGHOST`, `TIAO_WEB_PGDATABASE`, `TIAO_WEB_PGUSER`, `TIAO_WEB_PGPASSWORD` | credenciais do **site** (`tiao_web_user`), que só lê | `vault.database.tiao_web_user_pw` em `ansible/inventories/local/group_vars/all/vault.yml` (`ansible-vault view`) — fora do repositório; host e base são os mesmos do bot |

**Opcionais.** `PGPORT` e `TIAO_WEB_PGPORT` só são precisos se o Postgres não
estiver na 5432: a suíte lê os dois direto, com `5432` de padrão, em vez de
depender do libpq pegá-los do ambiente sozinho. Também já vêm com o valor certo
embutido: `TIAO_URL` (`https://tiao.batistela.tech`), `PANGOLIN_URL`
(`https://pangolin.batistela.tech`) e `TIAO_RESOURCE_ID` (`285`, o id do recurso
no Pangolin).

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

## Isto **não** entra no CI de cada push

A suíte é para ser rodada **à mão**, quando alguém quer saber se a caderneta
ainda está de pé: antes de um deploy, depois de mexer no Pangolin, ao investigar
uma reclamação. Não é para rodar sozinha a cada push, nem em cron, nem em pull
request.

O motivo é o limitador acima. Ele conta por cliente, e o cliente é o IP: uma
rodada do CI gasta duas das quinze tentativas da janela, e vários pushes na
mesma tarde esgotam a janela inteira. **Quando isso acontece, quem fica de fora
é o Seu Jader** — ele abre o link no curral, digita o PIN certo, e o portão
responde `429` por quinze minutos por causa de um push que ele nem sabe que
existiu. A caderneta dele é o que a suíte deveria proteger; um CI ligado nela é
a suíte derrubando o que veio guardar.

Some-se a isso que ela escreve na caderneta de verdade — durante uma pesagem, os
animais de mentira aparecem na página que ele está olhando.

O que roda sozinho é `tests/`: unitário, sem rede, sem banco, sem PIN.

## A SQL daqui é uma cópia — e a original não mora neste repositório

O `INSERT` que a fixture usa para semear é uma transcrição à mão do que o bot
faz de verdade. O original está na skill do Tião, **na VM `hermes`**, fora deste
repositório:

```
root@hermes-vm.local.batistela.tech:/root/.hermes/profiles/tiao/skills/tiao-gado/SKILL.md
```

São os blocos `INSERT INTO animais ... ON CONFLICT (brinco)` e `INSERT INTO
pesagens ... ON CONFLICT (animal_id, data)` de lá.

**Os dois têm que ser mudados juntos.** Se a skill ganhar uma coluna, trocar o
alvo do `ON CONFLICT` ou passar a gravar por outro caminho, esta suíte continua
verde: ela testa a página contra a cópia envelhecida dela mesma, não contra o
que o bot escreve. Nenhum teste pega isso — não há como, daqui, comparar com um
arquivo que vive em outra máquina. É por isso que está escrito aqui.

Quem mexer na `tiao-gado/SKILL.md` mexe também no `caderneta()` de
`test_fluxos_reais.py`, e vice-versa.

## Um teste precisa da rede da fazenda

`test_as_portas_estao_onde_o_plano_mandou` abre socket direto na VM
(`192.168.1.111:8790` tem que atender, `8791` não) em vez de passar pelo túnel.
Rodando de fora da LAN ele falha dizendo isso. Os endereços e as portas saem de
`TIAO_LAN_IP`, `TIAO_PORTA_LEITURA` e `TIAO_PORTA_ESCRITA`, todos com o valor
certo já embutido.

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
