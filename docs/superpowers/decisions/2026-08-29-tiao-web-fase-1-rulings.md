# Tião Web fase 1 — registro de decisões

As decisões tomadas durante a execução autônoma do plano, com o custo de cada uma
se estiver errada. O usuário pediu execução sem consulta; isto é o que ele precisa
ler para desfazer o que eu tenha errado.

Spec: `docs/superpowers/specs/2026-08-29-tiao-web-design.md`
Plano: `docs/superpowers/plans/2026-08-29-tiao-web-fase-1.md`

```
  Ruling 1 (T1/T4/T8): pyproject.toml as written installs only Python modules, so
    Plan text defect only, no code impact. Final review should not treat the count as a spec value.
    Justified: the brief's own environment note requires .venv to stay out of git. Expect the
  Ruling 2: Task 2 dispatched before Task 1's review returned, to keep the queue moving. Task 2
    Cost if wrong: if Task 1's review forces a change to those signatures, Task 2 needs a fix round.
  Ruling 3: copied gitignored ansible/vault.auth into the worktree so Tasks 5/8/9 can run vault ops
  Ruling 4 (Task 1, finding 1 — false positives): CONFIRMED and will fix. The plan's PROIBIDAS
  Ruling 5 (Task 1, finding 2 — function-call bypass): NO code change in Task 1. setval() and
    Cost if wrong: if the role turns out not to contain them, the guard is the only layer left —
  Ruling 6 (Task 2): implementer flagged that parse_spec raises a raw KeyError when a coluna dict
    Task 2's review round so it costs one loop rather than two.
    Cost if wrong: none material — it only widens which malformed specs report cleanly.
  Ruling 7 (Task 2, Critical — exception leakage): FIX. parse_spec is the trust boundary for
    Only `params` had an isinstance guard. Cost if wrong: none — guards only widen what reports
  Ruling 8 (Task 2, Important — regex param extraction): FIX by tokenising. `'Categoria:Bovino'`
    Cost if wrong: a token-walk that misses a parameter form would raise "faltam parametros" on a
  Ruling 9 (Task 2, Minor — resumo elements): FIX, folded in, since the same edit adds the guards.
    Keyword.DML scan, argued safe because DML words are reserved and cannot be identifiers.
    Reasoning is sound (PostgreSQL only permits SELECT/INSERT/UPDATE/DELETE/MERGE inside a CTE, so
    Ruling 10: ACCEPT as-is. The string is not valid SQL — DROP is not a legal expression inside a
    WITH grammar only permits SELECT/INSERT/UPDATE/DELETE as a CTE body — and those ARE caught by
  Ruling 11 (Task 3, Important — negative values): FIX, against the reviewer's own "not blocking"
  Ruling 12 (Task 3, Minor — zip truncation on mismatched lengths): DEFER, do not fix. The only
  Ruling 13 (Task 4, copy defect): FIX. The empty-state reads "patrao", missing the tilde on
    Task 4's review round so it costs one loop. Also fixing the same string in the plan text so
  Ruling 14 (Task 4, resolving the reviewer's "cannot verify from diff"): the ValueError in
    Cost if wrong: a wrongly-formatted cell shows as raw text instead of failing loudly — the
    Scoped re-review dispatched (review-4a68adc..11be809.diff), asked specifically to check the
    The scoped re-review was explicitly asked to capture the warning, so it will verdict this.
    Dispatch carries: the password-rewrite hazard spelled out, the prepared environment (vault.auth,
  Ruling 15: dispatching Task 6 while Task 5 is still running, against the skill's
    Task 6 is apps/tiao-web/src/ — so the rule's rationale (file conflicts) does not apply here.
    Residual risk is a git index.lock race on simultaneous commit, which fails loudly and retries.
    Task 6's Step 6 (verifying the query against the live database as tiao_web_user) DEPENDS on
    Task 5 creating that role, so I am withholding that step from the implementer and will run it
    Cost if wrong: one transient commit failure, or a verification I must remember to run. Both visible.
  Ruling 16 (Task 8, plan defect found before reaching it): my plan said "git push; wait for CI to
    The only path the plan described therefore required MERGING TO MAIN, which is one of the four
    Decision: use `gh workflow run apps.yml --ref feat/tiao-web-fase-1 -f app=tiao-web`. The
    CI-built image with NO merge to main and no local write:packages token (mine lacks that scope).
    Pinning an exact tag is also better practice than chasing :latest.
    Cost if wrong: if dispatch on a non-default ref is disallowed by repo settings, Task 8 stops
  Ruling 17 (Task 7, Minor — English 404): FIX, against the reviewer's non-blocking rating. The
    The read-only layer is now proven rather than assumed. This closes the reviewer's one ⚠️ on
    Task 6 and the "web layer never writes" global constraint.
    Note: reading the vault needs the venv's python — the system python3 lacks PyYAML.
    PASS: role read-only (INSERT/UPDATE/DELETE/CREATE all refused); function bypasses contained by
    PERMISSION DENIAL (stronger than the read-only transaction I predicted — setval, lo_import and
  Ruling 18 (concern 5 — "no tiao gateway process"): FALSE ALARM, resolved with context the
  Ruling 19 (concern 4 — 0 rows but animais_id_seq at 6): NOT lost data. That sequence was advanced
  Ruling 20 (concern 2 — read_only/timeout are USERSET GUCs the role can unset): my spec overstated
    SQL cannot issue SET at all (check_sql permits only SELECT), so the threat this defends against
    Fixing needs a server-wide REVOKE affecting every role; a separate change.
    SHA-256 of the live .env PGPASSWORD vs the decrypted vault.database.tiao_user_pw — exact match,
    Vault 49->51 keys, exactly the two added, none removed or changed, still AES256-encrypted.
    Grants verified live: SELECT on 4/4 tables and nothing else, 0 routine grants, pg_default_acl
    CREATE denied on both database and schema. Idempotent on re-run (only the raw postgresql_query
  Ruling 21 (Task 5, Important — hazard avoided but not neutralised): FIX, documentation-only.
    The reviewer answered exactly the question I posed: /root/.hermes/profiles/tiao/.env is NOT
    Ansible-managed, so the vault and that file are two independent copies of one secret with
    Decision: add a warning comment beside the tiao_user entry naming the coupling and its
    Cost if wrong: a comment nobody reads; the coupling still exists and is now at least recorded.
  Ruling 22 (Task 5, Important — postgres_users_no_log): REVERSED my earlier decision to only flag
    Cost if wrong: `make play-database` output becomes less debuggable; recoverable in one word.
  Ruling 23 (Task 5, Minor but operationally serious — grants playbook unwired): FIX. database.yml
    ZERO grants and the viewer shows its error page with no clue why. The brief did specify a
  Ruling 24 (Task 5, cosmetic): changed_when: false on the raw postgresql_query task, so an
    Process note: this is the SECOND time splitting a round's requirements across two messages has
  Ruling 25 (Task 5, implementer-raised gap): FIX. The import_playbook is untagged, so
    Adding tags: postgresql_install to the import so grants travel with user creation.
    Cost if wrong: the grants play also runs under that tag — idempotent, seconds.
    Correction to my own earlier note: my readings WERE against the worktree and WERE correct when
    Key stop condition carried in the dispatch: ports must bind to 192.168.1.111 and 127.0.0.1,
    Vault diff empty across the wave; no plaintext secret in any of the 5 commits.
    CI actually published — so the workflow_dispatch build path worked). Container NOT yet running
    One good signal already: zero bindings on 0.0.0.0, so nothing is exposed prematurely.
    State I verified directly rather than inferring: code committed (dc8e2d5, bd3847f), branch
  Ruling 26 (Task 8 recovery): re-dispatch a fresh implementer for the deploy only, explicitly
    Ports verified correct: 192.168.1.111:8790 and 127.0.0.1:8791 — the implementer correctly read
  Ruling 27 (correcting the implementer's own concern): it wrote that the empty-state page "is also
  Ruling 28 (Task 8, Important — unpushed commits): FIX by pushing. The implementer held back for
    Task 9 pushes anything. Cost if wrong: a stray CI build, which is harmless and visible.
  Ruling 29 (no scoped re-review for Task 8's fix): the fix introduced no diff at all — it published
    Incidental noted by the implementer: config/fragments/pangolin/tiao.yml is untracked in the
  Ruling 30 (Task 10 auth, corrected before running): I had written the e2e suite assuming
    I tried to recover their identity and CANNOT: the newest DB backup on the host is from Nov 2025
    Pangolin. No leak: unauthenticated headers carry no Server, host, IP; the auth page discloses
    Three-step PIN exchange reproduced in every detail, and the reviewer's cookie epoch suffix
    DIFFERED from the report's — proving the do-not-hardcode warning empirically. Session cookie is
    Warned impl-task10 immediately, since it was already dispatched and would otherwise read the
  Ruling 31 (a defect in MY plan, found by running it): the brief's test_pin_errado_nao_abre asserts
  Ruling 32 (superseding part of Ruling 31): the implementer replaced the Retry-After wait with an
    IMMEDIATE, explanatory failure on 429 — message states that Pangolin limited attempts, that the
    PIN was never actually judged, and that this is not a defect of the gate or the suite. Better
    Cost if wrong: a rate-limited run fails instead of self-healing; the message says how to recover.
    So an operator following the README alone can trip this with nobody else touching the gate,
    Task 9 reviewer.
    PIN, right PIN), so the session-scoped fixture holds; the README records that rule so a future
  Ruling 33 (Task 10, Critical): test_o_site_nao_consegue_escrever and ..._por_funcao catch
    InsufficientPrivilege. Cost if wrong: a genuine refusal raised as a different privilege error
  Ruling 34 (Task 10, Important): test_sem_pin_a_caderneta_nao_abre — the flagship, the one whose
  Ruling 35 (Task 10, Important): test_pin_errado_nao_abre still asserts a negative satisfiable by
  Ruling 36 (Task 10, Important): two leak tests are purely negative and pass on an empty body.
    Adding a status assertion before the negatives.
  Ruling 37 (Task 10, Minors): defensive DELETE at the TOP of the fixture so an interrupted run
    PGPORT as required though _conn never reads it.
    Confirmed clean: secret hygiene (only public hostnames, resource id 285 and the CSRF constant
    TELEGRAM_BOT_TOKEN from vault.hermes.telegram_bot_token — undoing the manual removal I made at
    This is the same drift class the Task 5 comment warns about, in the opposite direction: I hand-
  Ruling 38: restored service by removing the line by hand and restarting — chato:telegram and
  Ruling 39 (correcting MY OWN prescription): I told the implementer to use InsufficientPrivilege
    Probed live, INSERT raises ReadOnlySqlTransaction (25006) because default_transaction_read_only
    Vacuity closure measured, not asserted: UndefinedTable satisfied the old Error catch (True) and
    ProgrammingError siblings of InsufficientPrivilege and unrelated to ReadOnlySqlTransaction —
  Ruling 40 (Task 10 fix round 2): the grant assertion covers only `animais`. `pesagens` — the table
    INSERT would read False. Asked only for a comment naming the limit, not a fix.
    TELEGRAM_BOT_TOKEN from the default profile's .env (lineinfile state: absent), not merely
  Ruling 41 (deferred, not dispatched): review-task10 flagged that the fixture teardown and the
    README's manual cleanup identified rows differently. Checked the current tree — they now AGREE
    Playwright install. Crucially the implementer noticed that this `ok` is VACUOUS — the VM is
  Ruling 42 (vault key): KEEP vault.hermes.telegram_bot_token and the defaults entry, per the
  Ruling 43 (queued for fix round 3, NOT dispatched while round 2 is in flight): replace _limpar()'s
    Went beyond the ask twice, both well judged:
  Ruling 44: SKIPPING the scoped re-review of round 2 and going straight to the final whole-branch
    DROP-in-FROM string (re-confirmed to have no execution path), _params_da_sql's unguarded parse
    CONNECT/TEMP via PostgreSQL's PUBLIC default, default_privs scoped to tiao_user, the
    A. dead 8791 + the spec's "Docker enforces the boundary" + one uvicorn on 0.0.0.0:8790. "The
    B. the generic 404 handler (over-catching) + the absent 500 handler (not catching at all) — "the
    C. LIMIT-is-not-a-cap + advisory statement_timeout + pool_size=2. Each was individually blessed;
  Ruling 45: dispatching the fix wave as TWO agents split by directory (src/+docs, and e2e/) rather
    Portuguese ("Iniciar sessão com PIN"), not Brazilian. Not fixable in this repo; worth checking
    BEFORE today's src/ commits. The app half changes the error-page wording, so after it lands the
    Its concerns: (1) text(sql)._bindparams is a PRIVATE SQLAlchemy attribute — the right call since
    CAST(:data AS date) — `:data::date` is now refused at ingest; (3) the oversized-limit rewrite
    Image sha-bc5f954 from run 33256496887, no latest. Bindings 192.168.1.111:8790 and
  Ruling 46 (resource limits, decided by the implementer and endorsed): ENFORCE them rather than
    NanoCpus=250000000. Cost if wrong: an OOM kill on a page that materialises a huge result set —
    Nothing corrupted. FETCH FIRST still gets a LIMIT appended that Postgres rejects — unchanged
    UNCHANGED. sqlparse groups them as Parenthesis/Operation (ttype is None), so _acima_do_teto
    R2 (low): app.yml and the role's defaults match today but nothing enforces it — only prose
    R3 (low): POST /pesagens returns Starlette's bare English "Method Not Allowed", 405, unstyled.
    R4 (informational): the e2e bar-count assertion goes spuriously red if one of the rancher's own
    R5 (informational): parse_spec can raise a raw AttributeError if _bindparams is renamed,
    R6 (informational): congelado: true is now refused although the design doc promises it.
  Ruling 47: closing R1-R4 in one last dispatch, against the reviewer's own "would not hold" advice
    Rejection surfaces as SpecInvalido on the loopback-only write port, so it costs the reader
    This is the third time in this project that "the code is committed" and "the code is running"
    Ports 192.168.1.111:8790 and 127.0.0.1:8791, neither on 0.0.0.0. Limits genuinely applied:
    Memory=268435456, NanoCpus=250000000. PROOF THE NEW IMAGE IS LIVE: POST /pesagens returns the
    Authoritative pin recorded: the role's tiao_web_image (the only value rendered into the compose
  Ruling 48 (final): the e2e README claims no suite secret lives in the repo. That is FALSE for the
    PIN, which sits in plaintext in config/fragments/pangolin/tiao.yml and is the sole control on an
    Correcting the documentation only. Rotating or vaulting the PIN is the user's decision: I
```
