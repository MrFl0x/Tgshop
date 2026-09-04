import { useEffect } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import { BottomNav } from "./components/BottomNav";
import { DevBanner } from "./components/DevBanner";
import { CartProvider } from "./state/CartContext";
import { initTelegramWebApp } from "./telegram";
import { CatalogPage } from "./pages/CatalogPage";
import { ProductPage } from "./pages/ProductPage";
import { CartPage } from "./pages/CartPage";
import { CheckoutPage } from "./pages/CheckoutPage";
import { OrderStatusPage } from "./pages/OrderStatusPage";
import { OrdersListPage } from "./pages/OrdersListPage";
import { ProfilePage } from "./pages/ProfilePage";

export default function App() {
  useEffect(() => {
    initTelegramWebApp();
  }, []);

  return (
    <CartProvider>
      <HashRouter>
        <div className="app">
          <DevBanner />
          <div className="app-content">
            <Routes>
              <Route path="/" element={<CatalogPage />} />
              <Route path="/product/:id" element={<ProductPage />} />
              <Route path="/cart" element={<CartPage />} />
              <Route path="/checkout" element={<CheckoutPage />} />
              <Route path="/orders" element={<OrdersListPage />} />
              <Route path="/orders/:id" element={<OrderStatusPage />} />
              <Route path="/profile" element={<ProfilePage />} />
            </Routes>
          </div>
          <BottomNav />
        </div>
      </HashRouter>
    </CartProvider>
  );
}
