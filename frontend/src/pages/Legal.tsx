import type { ReactNode } from 'react';
import { Seo } from '../components/bits';
import { config } from '../config';

/**
 * Legal and policy pages.
 *
 * These are not boilerplate decoration — they are load-bearing in two ways:
 *
 * 1. **Compliance.** The Consumer Protection (E-Commerce) Rules 2020 require a
 *    seller to display its legal name, address, contact details, and the terms
 *    of sale, return and refund. The Information Technology Act 2000 and the
 *    SPDI Rules 2011 require a published privacy policy naming a grievance
 *    officer.
 * 2. **Payment gateway approval.** Razorpay reviews the live site during KYC and
 *    rejects applications without a reachable refund policy, privacy policy,
 *    terms and contact page. No policy pages means no ability to take payments.
 *
 * Every business-specific value comes from `config` (i.e. `VITE_*` env vars) so
 * the copy never contradicts the registered details. Values that have not been
 * supplied yet render as a visible `[TO BE COMPLETED]` marker rather than an
 * empty line — a reviewer must never see a policy with a blank address, and we
 * must never accidentally ship plausible-looking but invented details.
 */

const PLACEHOLDER = '[TO BE COMPLETED]';

const need = (value: string): ReactNode =>
  value && value !== '—' ? value : <mark className="todo">{PLACEHOLDER}</mark>;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="legal-section">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function LegalShell({
  title,
  meta,
  updated,
  children,
}: {
  title: string;
  meta: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <main className="page legal">
      <Seo title={`${title} — ${config.brandName}`} description={meta} />
      <header className="page-head">
        <p className="eyebrow">Legal</p>
        <h1>{title}</h1>
        <p className="legal-updated">Last updated: {updated}</p>
      </header>
      <div className="legal-body">{children}</div>
      <nav className="legal-nav" aria-label="Other policies">
        <a href="/policies/privacy">Privacy Policy</a>
        <a href="/policies/terms">Terms &amp; Conditions</a>
        <a href="/policies/returns">Refund &amp; Return Policy</a>
        <a href="/policies/shipping">Shipping Policy</a>
        <a href="/contact">Contact</a>
      </nav>
    </main>
  );
}

/** Registered seller block reused across every policy. */
function SellerIdentity() {
  return (
    <address className="legal-address">
      <strong>{need(config.legalName)}</strong>
      <br />
      {need(config.addressLine1)}
      {config.addressLine2 ? (
        <>
          <br />
          {config.addressLine2}
        </>
      ) : null}
      <br />
      {config.city}
      {config.postalCode ? ` – ${config.postalCode}` : ''}, {config.state}
      <br />
      {config.country}
      {config.gstin ? (
        <>
          <br />
          GSTIN: {config.gstin}
        </>
      ) : (
        <>
          <br />
          GSTIN: {need('')}
        </>
      )}
      <br />
      Email: <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>
      {config.supportPhone ? (
        <>
          <br />
          Phone: <a href={`tel:+${config.supportPhone}`}>+{config.supportPhone}</a>
        </>
      ) : null}
    </address>
  );
}

const UPDATED = '13 September 2026';

// ══════════════════════════════════════════════════════════════════════════
// Privacy Policy
// ══════════════════════════════════════════════════════════════════════════

export function PrivacyPolicyPage() {
  return (
    <LegalShell
      title="Privacy Policy"
      meta={`How ${config.brandName} collects, uses and protects your personal information.`}
      updated={UPDATED}
    >
      <p>
        This privacy policy describes how {need(config.legalName)} (&ldquo;we&rdquo;, &ldquo;us&rdquo;)
        collects, uses, discloses and protects your personal information when you use this website or purchase
        from us. It is published under the Information Technology Act, 2000 and the Information Technology
        (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011.
      </p>

      <Section title="1. Information we collect">
        <ul>
          <li>
            <strong>Account details</strong> — name, email address, phone number and a password stored only as
            a cryptographic hash. We never store plaintext passwords.
          </li>
          <li>
            <strong>Delivery information</strong> — shipping address, PIN code and a contact number for the
            courier.
          </li>
          <li>
            <strong>Order and payment records</strong> — items purchased, amounts, GST components, order
            status and return history.
          </li>
          <li>
            <strong>Payment credentials</strong> — we do <em>not</em> collect or store card numbers, UPI
            credentials or net-banking details. Payments are processed by Razorpay on their own
            PCI-DSS-compliant infrastructure; we receive only a transaction reference and its status.
          </li>
          <li>
            <strong>Technical data</strong> — IP address, browser user agent and request identifiers, recorded
            for security, rate limiting and audit purposes.
          </li>
          <li>
            <strong>Enquiries</strong> — anything you send us through the bulk-order form, WhatsApp or email.
          </li>
        </ul>
      </Section>

      <Section title="2. Why we use it">
        <ul>
          <li>To process and deliver your order, and to issue a GST invoice.</li>
          <li>To take payment, verify it, and process refunds and returns.</li>
          <li>
            To send transactional messages about your order — confirmation, dispatch, tracking, delivery, and
            return or refund status.
          </li>
          <li>To provide customer support and respond to enquiries.</li>
          <li>
            To prevent fraud, enforce our terms, and keep an audit trail of staff actions on your order.
          </li>
          <li>To meet statutory obligations, including tax and accounting record-keeping.</li>
        </ul>
        <p>
          We do not sell your personal information. We do not use it for advertising profiles or share it with
          data brokers.
        </p>
      </Section>

      <Section title="3. Who we share it with">
        <p>Only with parties necessary to fulfil an order or meet a legal obligation:</p>
        <ul>
          <li>
            <strong>Razorpay</strong> — payment processing. See their{' '}
            <a href="https://razorpay.com/privacy/" rel="noreferrer noopener">
              privacy policy
            </a>
            .
          </li>
          <li>
            <strong>Courier and logistics partners</strong> — name, address and phone number, so the parcel
            can be delivered.
          </li>
          <li>
            <strong>Resend</strong> — email delivery, receiving your address and the transactional message
            content.
          </li>
          <li>
            <strong>Cloudinary</strong> — serves product imagery. It does not receive your personal data.
          </li>
          <li>
            <strong>Our hosting provider</strong> — stores the database under our instruction.
          </li>
          <li>
            <strong>Government and law enforcement</strong> — only where we are legally compelled to disclose.
          </li>
        </ul>
      </Section>

      <Section title="4. Cookies and local storage">
        <p>
          We use browser local storage to keep you signed in between visits and to maintain your cart. These
          are strictly necessary for the service to function — we do not use third-party advertising or
          cross-site tracking cookies. Clearing your browser storage signs you out and empties an unsaved
          cart.
        </p>
      </Section>

      <Section title="5. How long we keep it">
        <p>
          Account and order records are retained for as long as your account is active, and thereafter for the
          period required by Indian tax and company law (currently eight financial years for transaction
          records). Security and audit logs are retained for a limited period and then deleted. You may
          request deletion of your account, subject to our obligation to retain records the law requires us to
          keep.
        </p>
      </Section>

      <Section title="6. How we protect it">
        <ul>
          <li>Passwords hashed with Argon2id, never stored or logged in plain text.</li>
          <li>Short-lived access tokens with rotating, revocable refresh tokens and reuse detection.</li>
          <li>Transport encryption (TLS) on every request.</li>
          <li>Rate limiting on authentication and sensitive endpoints.</li>
          <li>
            An append-only audit log of privileged staff actions, recording who did what and from where.
          </li>
          <li>Least-privilege database and storage credentials.</li>
        </ul>
        <p>
          No system is perfectly secure. If a breach affects your personal data and creates a real risk to
          you, we will notify you and the appropriate authority without undue delay.
        </p>
      </Section>

      <Section title="7. Your rights">
        <p>
          You may request access to, correction of, or deletion of your personal information; withdraw consent
          to non-essential processing; or complain to the grievance officer below. Write to{' '}
          <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a> from your registered address. We
          will acknowledge within 48 hours and respond within 30 days.
        </p>
      </Section>

      <Section title="8. Grievance officer">
        <p>As required by the Information Technology Act, 2000, our grievance officer can be contacted at:</p>
        <SellerIdentity />
      </Section>

      <Section title="9. Children">
        <p>
          Our products are adult outerwear and our services are not directed at children under 18. We do not
          knowingly collect personal information from minors.
        </p>
      </Section>

      <Section title="10. Changes">
        <p>
          We may update this policy. Material changes will be announced on this page with a revised date, and
          where we hold your email address we will notify you before the change takes effect.
        </p>
      </Section>
    </LegalShell>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Terms & Conditions
// ══════════════════════════════════════════════════════════════════════════

export function TermsPage() {
  return (
    <LegalShell
      title="Terms & Conditions"
      meta={`The terms on which ${config.brandName} sells and you buy.`}
      updated={UPDATED}
    >
      <p>
        These terms form the contract between you and {need(config.legalName)} when you use this website or
        place an order. By ordering, you accept them. Please also read our{' '}
        <a href="/policies/privacy">Privacy Policy</a>,{' '}
        <a href="/policies/returns">Refund &amp; Return Policy</a> and{' '}
        <a href="/policies/shipping">Shipping Policy</a>.
      </p>

      <Section title="1. The seller">
        <SellerIdentity />
      </Section>

      <Section title="2. Products">
        <ul>
          <li>
            Every piece is produced in small, numbered runs. Colour and texture vary naturally between batches
            of wool and cotton, and screen calibration varies between devices, so the garment you receive may
            differ slightly from the photograph.
          </li>
          <li>
            Fabric composition, fit guidance and care instructions are stated on each product page and form
            part of the description of the goods.
          </li>
          <li>
            A product marked <em>upcoming</em> is shown before it is available. It can only be purchased when
            pre-order is explicitly open, and the stated pre-order fulfilment window applies.
          </li>
        </ul>
      </Section>

      <Section title="3. Prices and taxes">
        <ul>
          <li>
            All prices are in Indian Rupees and are <strong>inclusive of GST</strong>. The tax component of
            each line is shown on your order and on the invoice.
          </li>
          <li>
            Shipping is calculated at checkout from your PIN code or state, and is free above the threshold
            stated at checkout.
          </li>
          <li>
            We may correct a pricing error before dispatch. If a price changes between adding an item to your
            cart and checkout, the checkout step will tell you and ask you to re-confirm — you are never
            charged a price you have not seen.
          </li>
          <li>A GST invoice is issued for every order and is available from your order page.</li>
        </ul>
      </Section>

      <Section title="4. Ordering and contract formation">
        <ol>
          <li>Adding an item to your cart is an invitation to treat, not an offer.</li>
          <li>Your order is an offer to buy. Stock is reserved for you for a short window while you pay.</li>
          <li>
            The contract is formed when we confirm the order — on successful payment for prepaid orders, or on
            our acceptance of a cash-on-delivery order.
          </li>
          <li>
            We may decline an order — for example where stock has been exhausted, an address is unserviceable,
            or we suspect fraud — and will refund any amount taken.
          </li>
        </ol>
      </Section>

      <Section title="5. Payment">
        <ul>
          <li>
            Card, UPI and net-banking payments are processed by Razorpay. Cash on delivery is available where
            your PIN code permits it.
          </li>
          <li>
            If a payment attempt fails, you may retry after a short cooldown. Your reservation is released
            when the payment window expires, and the items return to general stock.
          </li>
          <li>
            For cash-on-delivery orders, please have the exact amount ready. Our delivery partner collects it
            on our behalf.
          </li>
        </ul>
      </Section>

      <Section title="6. Your account">
        <p>
          You are responsible for keeping your password confidential and for activity under your account. Tell
          us immediately at <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a> if you believe
          it has been misused. We may suspend an account used fraudulently or in breach of these terms.
        </p>
      </Section>

      <Section title="7. Cancellation">
        <p>
          You may request cancellation before your order is packed. Once it is packed or shipped, cancellation
          requires our approval — see the <a href="/policies/returns">Refund &amp; Return Policy</a>. Approved
          cancellations of prepaid orders are refunded to the original payment method.
        </p>
      </Section>

      <Section title="8. Acceptable use">
        <p>
          You agree not to probe or disrupt the service, attempt unauthorised access, submit fraudulent
          orders, scrape the catalogue at volume, resell access, or use the site for any unlawful purpose.
        </p>
      </Section>

      <Section title="9. Intellectual property">
        <p>
          The {config.brandName} name, logo, product designs, photography and site content are ours or
          licensed to us. You may not reproduce them commercially without written permission. Nothing here
          transfers ownership to you beyond the goods you have bought.
        </p>
      </Section>

      <Section title="10. Limitation of liability">
        <p>
          Our total liability for any order is limited to the amount you paid for that order, except where
          Indian law does not permit such a limit — including liability for death or personal injury caused by
          negligence, or for fraud. We are not liable for indirect or consequential loss, or for delays caused
          by carriers, payment providers or events beyond our reasonable control.
        </p>
        <p>
          Nothing in these terms excludes your statutory consumer rights, including the right to goods of
          satisfactory quality and fit for their purpose.
        </p>
      </Section>

      <Section title="11. Force majeure">
        <p>
          We are not liable for failure or delay caused by events outside our reasonable control — natural
          disaster, epidemic, industrial action, courier failure, payment-provider outage, or government
          restriction. We will tell you promptly and, where an order cannot be fulfilled, refund it in full.
        </p>
      </Section>

      <Section title="12. Governing law and disputes">
        <p>
          These terms are governed by the laws of India. Courts at Bhopal, Madhya Pradesh have exclusive
          jurisdiction, without prejudice to your right as a consumer to bring proceedings where you reside.
          Any consumer complaint may be raised with the grievance officer named in our{' '}
          <a href="/policies/privacy">Privacy Policy</a>, and you retain the right to approach a consumer
          forum under the Consumer Protection Act, 2019.
        </p>
      </Section>

      <Section title="13. Changes to these terms">
        <p>
          We may update these terms. The version in force is the one published at the time you order, and
          material changes will be announced on this page.
        </p>
      </Section>
    </LegalShell>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Refund & Return Policy
// ══════════════════════════════════════════════════════════════════════════

export function ReturnsPolicyPage() {
  const days = config.returnWindowDays;
  return (
    <LegalShell
      title="Refund & Return Policy"
      meta={`${days}-day returns, exchanges and refunds at ${config.brandName}.`}
      updated={UPDATED}
    >
      <p>
        We want you to keep something you love. If a piece does not work, you have{' '}
        <strong>{days} days from delivery</strong> to request a return, exchange or replacement.
      </p>

      <Section title="1. Eligibility">
        <ul>
          <li>Requested within {days} days of the delivery date recorded on your order.</li>
          <li>Unworn, unwashed and undamaged, with all original tags attached.</li>
          <li>Returned in the original packaging where you still have it.</li>
          <li>Accompanied by the order number.</li>
        </ul>
      </Section>

      <Section title="2. What we offer">
        <ul>
          <li>
            <strong>Size exchange</strong> — swap for a different size of the same piece, subject to
            availability.
          </li>
          <li>
            <strong>Product exchange</strong> — swap for a different piece. Any price difference is settled at
            the time of exchange.
          </li>
          <li>
            <strong>Replacement</strong> — a new unit where the original is damaged, defective or the wrong
            item was sent.
          </li>
          <li>
            <strong>Refund</strong> — to your original payment method. Available for full-price items.
          </li>
        </ul>
      </Section>

      <Section title="3. Exclusions">
        <ul>
          <li>
            <strong>Sale items</strong> can be exchanged or replaced but are{' '}
            <strong>not eligible for a cash refund</strong>. Every sale item is marked as such on its product
            page before you buy.
          </li>
          <li>Items that are worn, washed, altered, damaged by misuse, or returned without tags.</li>
          <li>Requests made after the {days}-day window has closed.</li>
        </ul>
      </Section>

      <Section title="4. Return shipping">
        <ul>
          <li>
            <strong>We pay</strong> where the item arrived damaged, defective, or was the wrong item —
            including reverse pickup where our courier partner supports it.
          </li>
          <li>
            <strong>You pay</strong> for a change-of-mind return or a size exchange, unless we tell you
            otherwise in writing.
          </li>
        </ul>
      </Section>

      <Section title="5. How to request a return">
        <ol>
          <li>
            Sign in and open <a href="/orders">your orders</a>, then choose the order and select the item you
            want to return.
          </li>
          <li>Choose the reason and the outcome you want — refund, exchange or replacement.</li>
          <li>We review the request. Approval or rejection is recorded on the order and emailed to you.</li>
          <li>
            If approved, send the item back using the address and instructions on your order page, or await
            reverse pickup where that has been arranged.
          </li>
          <li>We inspect the item on arrival and complete the refund, exchange or replacement.</li>
        </ol>
        <p>
          You can also start a return by writing to{' '}
          <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>.
        </p>
      </Section>

      <Section title="6. When a refund becomes due">
        <p>
          A refund becomes <strong>eligible</strong> once the returned item is picked up or received, and is{' '}
          <strong>completed</strong> after our inspection confirms it meets the conditions above. If an
          inspection finds the item worn, damaged or outside policy, we will contact you before doing anything
          else, and may return the item to you.
        </p>
      </Section>

      <Section title="7. Refund timelines">
        <p>
          Approved refunds are issued to the original payment method. We initiate them promptly after
          inspection; the time they take to appear is set by your bank or card issuer and is typically{' '}
          <strong>5–7 working days</strong>. Cash-on-delivery orders have no prepayment to refund — a COD
          return is handled as an exchange or replacement, or by bank transfer where a refund is genuinely
          due.
        </p>
      </Section>

      <Section title="8. Cancellations">
        <p>
          You may request cancellation before your order is packed. After packing, cancellation needs our
          approval. An approved cancellation of a prepaid order is refunded on the same timeline as above.
        </p>
      </Section>

      <Section title="9. Damaged or incorrect deliveries">
        <p>
          If your parcel arrives damaged, or contains the wrong item, contact us within 48 hours with
          photographs. We will arrange a replacement or a full refund and cover the return shipping.
        </p>
      </Section>

      <Section title="10. Contact">
        <SellerIdentity />
        <p>Support hours: {config.supportHours}.</p>
      </Section>
    </LegalShell>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Shipping Policy
// ══════════════════════════════════════════════════════════════════════════

export function ShippingPolicyPage() {
  return (
    <LegalShell
      title="Shipping Policy"
      meta={`Dispatch times, charges, tracking and serviceability for ${config.brandName}.`}
      updated={UPDATED}
    >
      <Section title="1. Dispatch">
        <p>
          Orders are prepared and dispatched from our fulfilment centre in {config.city}, {config.state}.
          Small-batch pieces are finished and checked by hand before dispatch, so please allow the handling
          time shown at checkout. Pre-orders ship within the window stated on the product page.
        </p>
      </Section>

      <Section title="2. Delivery time">
        <p>
          Typical delivery is <strong>{config.shippingSlaDays}</strong> after dispatch, depending on
          destination. Remote locations may take longer. You will receive tracking by email as soon as the
          parcel is handed to the courier.
        </p>
      </Section>

      <Section title="3. Charges">
        <ul>
          <li>Shipping is calculated at checkout from your PIN code or state.</li>
          <li>Free shipping applies to orders above the threshold shown at checkout.</li>
          <li>Any charge is displayed before you pay — it is never added afterwards.</li>
        </ul>
      </Section>

      <Section title="4. Where we deliver">
        <p>
          We deliver across India. Some PIN codes are not serviceable by our courier partners, and checkout
          will tell you before you pay if your PIN code cannot be served. If you are unsure, check at checkout
          or write to <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>. International
          shipping is not currently offered.
        </p>
      </Section>

      <Section title="5. Tracking">
        <p>
          Tracking details appear on <a href="/orders">your order page</a> and are emailed to you. Carriers
          usually scan a parcel within a few hours of dispatch, so tracking may not update immediately.
        </p>
      </Section>

      <Section title="6. Cash on delivery">
        <p>
          COD is available where your PIN code permits it. Please keep the exact amount ready; our delivery
          partner collects payment on our behalf and records it against your order.
        </p>
      </Section>

      <Section title="7. Failed and undelivered parcels">
        <p>
          If a courier attempt fails, they will normally retry. If a parcel is returned to us undelivered —
          because of an incorrect address, an unavailable recipient or a refusal at the door — we will contact
          you. Re-shipping is at your cost unless the failure was ours. A prepaid order returned undelivered
          is refunded after the parcel reaches us.
        </p>
      </Section>

      <Section title="8. Delays">
        <p>
          Courier delays, weather and local disruptions are outside our control. If your parcel is materially
          late, contact us and we will investigate with the carrier and keep you informed.
        </p>
      </Section>

      <Section title="9. Contact">
        <SellerIdentity />
        <p>Support hours: {config.supportHours}.</p>
      </Section>
    </LegalShell>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// Contact
// ══════════════════════════════════════════════════════════════════════════

export function ContactPage() {
  return (
    <LegalShell
      title="Contact"
      meta={`How to reach ${config.brandName} — email, phone, WhatsApp and post.`}
      updated={UPDATED}
    >
      <p>
        We are a small team in {config.city} and a person reads every message. Support hours are{' '}
        {config.supportHours}.
      </p>

      <Section title="Registered address">
        <SellerIdentity />
      </Section>

      <Section title="Fastest routes">
        <ul>
          <li>
            <strong>Order questions</strong> — open <a href="/orders">your orders</a> first; status, tracking
            and returns are all there.
          </li>
          <li>
            <strong>Email</strong> — <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>
          </li>
          {config.supportPhone ? (
            <li>
              <strong>Phone</strong> — <a href={`tel:+${config.supportPhone}`}>+{config.supportPhone}</a>
            </li>
          ) : null}
          <li>
            <strong>Bulk and wholesale</strong> — use the <a href="/bulk">bulk enquiry form</a> and we will
            respond with pricing and lead times.
          </li>
        </ul>
      </Section>

      <Section title="Grievances">
        <p>
          Under the Information Technology Act, 2000 and the Consumer Protection (E-Commerce) Rules, 2020,
          complaints may be addressed to our grievance officer at the address above, or by email to{' '}
          <a href={`mailto:${config.contactEmail}`}>{config.contactEmail}</a>. We acknowledge complaints
          within 48 hours and aim to resolve them within 30 days. This does not affect your right to approach
          a consumer forum.
        </p>
      </Section>

      <Section title="Response times">
        <ul>
          <li>Order and delivery enquiries — 1 business day.</li>
          <li>Return and refund requests — reviewed within 2 business days.</li>
          <li>Bulk enquiries — 2–3 business days.</li>
          <li>Complaints — acknowledged within 48 hours.</li>
        </ul>
      </Section>
    </LegalShell>
  );
}
