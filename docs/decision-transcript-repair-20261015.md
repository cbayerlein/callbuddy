# Decision and transcript repair

## Observed failure

Call `5eddf06e64e91e3544932599` requested a private decision about Wednesday instead of Friday. The decision remained pending, but subsequent model speech accepted Wednesday and the private result claimed a confirmed appointment. No private answer event exists. Model prompting alone therefore did not preserve user authority.

## Changes

- Group adjacent transcript chunks by speaker/source for presentation. Turn boundaries, interruptions and private decisions separate blocks. Original events remain unchanged for diagnosis.
- Replace preparation questions and permission choices with an accessible loading status throughout text-model generation.
- On `ask_user`, clear queued audio and block subsequent model audio and successful finish requests until the user's explicit answer has been delivered.
- Keep withheld model transcripts in diagnostic events, not in the displayed spoken transcript.
- Without an answer, terminate after 20 seconds as inconclusive, explicitly requiring clarification/callback. There is no automatic callback or acceptance.
- Ask the model to speak a short holding phrase before requesting the private decision.

## Limits

The holding phrase is prompt-guided, not guaranteed recorded playback. The conservative timeout currently ends without a separately verified spoken explanation. It does not continue clarifying other details while waiting: all model speech is blocked. This deliberately prioritizes preventing unauthorized commitments; selective safe speech requires a further output-control design. No live phone acceptance has been performed for this patch.

## Verification

Focused app, dialogue and SIP regression: 45 passed, including a simulated model attempting unauthorized speech and finish while a decision is pending. Frontend typecheck/build passed. Browser fixtures are page-local and must confirm interception before form actions; they never authorize dialing.

Shared-browser fixture proof passed on the direct backend origin: loading placeholder hides permission choices, and streamed fragments render as two coherent speaker blocks. Both screenshots were visually inspected. The shared Chrome PID/start time remained unchanged. The app service was restarted with no active calls; public HTTPS health confirms live mode remains enabled. The first immediate post-restart health request raced startup and failed; the subsequent HTTPS health check passed. No SIP registration or phone call was made for this patch.
