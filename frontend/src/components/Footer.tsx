import { Link } from 'react-router-dom';
import { getWhatsAppLink } from '../config';

export default function Footer() {
  return (
    <footer>
      <Link className="wordmark" to="/">
        BLACK HOUSE
      </Link>
      <div>
        <Link to="/shop">Collection</Link>
        <Link to="/story">Story</Link>
        <Link to="/bulk">Bulk Orders</Link>
        <a href={getWhatsAppLink('Hello Black House.')}>WhatsApp</a>
      </div>
      <Link to="/top" onClick={(e) => { e.preventDefault(); window.scrollTo({ top: 0 }); }}>
        Back to top ↑
      </Link>
      <small>© 2026 Black House · Bhopal, Madhya Pradesh · Built in small batches.</small>
    </footer>
  );
}
