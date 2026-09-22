import { Suspense, lazy, useEffect, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import AnnouncementBar from './components/AnnouncementBar';
import CartDrawer from './components/CartDrawer';
import Footer from './components/Footer';
import Nav from './components/Nav';
import { Spinner } from './components/bits';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { QuickViewProvider } from './context/QuickViewContext';
import { ToastProvider } from './context/ToastContext';
import { WishlistProvider } from './context/WishlistContext';
import WishlistPage from './pages/Wishlist';
import AccountPage from './pages/Account';
import AuthPage from './pages/Auth';
import BulkPage from './pages/Bulk';
import Checkout from './pages/Checkout';
import Home from './pages/Home';
import { OrderDetailPage, OrdersPage } from './pages/Orders';
import ProductPage from './pages/Product';
import Shop from './pages/Shop';
import StoryPage from './pages/Story';
import './styles.css';

// Legal pages are lazy-loaded: they are needed for compliance and payment-gateway
// review, but no shopper wants them in the critical path of the storefront bundle.
const PrivacyPolicyPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.PrivacyPolicyPage })));
const TermsPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.TermsPage })));
const ReturnsPolicyPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.ReturnsPolicyPage })));
const ShippingPolicyPage = lazy(() =>
  import('./pages/Legal').then((m) => ({ default: m.ShippingPolicyPage })),
);
const ContactPage = lazy(() => import('./pages/Legal').then((m) => ({ default: m.ContactPage })));

const AdminPage = lazy(() => import('./pages/Admin'));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <main className="page">
        <Spinner />
      </main>
    );
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  return <>{children}</>;
}

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => window.scrollTo({ top: 0 }), [pathname]);
  return null;
}

function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <CartProvider>
          <BrowserRouter>
            <WishlistProvider>
              <QuickViewProvider>
                <ScrollTop />
                <a className="skip-link" href="#content">
                  Skip to content
                </a>
                <div className="topbar">
                  <AnnouncementBar />
                  <Nav />
                </div>
                <div id="content">
                  <Suspense
                    fallback={
                      <main className="page">
                        <Spinner />
                      </main>
                    }
                  >
                    <Routes>
                      <Route path="/" element={<Home />} />
                      <Route path="/shop" element={<Shop />} />
                      <Route path="/wishlist" element={<WishlistPage />} />
                      <Route path="/product/:slug" element={<ProductPage />} />
                      <Route path="/story" element={<StoryPage />} />
                      <Route path="/bulk" element={<BulkPage />} />
                      <Route path="/login" element={<AuthPage />} />
                      <Route
                        path="/account"
                        element={
                          <RequireAuth>
                            <AccountPage />
                          </RequireAuth>
                        }
                      />
                      <Route path="/checkout" element={<Checkout />} />
                      <Route path="/order/:id" element={<OrderDetailPage />} />
                      <Route
                        path="/orders"
                        element={
                          <RequireAuth>
                            <OrdersPage />
                          </RequireAuth>
                        }
                      />
                      <Route path="/admin" element={<AdminPage />} />
                      {/* Legal & policy pages — required for e-commerce compliance and
                      reviewed by Razorpay during merchant KYC. */}
                      <Route path="/policies/privacy" element={<PrivacyPolicyPage />} />
                      <Route path="/policies/terms" element={<TermsPage />} />
                      <Route path="/policies/returns" element={<ReturnsPolicyPage />} />
                      <Route path="/policies/shipping" element={<ShippingPolicyPage />} />
                      <Route path="/contact" element={<ContactPage />} />
                      <Route
                        path="*"
                        element={
                          <main className="page">
                            <p className="empty">Page not found.</p>
                          </main>
                        }
                      />
                    </Routes>
                  </Suspense>
                </div>
                <Footer />
                <CartDrawer />
              </QuickViewProvider>
            </WishlistProvider>
          </BrowserRouter>
        </CartProvider>
      </ToastProvider>
    </AuthProvider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
