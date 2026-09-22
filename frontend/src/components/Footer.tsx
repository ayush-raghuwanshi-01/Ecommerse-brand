import { Link } from 'react-router-dom';
import { config, getWhatsAppLink } from '../config';
import { IconMail, IconPhone, IconPin, IconWhatsApp } from './bits';

export default function Footer() {
  const whatsapp = getWhatsAppLink('Hello Black House.');

  return (
    <footer>
      <div className="footer-grid">
        <div className="footer-brand">
          <Link className="wordmark" to="/">
            BLACK&nbsp;HOUSE
          </Link>
          <p>
            Small-batch outerwear cut in Bhopal, Madhya Pradesh. Heavyweight cloth, numbered runs, made to
            stay.
          </p>
          <div className="footer-contact">
            <a href={`mailto:${config.contactEmail}`}>
              <IconMail size={15} />
              {config.contactEmail}
            </a>
            {whatsapp && (
              <a href={whatsapp} rel="noreferrer noopener" target="_blank">
                <IconWhatsApp size={15} />
                WhatsApp us
              </a>
            )}
            {config.supportPhone && (
              <a href={`tel:+91${config.supportPhone}`}>
                <IconPhone size={15} />
                +91 {config.supportPhone}
              </a>
            )}
            <span>
              <IconPin size={15} />
              {config.city}, {config.state} {config.postalCode}, India
            </span>
          </div>
          {config.gstin && <small>GSTIN: {config.gstin}</small>}
        </div>

        <div className="footer-col">
          <h4>Shop</h4>
          <Link to="/shop">The collection</Link>
          <Link to="/shop">Available now</Link>
          <Link to="/shop">Pre-order</Link>
          <Link to="/bulk">Bulk & uniforms</Link>
        </div>

        <div className="footer-col">
          <h4>Company</h4>
          <Link to="/story">Our story</Link>
          <Link to="/contact">Contact us</Link>
          <Link to="/orders">Track your order</Link>
          <a
            href="#top"
            onClick={(e) => {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
          >
            Back to top
          </a>
        </div>

        <div className="footer-col">
          <h4>Policies</h4>
          <Link to="/policies/privacy">Privacy Policy</Link>
          <Link to="/policies/terms">Terms &amp; Conditions</Link>
          <Link to="/policies/returns">Refund &amp; Returns</Link>
          <Link to="/policies/shipping">Shipping Policy</Link>
        </div>
      </div>

      <div className="footer-bottom">
        <small>
          © {new Date().getFullYear()} {config.legalName} · {config.city}, {config.state} · All prices include
          GST
        </small>
        <div className="footer-pays" aria-label="Payment methods accepted">
          <span>UPI</span>
          <span>Razorpay</span>
          <span>COD</span>
          <span>Cards</span>
        </div>
      </div>
    </footer>
  );
}
