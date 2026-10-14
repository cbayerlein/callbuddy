# Implementation checkpoint — 2026-10-14

## Verified

- Separate source/State application; no changes to the sister repository or
  phone-agent research source, credentials or budget ledger.
- Backend compilation and 24/24 focused tests passed. JUnit:
  State `results/backend-final.xml`.
- PJSUA2's installed PCM16 ByteVector conversion passed without registration.
- Real local aiortc peer negotiation received audio frames and closed both
  peers. This is local demo silence, not telephone/audio-quality acceptance.
- Locked frontend install, TypeScript and Vite build passed.
- Shared Host Browser exercised preparation, saved call recovery on reload,
  a private decision submitted using the keyboard, 390px mobile layout,
  authenticated transcript export and dark-theme settings.
- Desktop/mobile screenshots inspected. A light research card in dark mode
  was corrected through actual MUI theme variables, then inspected again.
- Early demo hangup cannot be resurrected; cancellation also blocks native
  dialing. Persistent model setup precedes dialing. Final output must drain
  before model-requested closure. These latter live contracts still need
  independent provider acceptance, not just implementation/source proof.

Evidence is in the matching State project's `results` and
`work/media-runs/ui-acceptance-20261014` with an explicit retention record.
No test credentials are installed in the normal application database.

## Running preview

The normal application is available on LAN port 4177, using its canonical
State root, with `live_enabled=false` and initial access setup still required.
The HTTP address is for demo/keyboard inspection only. Do not enter actual
provider credentials there. The temporary browser acceptance fixture uses
port 4178 and a separate database; it is stopped after acceptance.

## Open production gates

1. An approved HTTPS deployment origin and browser microphone permission.
   The current browser policy permits the Fritz hostname, but not the
   allocated Portal hostname. No browser-policy override was made.
2. Explicit provider credentials, tariffs, approved test destinations and
   a separate bounded acceptance budget for this product. The research
   runner's existing budget is not silently reused.
3. Both provider usage semantics, independent speech listening/reference
   checks, interruption/truncation consistency, latency, monitor/microphone
   takeover, TLS/registrar and process-failure cleanup qualification.
4. No accent-free voice, successful reservation, correct hearing, provider
   invoice or complete production qualification is claimed by these tests.

This is an implemented and tested product candidate, not a completed live
release. Research candidates remain opt-in and their evidence is not
automatically inherited by the new runtime.
