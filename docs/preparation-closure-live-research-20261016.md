# Preparation, closure and GPT-Live investigation

## Product repair

The preparation prompt now fixes the delivery channel to telephone and requests only information that materially affects the call. A fully specified short message can finish preparation without additional questions. Existing answers and the objective remain part of the supplied context. This is a prompting repair, not a claim that all irrelevant questions are deterministically eliminated.

Normal model-initiated closure now requires output audio and a recognized farewell in assistant transcript evidence. Missing farewells trigger one corrective response, rather than immediate hangup. Audio must drain and remain drained for one second before closure. A callee transcript arriving during closure cancels the pending finish. Explicit operator hangup, transport errors and unanswered private-decision timeout retain their existing behavior.

Farewell recognition covers common German and English phrases. It is a conservative lexical guard, not an independent acoustic or semantic evaluation. The opportunity for a response before farewell is also prompted; a response whose transcription arrives after closure cannot be recovered. Offline simulation does not qualify real provider behavior.

## Model investigation (2026-10-16)

### Correction after broader web research

The API-only investigation below was insufficient to establish product existence. GPT-Live-1.1 and Quip were officially announced on October 15, 2026. The release notes confirm rollout in ChatGPT Voice, more natural accents, German voice options, and more varied short search-progress phrases. The system card describes continuous full-duplex conversation and identifies 1.1 as the successor to GPT-Live-1. The announcement explicitly says API access is "coming soon"; no launch date is given. Thus product existence is confirmed, while account/API access to 1.1 remains unconfirmed.

Verified additional sources:

- https://openai.com/products/release-notes/ (October 15 entry)
- https://deploymentsafety.openai.com/gpt-live-1-1 (full page text, including Introduction)
- https://community.openai.com/t/gpt-live-1-1-is-rolling-out-with-new-voices-and-better-accents/1406704 (announcement and API follow-up)
- https://www.notebookcheck.com/ChatGPT-Voice-GPT-Live-1-1-bringt-zwei-deutsche-Stimmen.1425805.0.html (October 16 news report; names German voices Sonna and Miko; no independent acoustic benchmark)

No independently measured German latency distribution or one-second guarantee was established. The system card primarily evaluates safety/alignment, not response-gap performance. Publisher statements about smoother accents and delegation are not our own listening evidence. The API price documented for GPT-Live-1 must not be presented as confirmed pricing for 1.1.

The existing native Decisions integration can remove an app round trip for classification while speech continues; its examples currently use `gpt-live-1` and `gpt-6-luna`. A prediction must never substitute for explicit user permission. Source: https://developers.openai.com/api/docs/guides/decisions-voice.

The official continuous duplex evaluation guide provides CRAWL/WALK/RUN methods, continuous audio/event timing, task-state validation, and separate response-latency and interruption metrics: https://developers.openai.com/cookbook/examples/audio/voice_agent_evaluation. Its recorded example is explicitly not a benchmark. For CallBuddy, test one representative restaurant scenario repeatedly, distinguish first audible output from first substantive answer, and retain interruption, permission, reference and task-completion checks. Synthetic tests can establish bounded engineering progress without claiming a human-labelled German turn-taking benchmark.

Recommendation: build an opt-in Live adapter with the existing SIP bridge and independent backend delegation; compare the currently available Live model only under explicit paid-test admission, and use the same evaluation when 1.1 API access is actually released. No adapter implementation or paid test is authorized by this research-only request.

### Earlier API-only findings (retained for provenance)

Official sources:

- https://developers.openai.com/api/docs/models/gpt-live-1
- https://developers.openai.com/api/docs/guides/live
- https://developers.openai.com/api/docs/guides/voice-latency-cost?api=live

The exact `gpt-live-1.1` identifier was not found in official-domain searches; its model documentation paths returned 404 in the preceding read-only check. The account's current model list includes `gpt-live-1` and does not include `gpt-live-1.1`. Catalog visibility does not prove a successful voice session.

GPT-Live 1 is documented as full-duplex voice with independently configurable backend delegation. It uses `/v1/live/sessions`, not the existing `/v1/realtime` adapter. It is therefore a plausible architectural experiment for natural conversation, but not a profile-string substitution. The documented voice-session price is USD 0.05/minute, with backend usage billed separately and silence included in duration. No one-second latency guarantee is established by these sources.

No paid Live session, provider switch, research restart or research-ledger change was performed for this investigation.
