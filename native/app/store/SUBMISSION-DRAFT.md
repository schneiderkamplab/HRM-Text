# DFM Mimir submission answers — draft, 2 October 2026

Applies to SDU app 6818524811, iOS/macOS 0.1.5 (11). These are proposed answers,
not claims that all declarations have been submitted or approved.

## Listing and review contact

- Category: Productivity (saved).
- Copyright: 2026 Peter Schneider-Kamp (user supplied; saved).
- Review contact: Peter Schneider-Kamp, petersk@imada.sdu.dk. The user-supplied
  phone number is saved in both Apple forms; do not duplicate it in public docs.
- No sign-in required. Keep manual release after review.
- Public support page: publish SUPPORT.md; privacy page: finalize PRIVACY.md.
  Neither URL has been selected or entered yet.

## Saved App Privacy draft — 2 October 2026

Selected collection = Yes and saved four categories in App Store Connect:
Other User Content, User ID, Other Usage Data, Other Data Types. All are marked
linked to identity and not used for tracking. Content, identifiers and metadata
use App Functionality plus Other Purposes; usage counters use App Functionality.

These are saved answers, not a completed/published privacy declaration. Search
History remains unresolved: the Worker does not store queries in D1, but that
does not establish Jina's retention. Jina's current legal page (4 May 2026) points
to Elastic's DPA and warns its older terms may not reflect current practices.
Verify API-specific retention under the actual service arrangement before
publishing. Website-cookie statements are not evidence about this API.

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
underlying content question truthfully. The exact questionnaire remains to be
completed; an override does not replace the content assessment.

## Content rights

Proposed answer: “Yes, it contains, shows, or accesses third-party content, and
I have the necessary rights” only after confirming the model license, bundled
software notices, DFM/UCloud branding permissions and search-provider terms.
The web-search feature means “No third-party content” is not a good description.
Copyright holder Peter Schneider-Kamp does not alone establish those permissions.

## Encryption / export compliance

No custom encryption algorithm is implemented in the app's own code. However,
Dart HTTPS may include TLS from the runtime rather than exclusively using Apple's
OS encryption. Inspect the shipped runtime before selecting the Apple-OS-only
answer. Proposed classification if bundled TLS is confirmed: standard encryption
in addition to the OS, with the appropriate exemption/documentation assessment.
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

Publish approved support/privacy pages and add a privacy-policy link inside the
app (currently absent), then rebuild both platforms if source changes. Verify
signed installs, finalize privacy/age/rights/export answers and pricing/territories.
Review institutional trader details through the authorized SDU account owner.

Sources checked 2 October 2026:
- [Apple privacy definitions and optional disclosure](https://developer.apple.com/app-store/app-privacy-details/)
- [Apple age-rating definitions](https://developer.apple.com/help/app-store-connect/reference/app-information/age-ratings-values-and-definitions/)
