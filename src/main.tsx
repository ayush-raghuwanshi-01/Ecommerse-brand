import { Suspense, lazy, useEffect, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import CartDrawer from './components/CartDrawer';
import Footer from './components/Footer';
import Nav from './components/Nav';
import { Spinner } from './components/bits';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CartProvider } from './context/CartContext';
import { ToastProvider } from './context/ToastContext';
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

const AdminPage = lazy(() => import('./pages/Admin'));

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <main className="page"><Spinner /></main>;
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
            <ScrollTop />
            <a className="skip-link" href="#content">Skip to content</a>
            <Nav />
            <div id="content">
              <Suspense fallback={<main className="page"><Spinner /></main>}>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/shop" element={<Shop />} />
                  <Route path="/product/:slug" element={<ProductPage />} />
                  <Route path="/story" element={<StoryPage />} />
                  <Route path="/bulk" element={<BulkPage />} />
                  <Route path="/login" element={<AuthPage />} />
                  <Route path="/account" element={<RequireAuth><AccountPage /></RequireAuth>} />
                  <Route path="/checkout" element={<RequireAuth><Checkout /></RequireAuth>} />
                  <Route path="/orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
                  <Route path="/order/:id" element={<RequireAuth><OrderDetailPage /></RequireAuth>} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="*" element={<main className="page"><p className="empty">Page not found.</p></main>} />
                </Routes>
              </Suspense>
            </div>
            <Footer />
            <CartDrawer />
          </BrowserRouter>
        </CartProvider>
      </ToastProvider>
    </AuthProvider>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
