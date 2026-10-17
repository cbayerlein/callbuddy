# SIP audio repair and bounded product acceptance

## Outcome

The SIP audio defect is repaired. Local two-process audio and both Fonial call
directions passed independent receive-side signal checks. The final backend
candidate passed three consecutive Gemini conversations with unknown spoken
codes and an OpenAI conversation with an unknown spoken word. Both sides have
transcripts and the peer's independent RX recording contains the answer.

This is not an all-model semantic qualification: OpenAI consistently reordered
the German numeric reference 59 into 95 or omitted the requested numeric answer.
Those runs remain failed. The additional word test establishes audio transport
and a successful simple speech exchange, not a repair of numeric reasoning.

## Causes and changes

1. **Borrowed SWIG media storage:** `getInfo().media` was iterated after the
   temporary `CallInfo` owner had been destroyed. Local run 02 recorded invalid
   media type/index/status values and zero callbacks at the audio ports. Keeping
   `info = getInfo()` alive throughout iteration and attachment made local run
   03 pass in both directions. The research endpoint already retained this owner.
2. **SDP NAT rewriting:** after the bridge repair, Fonial internal run 03 connected
   but delivered no test signal. Enabling `sdpNatRewriteUse=1` made run 04 pass;
   reverse run 05 passed too, with independent tones and zero observed RX loss.
3. **Real-time draining:** the native IPC loop no longer adds the former long
   polling delay. Readers catch up queued frames instead of continually adding
   a 20-ms sleep. Early media is drained while ringing, preventing ringback from
   overflowing the capture queue before answer. The first connected frame is
   retained for the model.
4. **False spoken completion:** OpenAI sometimes returned only `finish_call`, or
   spoke a promise to answer while recording an answer privately. The tool now
   explicitly documents that its result is private. OpenAI cannot finish its
   first response before producing audio, but can still ask the user privately.
   A no-audio finish is rejected once; an unexecuted OpenAI result is removed
   before requesting an audio-only correction. Repeated silent completion fails.
   These guards do not establish reference correctness; the independent audio
   check retained the 59/95 failures.

## Product diagnostics and states

- Native journals retain call status, media callback observations, codec,
  attachment errors and timestamps without authorization headers or full SIP
  packets. Frame/voice counters, queue depth and bounded RTP counters are exposed.
- Calls retain `audio_state` (`checking`, `ready`, `failed`) and `audio_health`,
  including model input voice frames and generated output sample counts.
- Telephone connection and audio activation are separate UI facts. Five seconds
  without activation causes a media-specific failure and cleanup. Silence alone
  is not an error. Loss before confirmed activation cannot become a successful
  call just because the far end hung up.
- First-seen OpenAI event names and response item types are logged without audio
  payloads or secrets. Existing authenticated diagnosis and transcript endpoints
  remain the investigation entry points; no manual JSON attachment is needed.

## Actual acceptance route and isolation

The two Fonial public numbers did not terminate at the controlled endpoints in
the first two runs. Existing project evidence documents provider-internal target
IDs Claudia=2 and Zoiper=1. Subsequent controlled calls used those targets through
Fonial, not loopback and not an independently qualified public PSTN destination.
No provider routing was changed. Normal product E.164 dialing is unchanged.

The test runner starts a second product-native endpoint, accepting only the
expected number/internal identity for 90 seconds. Each run has an exclusive fresh
artifact root, short Unix-socket paths, a lease, deadline and cleanup receipts.
The internal route override is constructor/config injection only: public API
requests cannot enable it. Production still rejects unsolicited inbound calls.

Full model calls used the real preparation/accept/start API, persistent database,
guardian, native endpoint and provider adapter in isolated test application State.
They reused protected credential references; they did not insert test histories
into Chris's production database or change model/profile defaults.

German question recordings contain the challenge; the caller brief never does.
The peer receives/captures the actual RTP audio. Its recording is transcribed
without an expected-answer prompt in a separate transcription request. An early
fixture generator produced only a number, not the complete question; those runs
failed and were not qualified. Complete fixtures were checked before dispatch.

## Final evidence

All paths below are internal under State `projects/call-assistant/`.

| Gate | Evidence | Result |
|---|---|---|
| Local independent tones | `work/media-runs/sip-audio-local-03/` and native regression runs | Passed |
| Fonial forward / reverse | `work/media-runs/sip-audio-fonial-04/`, `sip-audio-fonial-05/` | Passed |
| Gemini code 47 | `sip-app-google-06`, call `e8cbe9fb1c26bd1bae598c02` | Spoken 47 confirmed |
| Gemini code 63 | `sip-app-google-07`, call `7e4a08b4370a3908270cf32e` | Spoken 63 confirmed |
| Gemini code 82 | `sip-app-google-08`, call `3b2a9b687c31a1d194bd8e18` | Spoken 82 confirmed |
| OpenAI word Ananas | `sip-app-openai-word-01`, call `d65a980b49a3b2516c93c52b` | Word confirmed |
| OpenAI numeric reference | `sip-app-openai-01` through `sip-app-openai-06` | Failed; preserved |
| Offline regression | `results/sip-audio-repair-tests.xml` | 44 passed |
| TypeScript / frontend | `results/sip-audio-repair-build.log` | Passed |
| Shared browser, real completed history | `work/media-runs/sip-ui-proof-01/` | Desktop/mobile, transcript, keyboard diagnostics passed |

The three final Gemini calls have status `completed`, closed model connections
and registrar-acknowledged cleanup. After all live tests, independent authenticated
non-binding queries across all registrar SRV targets returned zero contacts for
both identities. No model or native test processes are retained.

The shared browser's existing persistent context was reused; only the task tab
was opened/closed. The temporary read-only UI server used the actual isolated
acceptance history with call dispatch disabled. Production was restarted only
after checking there was no active user call. The OpenClaw gateway was not restarted.

## Reproduction and limits

Run `python -m call_assistant.audio_acceptance --run-root <fresh-root>` for the
provider-free native check. `--fonial` and optional `--reverse` perform live calls
only with explicit destination authority. `app_audio_acceptance` performs one real
API/model call and independent audio transcription; never replay a used run root.
The frozen pytest suite does not register or dial outside the local machine.

No provider invoice was retrieved. Product calls remain unlimited as requested;
research authorization and its ledger were not changed by this implementation.
Accent, broader semantic reliability, long-call qualification and an additional
external public-PSTN destination are not qualified by these tests.
