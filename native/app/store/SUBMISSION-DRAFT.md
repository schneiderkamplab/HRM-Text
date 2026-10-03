# DFM Mimir submission answers — draft, 2 October 2026

## Build 13 submission follow-up — 3 October 2026

Both SDU-signed 0.1.5 (13) archives passed the OS-TLS and signing audits and
uploaded successfully. Apple processing/build selection and final App Review
submission are separate steps. Builds 11/12 retain their original encryption
status; the OS-only answers apply only to the rebuilt version.

The user explicitly confirmed SDU has the necessary rights to distribute the
bundled model/branding and provide optional search content. Saved Content Rights
= Yes. Free pricing and availability in all 175 storefronts (including France)
were configured; manual release remains selected.

Both build 13 encryption questionnaires were saved as “None of the algorithms
mentioned above” (OS-only encryption; no bundled implementation). Both store
versions were switched from build 11 to build 13, saved, added for review and
submitted. Apple confirmed **Waiting for Review** for iOS and macOS on
3 October 2026 at approximately 07:39–07:40 CEST. No public release occurred.

- iOS submission: `57eb3e67-8ef4-4008-8009-5060e748e698`.
- macOS submission: `cdb16591-5865-4642-bf93-972f7dfb7c70`.
- App Store Connect app: `6818524811`, SDU team `46HSA3LZ7H`.
- Local signed archives/audits: `logs/sdu-store/{ios,macos}-signed-13/`.
- Upload evidence: `logs/sdu-store/{ios,macos}-upload-13.log`.


## Historical draft — build 11, 2 October 2026

The following applies to SDU app 6818524811, iOS/macOS 0.1.5 (11). These were proposed answers,
not claims that all declarations have been submitted or approved.

## Listing and review contact

- Category: Productivity (saved).
- Copyright: 2026 Peter Schneider-Kamp (user supplied; saved).
- Review contact: Peter Schneider-Kamp, petersk@imada.sdu.dk. The user-supplied
  phone number is saved in both Apple forms; do not duplicate it in public docs.
- No sign-in required. Keep manual release after review.
- Public support and privacy pages are published at
  https://schneiderkamplab.github.io/HRM-Text/support/ and /privacy/;
  their URLs are saved in App Store Connect.

## Saved App Privacy draft — 2 October 2026

Selected collection = Yes and saved four categories in App Store Connect:
Other User Content, User ID, Other Usage Data, Other Data Types. All are marked
linked to identity and not used for tracking. Content, identifiers and metadata
use App Functionality plus Other Purposes; usage counters use App Functionality.

Historical draft: Search History initially remained unresolved because the Worker
does not store queries in D1, but that does not establish Jina's retention.
Jina's current legal page (4 May 2026) points
to Elastic's DPA and warns its older terms may not reflect current practices.
Follow-up research found query logging and seven-day cache-expiry defaults in
Jina's public Search code. Treat Search History as collected for App Functionality,
linked and not used for tracking. All five categories are now saved and published
in App Store Connect (2 October 2026); the UI confirmed publication by Peter
Schneider-Kamp. `DNT: 1` is deployed on Worker requests but is not proof of zero retention.
Website-cookie statements are not evidence about this API.

The setup controls worked with a screenshot-grounded click after ordinary
locator activation failed; this was not proof of an Admin permission block.

## Privacy labels

Proposed: data is collected through optional feedback/search; no advertising
tracking. Do not select “Data Not Collected.” A consent dialog alone does not
qualify research/model-training feedback for Apple's optional-disclosure exemption.

| Data | Proposed purpose | Linkage / remaining check |
| --- | --- | --- |
| Other User Content: submitted chats, summaries, ratings, comments | App Functionality; Other Purposes for research/model training and permitted publication | Treat as linked: pseudonym persists, and text can identify its author |
| User ID: attribution pseudonym and search-key identity | App Functionality; Other Purposes where used for research attribution | Linked; not a hardware Device ID |
| Other Usage Data: daily search-key usage | App Functionality, including quotas/abuse prevention | Linked to access key |
| Other Data Types: submitted model/version/settings metadata | App Functionality and Other Purposes | Linked to the submitted feedback |
| Search History | App Functionality | Confirm Jina/provider retention; do not claim no collection solely because D1 does not store queries |
| Customer Support | App Functionality | Disclose if support collection falls within Apple's requirements; contact details can identify the sender |

No advertising SDK or cross-app advertising tracking is implemented. Do not
claim all user content is anonymous. Final labels must account for provider
practices and the actual use of each field, not simply choose every category.

## Age rating

The app is a general-purpose generative model, not a curated children's product.
Draft factual feature answers: no parental controls, no age-assurance mechanism,
no advertising, no person-to-person messaging/social network, no gambling,
contests or loot boxes. A conversation with the model is not by itself a
person-to-person messaging service. There is no public user-content feed.

Web search returns external content and links. Assess Apple's unrestricted-web
access definition against this behavior; do not describe search as filtered or
child-safe. Generated content can include mature, violent or medical topics when
prompted. Do not mark all content-frequency answers “None” based on the clean
welcome screen or our four sample chats. Proposed approach: request the highest
available age override for this initial release, while still answering each
underlying content question truthfully.

Completed 2 October: calculated rating 13+, overridden to 18+ at the user’s
request (19+ Korea; older OS global 17+). Feature controls/capabilities are No;
external search results do not constitute an embedded arbitrary-webpage browser.
Ordinary mature themes, non-graphic sexual content, medical information, fantasy/
realistic violence and weapon references are Infrequent; wellness topics Yes.
Graphic sexual content and prolonged graphic/sadistic violence are None based on
the user’s explicit confirmation that v1.5 reliably refuses both. Gambling,
simulated gambling, contests and loot boxes are absent.

## Content rights

Proposed answer: “Yes, it contains, shows, or accesses third-party content, and
I have the necessary rights” only after confirming the model license, bundled
software notices, DFM/UCloud branding permissions and search-provider terms.
The web-search feature means “No third-party content” is not a good description.
Copyright holder Peter Schneider-Kamp does not alone establish those permissions.

## Encryption / export compliance

No custom encryption algorithm is implemented in the app's own code. However,
Both build 12 Flutter engine binaries contain BoringSSL source references,
confirming bundled standard cryptography beyond Apple OS libraries. The Apple
questionnaire's standard-encryption answer leads to a France availability question;
this remains pending the user’s territory decision. No compliance answer saved yet.
Both uploaded builds currently show Missing Compliance. Do not equate that with
upload failure, and do not set an Info.plist exemption flag merely to suppress it.

## Reviewer notes

No account or login is required. The app bundles DFM Mimir v1.5 Q4_K_M (about
1.2 GB); allow initial model loading, then ask a question in Danish or English.
Ordinary chat works offline. Settings control context length, reply budget,
acceleration and appearance. Optional feedback shows a confirmation dialog.
Optional web search requires a service key and is disabled until configured.
Provide a dedicated review key if Apple must exercise that feature; do not place
production credentials in public documentation. On Mac the optional local API
runs inside the app; the store app has no standalone command-line server.

## Remaining release work

Support/privacy pages are published. A privacy-policy link and offline explanation
are now implemented in Settings → Online, with explicit external-browser opening
and a copyable URL if opening fails. Rebuild/upload both platforms as build 12. Verify
signed installs, finalize privacy/age/rights/export answers and pricing/territories.
Review institutional trader details through the authorized SDU account owner.

Sources checked 2 October 2026:
- [Apple privacy definitions and optional disclosure](https://developer.apple.com/app-store/app-privacy-details/)
- [Apple age-rating definitions](https://developer.apple.com/help/app-store-connect/reference/app-information/age-ratings-values-and-definitions/)

## Elastic terms checked — 2 October 2026

The [DPA linked by Jina](https://www.elastic.co/pdf/v100623-0-elastic-customer-dpa.pdf)
limits processor use to the agreement/customer instructions (2.3) and provides
deletion at termination or under the applicable retention policy, subject to legal
retention (5.1). It gives no Jina Search request-level zero-retention guarantee.
[Elastic's product privacy statement](https://www.elastic.co/legal/product-privacy-statement)
separately covers provider-controlled usage/security data, including query shapes
and potentially threatening inputs/outputs; it excludes processor-held customer
content. The general privacy statement's generative-AI training restriction must
not be presented as a verified Jina API-content guarantee because that statement
excludes processor-held data. Actual s.jina.ai query/log/cache retention is still
not established by these public documents. A zero-retention agreement is not a
prerequisite to using the service or listing an app: the requirement is an accurate
declaration of actual collection and use, including retained search data if present.

## Build 12 upload — 2 October 2026

Both signed archives passed audit and upload after the user refreshed Xcode Accounts.
iOS upload succeeded at 21:56:13 CEST and macOS at 21:56:18 CEST. Logs are
logs/sdu-store/ios-upload-12-retry.log and macos-upload-12.log. Apple processing,
build selection and final App Review submission remain outstanding.

## Updated age and France decisions — 2 October 2026

User superseded the 18+ override with the calculated rating. Removed the override
and verified 13+ for 172 territories, 16+ Vietnam/Brazil, 12+ Korea; older OS global
rating 12+ with regional exceptions. Content answers unchanged.

User wants France included. Selecting Yes in the standard-encryption questionnaire
displays a requirement to upload export compliance documentation and obtain Apple
approval; no Save option is offered. This is an outstanding documentation step,
not completed compliance or configured storefront availability.
