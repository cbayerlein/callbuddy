# Turn-taking quality research — 2026-10-15

## Conclusion

The current plateau is not evidence that conversational responses require a
one-second silence timer. A fixed timer is only one endpointing policy. Audio
end-of-turn classifiers and provider-native semantic decisions are alternatives.
Keep SIP/Fonial and persistent speech-to-speech sessions; neither LiveKit Cloud
nor a new telephone provider is a prerequisite for evaluating these approaches.
No new paid audio calls, GPU work, native Goal continuation, or research-ledger
changes were made for this investigation. Accent remains deferred.

## Evidence from our own run

Recomputed using the existing read-only `dialogue_quality_timing.timing_parts`
against the complete caller/callee journals of
`dialogue-quality-v2-20261014-restaurant-latency07-dialogue-restaurant` under the
phone-agent State project's `work/media-runs` directory.

| Observed median component | Caller | Restaurant |
| --- | ---: | ---: |
| Last input voice consumed to input SDK send | 60 ms | 42 ms |
| Input SDK send to observed provider speech-stop event | 1,448 ms | 1,292 ms |
| Speech-stop observation to response-create send | 23 ms | 94 ms |
| Response-create send to observed response-created | 131 ms | 194 ms |
| Response-created to first decoded voiced audio | 778 ms | 964 ms |
| Decoded voice to delivered voice | 41 ms | 44 ms |
| Input queue before consumption | 0.23 ms | 0.21 ms |
| Complete last-input-voice to delivered-voice measurement | 2,602 ms | 2,605 ms |

These are medians of individual stages, not an additive decomposition of one
median turn. SDK-send-to-stop includes the fixed one-second detector policy,
transport and server/event observation; it is NOT pure network latency. The
generated-audio stage includes provider scheduling and generation, not an
isolated model-inference benchmark. The prior 2.49-second acoustic median uses
different signal boundaries and is not interchangeable with this journal metric.
Hardware audibility was not measured. Tiny PCM queue delays do not explain the
whole multi-second delay. Response dispatch is not the dominant measured stage.

The old 800-ms experiment failed its controlled latency gate and omitted a
spoken date in the natural dialogue. Prompt compaction also failed the declared
latency gates. A filler at 2.84 seconds did not fix a substantive name response
at 10.04 seconds. Do not promote these candidates or replay their paid intents.

## Alternatives and evidence quality

### 1. Audio-native endpoint classifier, separate from the speaking model

Pipecat Smart Turn v3.2 evaluates actual PCM, including prosody, with a recent
eight-second window. It supports German and English, has an 8-MB quantized CPU
model, and has an open BSD-2-Clause model implementation. Its documentation
recommends a 200-ms VAD pause before classification and reports under 100 ms of
inference on ordinary cloud instances. These are vendor component measurements,
not a one-second end-to-end guarantee. An incomplete decision can still wait
for a three-second fallback. Preserve rolling context and re-evaluate if speech
resumes while inference is running.

LiveKit's current audio turn detector has a local `v1-mini` option and a hosted
full `v1` option. It supports German, does not require STT, and documents Realtime
integration with the provider's own turn detector disabled. Defaults include
300-ms minimum endpointing and a VAD minimum silence of at least 250 ms. Without
STT its language thresholds default to English: German calibration must be
explicitly checked. Cloud service and a Cloud account are not required for the
local mini path. The older transcript-only detector is deprecated in current
documentation; do not design a new dependency around that older recommendation.

**Recommendation:** first compare Smart Turn v3.2 and LiveKit v1-mini offline in
shadow mode on the same complete German PCM, including mid-sentence pauses.
Keep one endpointing authority. Do not leave both an external classifier and
provider auto-VAD committing the same input. SIP remains an independent adapter.

### 2. Provider-native semantics and response-start latency

OpenAI documents semantic VAD as an alternative to silence-only VAD. `high`
eagerness permits earlier completion but does not guarantee one-second audio.
This was already explored here; simply re-enabling it is not a new finding.
The persistent research bridge already selects minimal reasoning effort for
short-release runs. Do not claim that lowering reasoning is an untouched fix.
The new product adapter currently does not explicitly set reasoning effort;
that difference deserves a controlled, opt-in comparison, not a silent model
configuration change. The selected GPT-Realtime-2.1 documentation explicitly
says higher reasoning effort can increase latency.

Provider-generated audio itself takes about 0.8–1.0 seconds after the observed
response-created event in the inspected run. Faster endpointing alone may
therefore still miss a one-second complete target. Compare native auto-response
versus application dispatch only after preserving admission, pause, private
decisions and cancellation; our measured dispatch delay is only 23–94 ms.
Google remains an adapter candidate, not a demonstrated latency improvement.
The Google documentation fetch redirected beyond the retrieval limit in this
investigation; no undocumented defaults or comparative timing claims are made.

### 3. Speculative generation without speculative playback

Begin preparing a response at a plausible boundary, hold its audio privately,
and discard/cancel it if the caller resumes. This can overlap work but increases
cost and lifecycle complexity. Never play a speculative promise or execute a
speculative booking/tool. A resumed utterance must replace, not append stale
audio. Research this only if a simpler classifier leaves model generation as
the measured bottleneck. No speculative implementation was installed here.

### 4. Full-duplex models

NVIDIA PersonaPlex/Moshi is an example of genuinely full-duplex streaming rather
than turn-by-turn half-duplex orchestration. It is a larger architectural option,
not proof of reliable German business calls or private decision/tool handling.
The published examples and Fisher training corpus are English; the reviewed
README does not establish our required German quality. Model-license acceptance
and GPU inference are additional requirements. Do not replace the working
provider/SIP stack with it on the strength of a low-latency demo.

## A more useful evaluation method

The public eot-bench evaluates causal decisions at EVERY pause in real human
turns, distinguishing internal `hold` pauses from real `eot` endings. This is
better than selecting isolated, already-trimmed utterances. It includes German.
Its headline leaderboard is published by LiveKit, a competing model vendor;
use the open methodology and raw per-language evidence, not its ranking as
independent acceptance. Its English table shows approximately 0.54 seconds of
endpointing at a 5% false-cutoff rate for hosted LiveKit v1, versus approximately
1.05 seconds for Smart Turn v3.2 and 1.07 seconds for v1-mini. These figures are
endpointing only, not response audio, and the English headline is not a German
result. They warn against equating a 65-ms classifier with a 65-ms conversation.

Freeze a small representative German set containing complete statements,
0.6–0.9-second hesitations, dates, names, spelled codes, corrections, trailing
phrases and intentional pauses. Include existing restaurant audio but not only
two cooperating model voices. Label true final boundaries independently of
the candidate. Hold out examples before tuning; preserve full preceding PCM.
Measure false cutoffs, missed ends, overlap, lost syllables and semantic errors,
not merely mean silence. Use the same inputs and confidence/timeout sweep for
all candidates. Never feed future audio or a known transcript to a causal judge.

The user's target is one second from the last actual speech to the first
substantive audible response. Report median, p90/p95, maximum and the fraction
of safe complete turns within one second. Measure greeting/ordinary answers,
tool decisions and genuine user-thinking separately. Do not hide tool latency
or claim fillers meet the substantive-response goal. Define reliability from
measured interruption/semantic tradeoffs rather than silently converting the
user's target to an easier percentile.

After offline selection, one restaurant scenario is sufficient for the next
paid integration comparison. Do not repeat doctor/airline matrices or tackle
accent now. Require a fresh dated admission fitting the remaining authorized
budget; historical reserves stay intact. Heavy batch/model inference belongs
on RunPod under its current workflow. No such work was launched by this report.

## Sources retrieved in this investigation

1. https://developers.openai.com/api/docs/guides/realtime-vad
2. https://developers.openai.com/api/docs/models/gpt-realtime-2.1
3. https://docs.pipecat.ai/api-reference/server/utilities/turn-detection/smart-turn-overview
4. https://github.com/pipecat-ai/smart-turn/blob/main/README.md
5. https://docs.livekit.io/agents/logic/turns/turn-detector/
6. https://github.com/livekit/eot-bench/blob/main/README.md
7. https://github.com/NVIDIA/personaplex/blob/main/README.md

Documentation and default branches are mutable; pin versions, model weights,
source hashes and licenses before an executable benchmark admission. No vendor
performance figure above is a result from our installed product.
