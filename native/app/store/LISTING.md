# SDU App Store / TestFlight copy — draft

Prepared 2026-10-01 for proposed SDU identifier `dk.sdu.dfm.mimir`.
These fields have not been entered into App Store Connect. Confirm the display
name is available and approve institutional/contact details before submission.

## Shared fields (English U.K.)

- Name: **DFM Mimir**
- Subtitle: **Danish and English, on device**
- Primary category: **Productivity**
- Price: **Free**, no in-app purchases
- Keywords: `Danish,English,AI,chat,offline,writing,assistant,language,local`
- Version: **0.1.5**, build **11** reserved for this preparation
- Copyright: confirm institutional rights-holder text with SDU
- Support URL / Privacy Policy URL: publish the approved texts in this directory
  to stable public HTTPS pages, then enter their actual URLs. No placeholder URL
  should be submitted.

## Description — shared

Chat in Danish and English with Mimir, a language model from Danish Foundation
Models, a research collaboration. Mimir was trained on SDU UCloud.

The app includes DFM Mimir v1.5 in a compact 4-bit format. The model runs on your
device, so you can start chatting without an account or an additional model
download. Ordinary chats work offline and are stored locally.

• Write, rewrite, brainstorm and ask questions in Danish or English.
• Keep multiple conversations and read answers with basic Markdown formatting.
• Adjust text size, reply length, context size and generation settings.
• Summarize earlier conversation turns to make room in longer chats, with an
  option to see the summary as it is generated.
• Use the bundled model or manage compatible Mimir GGUF models.

Optional online features are controlled in Settings. Model discovery/downloads
contact Hugging Face and the catalog host. Web search requires a Mimir search key
and sends search queries through our service to Jina AI. Sharing feedback asks
for confirmation before sending the current chat; permission to publish it under
CC BY 4.0 is a separate choice.

Mimir can make mistakes. Check important answers. Speed and usable context size
depend on your device and available memory. The included model was trained with
a context length of 4,096 tokens; larger settings are experimental. The bundled
model makes this a large download (about 1.2 GB of model weights).

## macOS addition

Built for Apple Silicon Macs, with Apple Metal acceleration and a CPU option.
Advanced users can enable a configurable OpenAI-compatible local API while the
app is running. The Mac App Store app does not include the standalone command-line
server distributed in the GitHub desktop package.

## iOS addition

Runs locally on compatible iPhone and iPad devices, using Apple Metal acceleration
where available. Large contexts and simultaneous apps can increase memory pressure;
choose smaller settings on devices with less available memory.

## TestFlight: what to test

Test offline chat in Danish and English; switching conversations; text size and
settings; stopping a reply; long-chat compaction; app restart and saved chats.
On Mac also test model file import and the optional local API. Report your device,
OS version and reproduction steps. Do not include private information in feedback
unless you intend to share it.

## Review notes (both platforms)

No account or sign-in is required for the core app. The model is bundled. Launch
the app, allow local model loading to finish, start a chat and send, for example,
“Give me three ideas for a short walk.” Repeat in airplane/offline mode. Local
inference can take longer on older devices. Settings exposes context/reply limits
and CPU/acceleration choices.

Online settings are optional; the app remains useful with outgoing requests off.
Search requires a service key. If search is enabled in the submitted binary,
provide a separate limited reviewer key in private App Review notes and verify it
before submission. Do not put credentials into the listing, repository, screenshots
or bundle. Feedback sends only after the consent dialog is confirmed. Test feedback
will reach the research service, so label it as a review test and avoid real data.

The optional desktop API is off by default. It runs in the GUI process; the Mac
store archive contains no standalone server or installer/helper.

Reviewer contact: confirm the authorized person's name, phone and monitored email
in App Store Connect. Do not copy a phone number from unrelated account records.

## Declarations still requiring review

- Age rating: complete Apple's current questionnaire for an AI chat application;
  do not infer a rating from the absence of curated adult content. Model output
  can be unpredictable. This is not a Kids Category submission.
- Content rights: verify redistribution licenses for the model, code and logos,
  and institutional authority to use the SDU/UCloud branding.
- Export compliance: validate the actual build's encryption usage and answer the
  questionnaire consistently. HTTPS and platform keychain usage are not grounds
  to invent a custom-cryptography declaration.
- EU trader status/contact: SDU must supply the institutional declaration.
- Privacy labels: use PRIVACY-REVIEW.md and approve the final public policy.
