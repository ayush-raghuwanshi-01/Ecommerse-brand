import { Link } from 'react-router-dom';
import { config, getWhatsAppLink } from '../config';

export default function Footer() {
  const whatsapp = getWhatsAppLink('Hello Black House.');

  return (
    <footer>
      <Link className="wordmark" to="/">
        {config.brandName.toUpperCase()}
      </Link>

      <div>
        <Link to="/shop">Collection</Link>
        <Link to="/story">Story</Link>
        <Link to="/bulk">Bulk Orders</Link>
        {whatsapp ? (
          <a href={whatsapp} rel="noreferrer noopener">
            WhatsApp
          </a>
        ) : null}
      </div>

      {/* Policy links must be reachable from every page: e-commerce rules require
          them to be displayed, and a payment-gateway reviewer looks for them here
          first. */}
      <div className="footer-legal">
        <Link to="/policies/privacy">Privacy Policy</Link>
        <Link to="/policies/terms">Terms &amp; Conditions</Link>
        <Link to="/policies/returns">Refund &amp; Returns</Link>
        <Link to="/policies/shipping">Shipping</Link>
        <Link to="/contact">Contact</Link>
      </div>

      <Link
        to="/top"
        onClick={(e) => {
          e.preventDefault();
          window.scrollTo({ top: 0 });
        }}
      >
        Back to top ↑
      </Link>

      <small>
        © {new Date().getFullYear()} {config.legalName} · {config.city}, {config.state} · Built in small
        batches.
      </small>
    </footer>
  );
}
