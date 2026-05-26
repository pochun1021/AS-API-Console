import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { apiClient } from "./api/client";
import AppLayout from "./components/AppLayout";
import { clearOAuthAuthContext, readOAuthAuthContext } from "./authContext";
import { detectSystemLocale, useLocale } from "./i18n/locale";
import ApplyPage from "./pages/ApplyPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import AdminPage from "./pages/AdminPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import LimitStrategiesPage from "./pages/LimitStrategiesPage";
import OperationAuditLogsPage from "./pages/OperationAuditLogsPage";
import WhitelistAdminPage from "./pages/WhitelistAdminPage";

export default function App() {
  const [auth, setAuth] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [logoutInProgress, setLogoutInProgress] = useState(false);
  const [localeReady, setLocaleReady] = useState(false);
  const { setLocale } = useLocale();

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
      if (typeof window !== "undefined") {
        window.location.assign("/main/login");
      }
    }
  }

  useEffect(() => {
    let canceled = false;
    async function bootstrapAuth() {
      try {
        const devAuth = readOAuthAuthContext();
        const currentUser = await apiClient.getCurrentUser(devAuth);
        if (!canceled) {
          setAuth(currentUser);
        }
      } catch {
        if (!canceled && typeof window !== "undefined") {
          window.location.assign("/main/login");
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
  }, []);

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

  if (!authReady || !auth || !localeReady) {
    return null;
  }

  return (
    <AppLayout auth={auth} onChangeLocale={changeLocale} onLogout={handleLogout} logoutInProgress={logoutInProgress}>
      <Routes>
        <Route path="/" element={<Navigate to="/apply" replace />} />
        <Route path="/apply" element={<ApplyPage auth={auth} />} />
        <Route path="/api-keys" element={<MyApiKeysPage auth={auth} />} />
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
