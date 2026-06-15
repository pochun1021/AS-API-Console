import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { apiClient } from "./api/client";
import AppLayout from "./components/AppLayout";
import { clearOAuthAuthContext, readOAuthAuthContext } from "./authContext";
import { detectSystemLocale, useLocale } from "./i18n/locale";
import ApplyPage from "./pages/ApplyPage";
import LoginDeniedPage from "./pages/LoginDeniedPage";
import LoginErrorPage from "./pages/LoginErrorPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import AdminPage from "./pages/AdminPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import LimitStrategiesPage from "./pages/LimitStrategiesPage";
import InstituteViewPage from "./pages/InstituteViewPage";
import ModelsPage from "./pages/ModelsPage";
import OperationAuditLogsPage from "./pages/OperationAuditLogsPage";
import WhitelistAdminPage from "./pages/WhitelistAdminPage";
import { redirectToLogin } from "./utils/navigation";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [auth, setAuth] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [logoutInProgress, setLogoutInProgress] = useState(false);
  const [localeReady, setLocaleReady] = useState(false);
  const { setLocale } = useLocale();
  const isLoginDeniedRoute = location.pathname === "/login-denied";
  const isLoginErrorRoute = location.pathname === "/login-error";

  function navigateToLoginError(error) {
    const route = error?.payload?.route || "users_me";
    const reason = error?.payload?.reason || "session_restore_failed";
    const requestId = error?.payload?.request_id || "";
    const params = new URLSearchParams({ route, reason });
    if (requestId) params.set("request_id", requestId);
    navigate(`/login-error?${params.toString()}`, { replace: true });
  }

  function changeLocale(nextLocale) {
    setLocale(nextLocale);
    apiClient.updateLocalePreference(nextLocale, auth).catch(() => {
      // Do not block UI locale switch when persistence fails.
    });
  }

  async function handleLogout() {
    if (logoutInProgress) return;
    setLogoutInProgress(true);
    try {
      await apiClient.logout(auth);
    } catch {
      // Best effort logout: clear local auth state and force re-login.
    } finally {
      clearOAuthAuthContext();
      setAuth(null);
      setLogoutInProgress(false);
      redirectToLogin();
    }
  }

  useEffect(() => {
    let canceled = false;
    async function bootstrapAuth() {
      if (isLoginDeniedRoute || isLoginErrorRoute) {
        if (!canceled) {
          setAuthReady(true);
          setLocale(detectSystemLocale());
          setLocaleReady(true);
        }
        return;
      }
      try {
        const devAuth = readOAuthAuthContext();
        const currentUser = await apiClient.getCurrentUser(devAuth);
        if (!canceled) {
          setAuth(currentUser);
        }
      } catch (error) {
        if (canceled) return;
        if (error?.status >= 500) {
          navigateToLoginError(error);
        } else {
          redirectToLogin();
        }
      } finally {
        if (!canceled) {
          setAuthReady(true);
        }
      }
    }
    bootstrapAuth();
    return () => {
      canceled = true;
    };
  }, [isLoginDeniedRoute, isLoginErrorRoute, navigate, setLocale]);

  useEffect(() => {
    if (!auth) return;
    let canceled = false;
    async function initLocale() {
      try {
        const preference = await apiClient.getLocalePreference(auth);
        if (canceled) return;
        if (preference?.preferred_locale === "zh-TW" || preference?.preferred_locale === "en") {
          setLocale(preference.preferred_locale);
          return;
        }

        const systemLocale = detectSystemLocale();
        setLocale(systemLocale);
        try {
          await apiClient.updateLocalePreference(systemLocale, auth);
        } catch {
          // Keep running with current UI locale when initial persistence fails.
        }
      } finally {
        if (!canceled) setLocaleReady(true);
      }
    }
    setLocaleReady(false);
    initLocale();
    return () => {
      canceled = true;
    };
  }, [auth, setLocale]);

  if (isLoginDeniedRoute || isLoginErrorRoute) {
    return (
      <Routes>
        <Route path="/login-denied" element={<LoginDeniedPage />} />
        <Route path="/login-error" element={<LoginErrorPage />} />
        <Route path="*" element={<Navigate to="/login-denied" replace />} />
      </Routes>
    );
  }

  if (!authReady || !auth || !localeReady) {
    return null;
  }

  return (
    <AppLayout auth={auth} onChangeLocale={changeLocale} onLogout={handleLogout} logoutInProgress={logoutInProgress}>
      <Routes>
        <Route path="/" element={<Navigate to="/apply" replace />} />
        <Route path="/apply" element={<ApplyPage auth={auth} />} />
        <Route path="/api-keys" element={<MyApiKeysPage auth={auth} />} />
        <Route path="/usage-examples" element={<ModelsPage auth={auth} />} />
        <Route
          path="/whitelists"
          element={
            auth.role === "admin" ? (
              <WhitelistAdminPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/institute-view"
          element={
            auth.role === "admin" ? (
              <InstituteViewPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/limit-strategies"
          element={
            auth.role === "admin" ? (
              <LimitStrategiesPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/users"
          element={
            auth.role === "admin" ? (
              <AdminPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/admin-dashboard"
          element={
            auth.role === "admin" ? (
              <AdminDashboardPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/operation-audit-logs"
          element={
            auth.role === "admin" ? (
              <OperationAuditLogsPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
      </Routes>
    </AppLayout>
  );
}
