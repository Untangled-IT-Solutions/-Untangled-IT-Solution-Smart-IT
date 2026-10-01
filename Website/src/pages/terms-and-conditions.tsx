import { FileText, Mail } from "lucide-react";

const TERMS = [
  {
    title: "Quotations, pricing and VAT",
    text: "Quotations are issued in South African Rand (ZAR). Prices exclude VAT unless the quotation states otherwise, and VAT is charged at the applicable rate. Pricing remains valid only for the period shown on the quotation. After expiry, pricing and availability may be confirmed again before an order is accepted.",
  },
  {
    title: "Acceptance and payment",
    text: "A signed quotation, written electronic acceptance or valid purchase order confirms the accepted scope, subject to applicable law. Procurement and work begin after any required deposit or cleared payment unless approved account terms state otherwise. The client is responsible for ensuring that its purchase order matches the accepted quotation.",
  },
  {
    title: "Product availability and substitutions",
    text: "Products, exchange-rate pricing and lead times remain subject to distributor or manufacturer confirmation. Untangled IT Solutions will not make a material product substitution without the client's written approval. Equivalent alternatives may be proposed when the quoted product is unavailable or discontinued.",
  },
  {
    title: "Delivery and collection",
    text: "Delivery dates are estimates calculated from order confirmation, receipt of required payment and supplier confirmation. Untangled IT Solutions will communicate material supplier, manufacturer, courier or other delays outside its reasonable control. The client must provide accurate delivery and contact information.",
  },
  {
    title: "Scope of products and services",
    text: "Only products and services expressly listed in the accepted quotation are included. Installation, structured cabling, migration, configuration, training, data transfer, travel and after-hours work are excluded unless itemised. Additional work requested by the client may require a revised quotation or written change approval.",
  },
  {
    title: "Manufacturer warranties and support",
    text: "Hardware carries the OEM or distributor warranty stated in the quotation or product documentation. Warranty claims are handled through the applicable manufacturer or supplier process. Misuse, accidental damage, unauthorised modification or operation outside manufacturer guidance may affect warranty cover. Mandatory rights under South African law remain unaffected.",
  },
  {
    title: "Returns, cancellations and defective goods",
    text: "Returns and cancellations are handled in accordance with applicable South African law and relevant supplier return-authorisation processes. Where legally permitted, opened, activated, special-order or correctly supplied non-defective products may attract restocking or cancellation charges or may be non-returnable. Nothing in these terms limits remedies that cannot lawfully be excluded.",
  },
  {
    title: "Software, cloud services and subscriptions",
    text: "Software, cloud services and subscriptions are governed by the relevant publisher or provider licence terms. The client is responsible for lawful use and suitable licensing. Activated licences, digital products and commenced subscriptions may be non-refundable where the law permits. Renewal charges apply only when included in the accepted order or separately authorised.",
  },
  {
    title: "Risk and ownership",
    text: "Risk in physical goods passes to the client on delivery or collection. Ownership remains with Untangled IT Solutions until full payment has cleared, subject to applicable law. The client must inspect deliveries promptly and report visible shortages or transit damage as soon as reasonably possible.",
  },
  {
    title: "Client systems, data and access",
    text: "The client must maintain current, tested backups before installation, repair, configuration or migration work. Access credentials must be provided through an agreed secure method and changed after completion where appropriate. Untangled IT Solutions will take reasonable care when handling client equipment, systems and information.",
  },
  {
    title: "Limitation of liability",
    text: "To the extent permitted by law, liability is limited to direct loss up to the value of the affected quotation or service. Untangled IT Solutions is not liable for indirect or consequential loss arising from matters outside its reasonable control. This clause does not exclude liability or rights that cannot lawfully be limited, including liability for fraud, wilful misconduct or gross negligence.",
  },
  {
    title: "Applicable law and mandatory rights",
    text: "These terms are governed by the laws of South Africa. Written or electronic acceptance may constitute acceptance under applicable law. Nothing in these terms limits applicable rights that cannot lawfully be excluded, including qualifying rights under the Consumer Protection Act.",
  },
];

export default function TermsAndConditionsPage() {
  return (
    <main className="min-h-screen bg-background pb-20 pt-10 text-foreground sm:pt-14">
      <header className="border-b border-border bg-muted/40">
        <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
          <div className="flex items-center gap-3 text-[#839705]">
            <FileText className="h-5 w-5" aria-hidden="true" />
            <span className="text-sm font-semibold uppercase">Customer information</span>
          </div>
          <h1 className="mt-4 text-3xl font-bold sm:text-4xl">Quotation Terms and Conditions</h1>
          <p className="mt-4 max-w-3xl text-base leading-7 text-muted-foreground">
            These terms apply to quotations issued by Untangled IT Solutions (Pty) Ltd unless a signed agreement expressly replaces them.
          </p>
          <p className="mt-3 text-sm text-muted-foreground">Effective date: 1 October 2026</p>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="grid gap-x-12 gap-y-9 md:grid-cols-2">
          {TERMS.map((term, index) => (
            <section key={term.title} aria-labelledby={`term-${index + 1}`}>
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#839705] text-sm font-bold text-white">
                  {index + 1}
                </span>
                <div>
                  <h2 id={`term-${index + 1}`} className="text-base font-bold text-foreground">
                    {term.title}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{term.text}</p>
                </div>
              </div>
            </section>
          ))}
        </div>

        <section className="mt-14 border-t border-border pt-8">
          <h2 className="text-lg font-bold">Questions about these terms</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Ask us to clarify any condition before accepting a quotation. A quotation-specific written condition takes precedence where it expressly changes these standard terms.
          </p>
          <a
            href="mailto:accounts@untangledits.co.za"
            className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#718204] underline decoration-[#839705]/40 underline-offset-4 hover:text-[#839705]"
          >
            <Mail className="h-4 w-4" aria-hidden="true" />
            accounts@untangledits.co.za
          </a>
        </section>
      </div>
    </main>
  );
}
