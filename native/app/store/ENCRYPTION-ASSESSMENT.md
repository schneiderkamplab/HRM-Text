# French encryption assessment — DFM Mimir

Prepared 3 October 2026. Working assessment for SDU review, not an ANSSI decision.
Scope: iOS and macOS 0.1.5 (12), App Store Connect 6818524811.

## Finding

**No applicable exemption or existing declaration has been established.**
Proceed on the basis that France needs a documented resolution before completing
Apple's encryption workflow. This is not a finding that no exemption can exist.

[Apple's documentation](https://developer.apple.com/help/app-store-connect/reference/app-information/export-compliance-documentation-for-encryption)
requires a French declaration for industry-standard encryption outside the OS
when distributing in France. Both archived Flutter frameworks contain BoringSSL.
The OS-only answer therefore does not describe these builds. Keychain use alone
would not explain away the bundled TLS implementation.

## French rules assessed

Under [Decree 2007-663](https://www.legifrance.gouv.fr/loda/id/JORFTEXT000000646995/):

- Article 3 distinguishes confidentiality from authentication/integrity only.
  Mimir's HTTPS protects content confidentiality.
- Annex 1's specialized equipment categories do not clearly fit this chat app.
  Category 11 is restricted to system administration data; Mimir transfers
  queries, feedback and models. Category 12 concerns personal/development imports,
  not clearly public app supply. Category 14 concerns ultra-wideband modulation.
- Annex 2's mass-market criteria establish a declaration category for specified
  exports, not a blanket exemption from French supply formalities.
- Article 6 extends a supplier's declaration to intermediaries distributing the
  declared product under the same conditions. Coverage of a library embedded in
  a new application needs evidence; it cannot be inferred from dependency use.

Open-source availability, free pricing, optional networking and Danish university
ownership do not by themselves establish an exemption under the provisions reviewed.

## Existing coverage search

Public searches for Flutter/BoringSSL ANSSI declarations and Flutter issue reports
did not locate an attestation demonstrably covering Mimir. An ANSSI presentation
mentioning BoringSSL is not a declaration. Neither Apple's OS coverage nor a US
export classification establishes French coverage for the embedded library.

Remaining route: obtain an SDU or upstream attestation, its product/version scope,
operations and redistribution conditions, then confirm applicability to this app
with ANSSI and acceptance with Apple. Internal SDU records are not publicly
searchable; this information has been requested from the project owner.

## Prepared package and remaining administrative fields

- [Technical description](ENCRYPTION-TECHNICAL.md): implementation and evidence.
- [Unsent inquiry](ENCRYPTION-INQUIRY.md): ask ANSSI about exemption/coverage.
- [Product listing](LISTING.md), [support](SUPPORT.md) and [privacy](PRIVACY.md).
- Applicant candidate: **Syddansk Universitet / University of Southern Denmark**,
  Campusvej 55, DK-5230 Odense M, Denmark; CVR **29283958**. Verified from
  [SDU contact details](https://www.sdu.dk/da/forskning/codes) and
  [SDU sales terms](https://www.sdu.dk/en/om-sdu/salgsbetingelser).
- Pending: authorized signatory's name/title/email and authority; SDU legal/export
  contact; any existing declaration/reference; suitable current institutional
  registration evidence. Do not infer signing authority from an Apple account role.

[ANSSI's forms page](https://cyber.gouv.fr/reglementation/reglementation-identite-confiance-numerique/controles-reglementaires-cryptographie/controle-moyen-de-cryptologie/controle-reglementaire-cryptographie-formulaires/)
provides the official form. The technical description here is supporting material,
not a replacement for that form or an official attestation. Before filing, confirm
which operations and responsible supplier/importer should be named for distribution
from Denmark through Apple. Complete the current official form, have SDU review
and sign it, and supply the required institutional/product attachments. Keep
signatures and non-public personal information out of this public repository.

No inquiry, declaration or new Apple compliance submission has been sent as part
of this assessment. No exemption flag or approval code has been invented.
