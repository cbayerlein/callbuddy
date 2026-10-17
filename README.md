# CallBuddy — modular, self-hosted telephone assistant

Configured LAN installation: **https://ubuntu-2404-openclaw.fritz.box/callbuddy/**.
See `docs/lan-deployment.md` for the persistent service, HTTPS/CA, provisioned
profiles, cost scope and verified versus still-open live acceptance.
`docs/latency-research-20261015.md` records the new endpointing investigation.

## Architecture and implemented scope

Each person runs their own installation. React/Material UI is presentation,
not a phone client with embedded provider credentials. FastAPI owns settings,
confirmed Memory, preparation, frozen call briefs, results and ordered events.
SQLAlchemy/SQLite persists these records; Alembic installs the schema.

The backend launches an independent guardian and a separate native PJSUA2
endpoint. The guardian owns hangup, pause, DTMF and microphone takeover even
when the model worker stalls. One persistent OpenAI Realtime or Google Live
session bridges native audio. Browser monitoring/takeover uses authenticated
WebRTC; text guidance and private correlated decisions work without a mic.
No incoming calls, automatic redials or replay of uncertain model commands.

Profiles configure SIP domain, registrar, transport, proxy, authentication,
caller identity and prices, as well as model, preparation model, voice,
language and price ceiling. Provider secrets are server-only files with mode
0600. Rotation creates new references so admitted calls retain their snapshot.
Confirmed Memory must be selected explicitly for a brief. AI suggestions are
unconfirmed and never automatically become personal facts.

Research candidates carry a source hash and evidence references. Import does
not qualify them. Automatic model recommendation additionally requires audio
measurements, human listening approval, role/reference checks and an unchanged
approved model profile. No hot swap changes an ongoing call.

## Installation on this host

Source: `workspace/projects/call-assistant`.
Mutable data: `/var/lib/openclaw/state/projects/call-assistant`.
The checked-in `uv.lock` pins Python dependencies. Native PJSUA2 is separately
platform-specific; this host uses the verified CPython 3.12 Linux wheel from
the phone-agent project's `packages/pjsua2` directory. Other installations
must provide a matching native wheel; SIM/Android privileges are not needed.

```sh
UV_PROJECT_ENVIRONMENT=/var/lib/openclaw/state/projects/call-assistant/work/venv uv sync --locked
uv pip install --python /var/lib/openclaw/state/projects/call-assistant/work/venv/bin/python /path/to/pjsua2-compatible-wheel.whl
```

For this workspace, keep the virtual environment and frontend dependencies in
the matching State `work` directory, not a copied source tree. Install exact
frontend dependencies with `node frontend/install.mjs` (using the checked-in
npm lock), then run `node frontend/build.mjs`.
`CALL_ASSISTANT_STATE` selects the State project; `CALL_ASSISTANT_WEB` optionally
selects its compiled `packages/web` directory. Frontend builds typecheck first.

Run with the installed Python interpreter:

```sh
PUBLIC_URL=https://your-approved-host.example PORT=4177 python -m call_assistant
```

Default bind is loopback. `HOST` controls an explicitly chosen LAN bind. Use
HTTPS and a suitable reverse proxy for browser microphone support; HTTP LAN
preview is suitable only for UI inspection, not entry of real credentials.
`PUBLIC_URL` must match the
actual browser origin. The first visit sets this installation's own password.
There is no preconfigured production password and no copied provider account.

## Telephone calls and diagnostics

The app offers telephone calls only, enabled by `CALL_ASSISTANT_LIVE=1`.
There is no product budget limit or tariff-based destination admission. Actual
provider charges still apply. This does not remove separate research spending
authorizations. Calls still require explicit acceptance and never redial automatically.
Text preparation and live audio have independent profile selections. The
operator text default is GPT-6 Luna, independent of the chosen audio provider.
Provider failures, stages and redacted details are saved in the local database
and exposed through authenticated `/api/calls/{id}/diagnostics`.

Both adapters/native transports are implemented, not yet qualified end to
end in this product. Remaining live acceptance covers provider billing/usage
semantics, first-audio latency, pronunciation, interruptions and final audio,
TLS/registrar behaviour, browser monitor/mic and independent cleanup evidence.
The registrar's unregister acknowledgement plus local closure is not proof
of remote audio or an independent provider query. Estimated cost is not an
invoice. Missing usage does not interrupt calls; uncertain effects never redial.

The new implementation has no deterministic hearing/reference correctness
guarantee. Prompt checks and future candidate imports cannot substitute for
independent audio/code-order checks. Existing research evidence remains
separate and unchanged; no historical acceptance is inherited automatically.

## Focused verification

```sh
python -m compileall -q src
python -m pytest -q
node --check frontend/build.mjs
node frontend/build.mjs
```

`tests/personal_setup_probe.cjs` checks the existing shared browser task tab.
It never creates/disposes a browser context or calls a telephone number.

See `NOTICE` for original AnrufBot attribution. No remote repository writes,
commits, Gateway restarts or paid acceptance calls are part of this setup.
