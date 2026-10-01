// src/App.tsx
import { useEffect, useState } from 'react'
import Header from './components/header'
import Home from './pages/home'
import QuotePage from './pages/quote'
import ProductsPage from './pages/products'
import RefurbishedPage from './pages/refurbished'
import SoftwarePage from './pages/software'
import SupportPage from './pages/support'
import SolutionsPage from './pages/solutions'
import HelpMeChoosePage from './pages/help-me-choose'
import CartPage from './pages/cart'
import CheckoutPage from './pages/checkout'
import TrackQuotePage from './pages/track-quote'
import TrackOrderPage from './pages/track-order'
import TermsAndConditionsPage from './pages/terms-and-conditions'
import { StoreProvider } from './lib/store-context'
import './App.css'

export type Page = 'home' | 'products' | 'refurbished' | 'software' | 'support' | 'solutions' | 'help-me-choose' | 'cart' | 'checkout' | 'quote' | 'track-quote' | 'track-order' | 'terms-and-conditions'

function pageFromLocation(): Page {
  const params = new URLSearchParams(window.location.search)
  return params.get('page') === 'terms-and-conditions' ? 'terms-and-conditions' : 'home'
}

function AppContent() {
  const [currentPage, setCurrentPage] = useState<Page>(pageFromLocation)
  const [showQuote, setShowQuote] = useState(false)

  useEffect(() => {
    const handleHistory = () => setCurrentPage(pageFromLocation())
    window.addEventListener('popstate', handleHistory)
    return () => window.removeEventListener('popstate', handleHistory)
  }, [])

  const navigateTo = (page: Page) => {
    console.log('📍 Navigating to:', page);
    if (page === 'terms-and-conditions') {
      window.history.pushState(null, '', '/?page=terms-and-conditions')
    } else if (new URLSearchParams(window.location.search).get('page') === 'terms-and-conditions') {
      window.history.pushState(null, '', '/')
    }
    setCurrentPage(page)
    if (page !== 'quote') {
      setShowQuote(false)
    }
  }

  // --- NEW: Navigation function that supports data/params ---
  const handleNavigate = (page: string, data?: any) => {
    console.log('📍 Navigating with data:', page, data);

    // Handle track-order with params
    if (page === 'track-order') {
      // Set current page and store data in a state or URL
      setCurrentPage('track-order');
      // You can pass data via state or URL params
      // For simplicity, we'll use URL params and let TrackOrderPage read them
      if (data) {
        // Update URL with query params
        const queryString = new URLSearchParams(data).toString();
        window.history.pushState(null, '', `?page=track-order&${queryString}`);
      }
      return;
    }

    // Handle other pages
    if (page === 'track-quote') {
      setCurrentPage('track-quote');
      if (data) {
        const queryString = new URLSearchParams(data).toString();
        window.history.pushState(null, '', `?page=track-quote&${queryString}`);
      }
      return;
    }

    setCurrentPage(page as Page);
    if (page !== 'quote') {
      setShowQuote(false);
    }
  };

  const openQuote = () => {
    console.log('Opening quote modal');
    setShowQuote(true)
  }

  const closeQuote = () => {
    setShowQuote(false)
  }

  const navigateToStore = () => {
    setCurrentPage('products')
    setShowQuote(false)
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'home':
        return <Home onNavigate={navigateTo} />
      case 'products':
        return <ProductsPage onNavigate={navigateTo} />
      case 'refurbished':
        return <RefurbishedPage onNavigate={navigateTo} />
      case 'software':
        return <SoftwarePage />
      case 'support':
        return <SupportPage />
      case 'solutions':
        return <SolutionsPage />
      case 'help-me-choose':
        return <HelpMeChoosePage onNavigate={navigateTo} onRequestQuote={openQuote} />
      case 'cart':
        return <CartPage onNavigate={navigateTo} />
      case 'checkout':
        // ✅ FIX: Pass onNavigate prop to CheckoutPage
        return <CheckoutPage onNavigate={handleNavigate} />
      case 'quote':
        return (
          <QuotePage
            onClose={closeQuote}
            onNavigateToStore={navigateToStore}
            onNavigate={navigateTo}
          />
        );
      case 'track-quote':
        return <TrackQuotePage />
      case 'track-order':
        return <TrackOrderPage />
      case 'terms-and-conditions':
        return <TermsAndConditionsPage />
      default:
        return <Home onNavigate={navigateTo} />
    }
  }

  return (
    <>
      <Header
        onNavigate={navigateTo}
        currentPage={currentPage}
        onRequestQuote={openQuote}
      />
      <div id="center">
        {renderPage()}
      </div>

      {/* Quote Modal/Overlay */}
      {showQuote && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-sm">
          <div className="min-h-screen px-4 py-8">
            <div className="mx-auto max-w-3xl rounded-2xl bg-background shadow-2xl">
              <QuotePage
                onClose={closeQuote}
                onNavigateToStore={navigateToStore}
                onNavigate={navigateTo}
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function App() {
  return (
    <StoreProvider>
      <AppContent />
    </StoreProvider>
  )
}

export default App
