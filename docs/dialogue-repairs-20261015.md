# Dialogue preparation and provider diagnostics repair

## User-visible contract

- Start with destination and free-text objective, without a scenario selector.
- Extract explicitly stated party size/time before asking questions. With a
  selected text profile, preparation uses the entire objective and confirmed
  context. Answers trigger another missing-information check. AI completion
  suppresses unrelated fallback questions; unknown facts remain unknown.
- Select text and live audio profiles independently, including across providers.
  The operator text default is `gpt-6-luna`; live selection is preserved.
- No product demonstration mode, cost ceiling, tariff admission, or price
  confirmation requirement. Provider charges still apply. Independent research
  budgets are unchanged. Explicit call acceptance, no-redial and cleanup remain.
- Call state, phases, transcripts and redacted provider errors remain in SQLite.
  Each failure has a diagnosis ID, phase, provider/model, error type/code and
  sanitized detail. Authenticated diagnostics are accessible in the result UI
  and `/api/calls/{id}/diagnostics`. No transcript attachment is required for
  subsequent local investigation. Audio recording remains opt-in.

## Observed connection failure

The submitted historical call `9408ece804aeb50951bf1b1c` failed in preparation.
The original implementation retained only `APIError`; its closure receipt
confirms no connected call, no media frames, SIP unregister acknowledgement
and local model closure. The historical exception payload cannot be recovered.

A fresh registration-free, input-free connection probe reproduced Google
code 1007: the Live API rejected `additional_properties` inside the tool schema.
The adapter had reused OpenAI's JSON schema. Google schemas now omit
`additionalProperties`, retaining required fields; OpenAI schemas are unchanged.
After this repair Google instead returned code 1011: prepayment credits depleted.
That is a separate account limitation, not a budget abort in CallBuddy. No
credits, billing settings, keys or provider project were changed. No call was
placed. The recovery probe is time-stamped separately from the historical run.

OpenAI's configured persistent audio session acknowledged setup with no audio
input, response generation, SIP registration or dial. This is connection proof,
not an end-to-end telephone conversation acceptance.

## Verification

- Focused backend tests: 36 passed, including explicit fact reuse, AI completion,
  separate text profile, authenticated persistent diagnostics, Google tool schema,
  unbounded product admission and idempotent start/queued controls.
- Frontend TypeScript and Vite build passed.
- Shared-browser regression passed on the existing persistent context, including
  desktop/mobile screenshots, no horizontal overflow, independent text selector,
  no scenario/demo/budget controls and no page errors. Chrome owner unchanged.
- Real authenticated preparation request through the app with GPT-6 Luna:
  objective stated `2 Personen`; response retained it and asked for the missing
  evening time. One text request, no call or audio dispatch. Idempotency key:
  `dialogue-regression-luna-20261015`.
- Supplied password used only for the existing app login during verification;
  existing provider credential references were reused, not rotated or exposed.

Internal artifacts: State `results/dialogue-repairs-tests.xml`,
`results/dialogue-repairs-build.log`, and
`work/media-runs/dialogue-repairs-20261015/` with a retention manifest.

## Remaining limitation

Gemini Live is blocked until the Google project has usable credit. OpenAI Live
can be selected instead. No automatic provider fallback, recharge or outbound
call was performed. Natural-language fact extraction is not a universal semantic
guarantee; the regression establishes the supplied party-size case.
