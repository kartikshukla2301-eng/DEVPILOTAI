import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { PageLoader } from "./components/ui";
import { useAuth } from "./context/AuthContext";
import { NotificationProvider } from "./context/NotificationContext";
import { LoginPage, RegisterPage } from "./pages/AuthPages";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const CodeReview = lazy(() => import("./pages/CodeReview"));
const Debugger = lazy(() => import("./pages/Debugger"));
const Explainer = lazy(() => import("./pages/Explainer"));
const Optimizer = lazy(() => import("./pages/Optimizer"));
const Documentation = lazy(() => import("./pages/Documentation"));
const History = lazy(() => import("./pages/History"));
const HistoryDetail = lazy(() => import("./pages/HistoryDetail"));
const SettingsPage = lazy(() => import("./pages/Settings"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Landing = lazy(() => import("./pages/Landing"));

/** "/" shows the landing page to visitors and sends signed-in users to their dashboard. */
function Root() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/dashboard" replace /> : <Landing />;
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="flex h-full items-center justify-center"><PageLoader label="Loading your workspace…" /></div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/dashboard" replace /> : <>{children}</>;
}

export default function App() {
  const { user } = useAuth();
  return (
    <NotificationProvider userId={user?.id ?? null}>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
          <Route path="/" element={<Root />} />
          <Route path="/home" element={<Landing />} />
          <Route element={<Protected><AppLayout /></Protected>}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/review" element={<CodeReview />} />
            <Route path="/debug" element={<Debugger />} />
            <Route path="/explain" element={<Explainer />} />
            <Route path="/optimize" element={<Optimizer />} />
            <Route path="/docs" element={<Documentation />} />
            <Route path="/history" element={<History />} />
            <Route path="/history/:type/:id" element={<HistoryDetail />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    </NotificationProvider>
  );
}
