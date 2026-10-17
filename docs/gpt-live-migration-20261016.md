# GPT-Live 1 migration

## Decision

Chris selects GPT-Live 1 for the OpenAI voice path and research. Realtime 2.1 was the initial integration baseline for reference-code recognition, noise/interruption handling and the existing tool workflow. It remains a historical comparison, not the active OpenAI default. The research/coding agent is still GPT-6.1 Sol; the voice model under study is GPT-Live 1.

## Implemented contract

- `LiveSession` uses the dedicated `/v1/live/sessions` WebSocket, `session.start`, continuous PCM input and output, independent transcript deltas, and Responses delegation to configurable `backend_model` (initially GPT-6 Luna).
- The voice prompt owns conversation style and delegation guidance. The backend prompt owns task facts and tools. No manual voice response triggers, commits or invented per-turn completion events.
- Only completed nested function-call items dispatch tools. Private decisions use the existing app authority gate. Tool results go through `response.item.create`, followed by `response.create` for backend continuation only. Repeated call identities are not replayed.
- Model output remains blocked while a private user decision is pending. Guardian/native pause, takeover and hangup remain independent of the model.
- Normal farewell closure waits for acoustic output to stop and native playback to drain. Normal digital-silence frames are preserved; after an accepted finish request, zero-only frames no longer keep the native queue full. A callee transcript during closure cancels the pending finish.
- Receiver stays alive through `session.close` and terminal `session.closed`, with bounded finalization. Final voice seconds/USD estimate are separate from backend token/EUR estimates; no exchange rate or invoice certainty is invented.
- The default OpenAI profile is migrated without changing credentials, preparation text model or historical call snapshots. Its previous Realtime profile is retained. Gemini remains available. The UI exposes the Live backend model and hides inapplicable Realtime turn controls.

## Evidence and limits

53 offline app/provider/SIP tests passed, including routing, nested tool handling, usage, terminal acknowledgement, migration preservation and rejection of a failed readiness result. Frontend build passed. The shared-browser desktop/mobile profile probe verified Live model/backend settings and absence of Realtime turn controls without saving or dialing; Chrome PID/start time was unchanged after cleanup. The deployed HTTPS health check passed.

The first model-only readiness canary acknowledged startup and finalized. A subsequent bounded direct PCM canary produced German output and transcripts matching the provided spoken number, then finalized with 9 seconds reported. It was not independent hearing verification, a phone call, a restaurant task or a latency benchmark.

The first delegation canary ended too early because digital-silence frames counted as speech; it also exposed a harness result-label defect (`ready` alongside an error). Its immutable artifact is retained as FAILED evidence despite its label/exit status. The helper now counts nonzero audio for readiness and sets failed state on exceptions. Follow-up canary results must be read from their fresh artifact, never inferred from the first canary.

The fresh second delegation canary exercised a real nested `ask_user` call, delivered a synthetic private denial, received backend usage and spoken-output transcript refusing confirmation, and finalized with 9 seconds of voice usage. This verifies the delegation transport; it does not qualify private authority under real phone conditions or full farewell playback. Its bounded stop occurred during the closing phrase. No human was called and no external commitment was made.

Research continuation reuses the same supervised native Goal and hourly report owner, with an updated GPT-Live restaurant objective. Existing incremental and global budget limits and historical reservations remain binding. Live-specific fresh pricing and prospective admission are required before paid research; migration itself does not grant more funds. No real phone call or SIP registration was performed for this migration.

## Official protocol sources

- https://developers.openai.com/api/docs/guides/live-migration
- https://developers.openai.com/api/docs/guides/voice-websockets?api=live
- https://developers.openai.com/api/docs/guides/live-delegation
- https://developers.openai.com/api/docs/guides/live-conversations
- https://developers.openai.com/cookbook/examples/audio/voice_agent_evaluation
