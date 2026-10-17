# Gemini configuration and bounded endpointing pilot — 2026-10-15

## Product changes

The configured Fonial SIP profile now exposes a separate `phone_number` field.
It is display metadata from the authorized account record, not a provider-side
number assignment or a replacement for the SIP registration identity. The UI
also labels `caller_id` as the SIP sender identity so the two are not confused.

The existing Default Gemini API Key was imported through the authorized shared
Host Browser into a mode-0600 credential file, then referenced by the server-only
profile store. No new key, billing account or Cloud project was created, no
clipboard was used, and no secret was printed. Existing key restrictions were
not changed because the key may serve other applications. The temporary AI
Studio tab was closed after import; the shared browser service was preserved.

The additional profile uses `gemini-3.8-live`, German, voice `Kore`, and
`gemini-3.8-flash` for optional AI preparation. Both models were present in the
authenticated paginated model catalogue and passed metadata access checks.
OpenAI remains the default, with `gpt-4.1-mini` for its preparation requests.
Rule-based task questions remain available without an LLM request. Changing
the selected call model profile also selects its configured preparation model.

The Google accounting ceiling is EUR 100/M tokens, deliberately conservative,
not an assertion of the provider's actual EUR tariff. The official Google price
page retrieved through an HTTP client (the generic fetch redirect limit failed)
listed Gemini 3.8 Live audio input USD 3/M and output USD 12/M. Source:
https://ai.google.dev/gemini-api/docs/pricing?hl=en . No grounding tool was enabled.
There were no model audio sessions or dials in these account checks.

Steering source inspection confirms private instruction commands and model
delivery, private `ask_user` decisions/function responses, pause/resume/hangup,
monitoring and microphone takeover. A delivery receipt is not evidence that a
model followed the instruction. Full live product qualification remains open.

31 focused backend tests, the frontend typecheck/build and an authenticated
shared-browser probe passed, including both credential-bearing profiles and
the displayed phone mapping. The browser is a secure HTTPS context. Neither
this setup nor offline source proof qualifies provider audio/billing behavior.

## First endpoint detector screening

The pilot is isolated from the product runtime and phone-agent research source.
No historical source, sealed evidence or budget reservation was changed.
Its entry point is `tests/turn_detector_pilot.py`; results are in the matching
State project at `results/turn-detector-pilot-20261015.json`.

The existing RunPod CPU worker supports only environment inspection and a
synthetic CPU/RAM probe, not arbitrary model inference. Rather than deploy a new
worker for sixteen short predictions, this bounded development smoke used a
separate local environment with CUDA disabled, native thread counts set to one,
nice 10, ionice 2:7 and a 120-second process deadline. Larger evaluation remains
a RunPod task. No RunPod capacity or paid model generation was activated.

Frozen inputs were four complete playback spans from the existing restaurant
recording, with both caller and restaurant represented. Each supplied one final
pause and one internal pause, producing eight causal input prefixes. Final
prefixes retained the full original playback and appended 250 ms of silence;
existing trailing silence therefore makes final action delays 650–830 ms.
Internal predictions used only audio available 250 ms after the pause began.
The largest qualifying internal pause per turn was selected before scoring.
These playback boundaries are operational labels, NOT independent human
semantic annotations; they cannot establish a real-world interruption rate.

Smart Turn v3.2 CPU weights were pinned to Hugging Face revision
`f766f81d3cfdf7737ac64aad813d91bbfd56bf93`; their SHA-256 is recorded in the
result. The model uses the documented eight-second causal audio window and
Whisper features. Its unchanged threshold was 0.5.

LiveKit Agents 1.8.8 used its own `TurnDetector(version='v1-mini')` stream with
livekit-local-inference 0.2.7, 20-ms frames and the SDK's German threshold 0.245.
The installed MODEL_LICENSE explicitly forbids standalone use outside LiveKit
Agents and restricts using its outputs to develop other models. Consequently
the native model was NOT detached from that framework, and its predictions are
not training data for Smart Turn. This is a stronger dependency constraint than
the earlier documentation-only overview established.

The first environment check exposed a NumPy/SciPy ABI mismatch and the first
stream probe exposed invalid oversized audio frames; both runs failed, were not
reported as benchmark successes, and were repaired only in the isolated test
environment/harness. Production dependencies were not altered.

| Detector | Internal pauses incorrectly ended | Final endings recognized | Median prediction execution |
| --- | ---: | ---: | ---: |
| Smart Turn v3.2 | 4/4 | 4/4 | about 96 ms |
| LiveKit Agents v1-mini | 4/4 | 3/4 | about 70 ms |

This confirms fast component inference, not safe fast turn-taking. Neither
candidate is promoted and the one-second conversation target is unproven.
Do not tune thresholds until the selected examples/labels and preprocessing
have been checked against independently annotated human German speech. The
synthetic sample is too small and biased for a general comparison or ranking.

`tests/prepare_turn_corpus.py` prepares a fixed four-turn public German sample
from `livekit/eot-bench-data`, using existing annotated internal/final silences
and no detector scores for selection. Its metadata and complete audio belong
under State `inputs/turn-detector-human-pilot-20261015`. The initial remote
filter request timed out; an extended bounded read also timed out. Read-only
row inventory confirmed German data at row 500. The alternate bounded row
retrieval path then returned HTTP 502 (including the one-row fallback).
Consequently no human-corpus manifest was produced and human-data validation
did NOT run. Do not report the synthetic screening as human validation.
The next decisive research step is obtaining that fixed annotated corpus through
a healthy data source, then comparing unchanged causal policies. No background
retry, worker or paid model session was left running.
