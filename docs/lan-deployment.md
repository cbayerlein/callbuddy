# Configured LAN deployment — 2026-10-15

## Entry point

https://ubuntu-2404-openclaw.fritz.box/callbuddy/

Apache's existing HTTPS vhost includes
`/etc/apache2/conf-available/callbuddy-route.conf` before the gateway catch-all.
The fragment is versioned in `deploy/callbuddy-apache.conf`. It strips the
`/callbuddy/` prefix when proxying; the frontend uses relative asset/API URLs.
The existing FRITZ BOX Internal Root CA certificate chain and renewal-managed
leaf certificate are reused. No browser TLS bypass, new CA, public DNS entry,
extra external listener or OpenClaw Gateway restart is required.

The backend is the enabled system service `callbuddy.service`, versioned in
`deploy/callbuddy.service`, bound only to `127.0.0.1:4177`. It uses the canonical
State database and credentials. Start/reboot durability does not depend on a
chat-owned terminal. The old plain HTTP LAN listener is no longer exposed.

## Personal provisioning

`python -m call_assistant.provision` accepts paths, never secret values, for the
Chat-V2 password handoff, credential root, State root and a fresh SQLite backup.
It stores only a salted scrypt password hash, creates versioned server-only
credential references and sets the existing Fonial and OpenAI profiles as
defaults. Do not rerun casually: it resets the operator password and defaults.
The supplied handoff remains private under its existing Chat-V2 owner.

The Fonial registration identity is the SIP account username, NOT the public
telephone number. The latter is kept as the user's callback number. The
individual outbound proxy is `sbc.sip.plusnet.de`. System resolvers enable SIP
SRV discovery, automatic registration retries are disabled, and native audio
ports are released before PJSUA2 teardown.

OpenAI uses the existing account, `gpt-realtime-2.1`, `marin`, German and
`gpt-4.1-mini` for preparation. The conservative model accounting ceiling is
EUR 100 per million tokens, not a claim that all tokens have that tariff.
The official model page lists audio output at USD 64/M; the application uses a
deliberately higher accounting ceiling rather than an invented exact EUR rate.

An additional Google profile is now configured with `gemini-3.8-live`, `Kore`
and `gemini-3.8-flash` for preparation. The existing AI Studio credential was
imported through the authorized shared browser; both model entitlements were
confirmed. OpenAI remains the default. Each profile card displays its preparation
model. The SIP card displays the separately stored public phone-number mapping.
See `gemini-and-turn-pilot-20261015.md` for checks and remaining live limitations.

The Fonial standard German tariff ceiling is EUR 0.119/minute including VAT,
covering the published mobile rate (landline is EUR 0.0119/minute). No discount
or internal-route free-call assumption is used. The configured profile is
limited to German geographic/mobile destinations; unpriced foreign and special
numbers are rejected before dispatch. Configure their applicable tariff in
another profile before using them. Source:
https://www.fonial.de/telefonanlage/preise/ (retrieved 2026-10-15).

Initial per-call budget remains EUR 2 and recording remains off. Live mode is
available only after the user prepares and accepts a brief and explicitly
chooses Live/Now call. Enabling the application is not permission for autonomous
research calls and does not transfer the research budget to this product.

## Verified scope and limitations

- HTTPS frontend/backend, trusted CA validation without `-k`, authenticated
  shared-browser access, secure/HttpOnly session cookie, secure context and
  media-device API availability.
- Personal settings and both credential-bearing profiles, without returning
  secret values or credential references to the browser.
- OpenAI model entitlement by read-only metadata GET, not a paid audio session.
- Real Fonial REGISTER 200 and unregister 200 on the corrected product endpoint;
  an independent authenticated non-binding query then found zero contacts.
- Zero dials and zero model audio sessions in these setup probes.
- Native library import, focused unit tests and frontend typecheck/build.

The first probe failed and crashed during cleanup; it was not called a success.
An independent zero-contact query preceded the corrected probe. No automatic
redial or historical research dispatch was performed. The corrected successful
probe is in State `results/account-preflight-20261015-corrected.json`.

This verifies configured access and registration, not a successful end-to-end
telephone conversation, remote audio quality, model billing, microphone sound,
private-decision recovery or the one-second latency target. The product's
remaining live qualification is still explicitly open. Browser microphone
permission must be granted on the actual client if takeover is used.

Database and Apache backups are under the matching State backup category,
`backups/call-assistant/2026-10-15/`. Source changes remain uncommitted until
Chris requests a commit/push.
