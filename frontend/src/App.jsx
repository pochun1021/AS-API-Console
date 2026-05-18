import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import DevAuthSwitcher from "./components/DevAuthSwitcher";
import { devAuthProfiles, readOAuthAuthContext } from "./authContext";
import { detectSystemLocale, useLocale } from "./i18n/locale";
import ApplyPage from "./pages/ApplyPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import AdminPage from "./pages/AdminPage";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import LimitStrategiesPage from "./pages/LimitStrategiesPage";
import PendingApplicationsPage from "./pages/PendingApplicationsPage";
import WhitelistAdminPage from "./pages/WhitelistAdminPage";

const STORAGE_KEY = "as-api-console-dev-auth-profile";

function readStoredProfileKey() {
  if (typeof window === "undefined") {
    return "user";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "user") {
    return "user";
  }
  return "user";
}

export default function App() {
  const [profileKey, setProfileKey] = useState(readStoredProfileKey);
  const [oauthAuth, setOAuthAuth] = useState(readOAuthAuthContext);
  const [localeReady, setLocaleReady] = useState(false);
  const { setLocale } = useLocale();

  const auth = useMemo(() => oauthAuth || devAuthProfiles[profileKey] || devAuthProfiles.admin, [oauthAuth, profileKey]);

  function changeProfile(nextKey) {
    if (oauthAuth) return;
    setProfileKey(nextKey);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, nextKey);
    }
  }

  function changeLocale(nextLocale) {
    setLocale(nextLocale);
  }

  useEffect(() => {
    setOAuthAuth(readOAuthAuthContext());
  }, []);

  useEffect(() => {
    let canceled = false;
    async function initLocale() {
      try {
        if (!canceled) setLocale(detectSystemLocale());
      } finally {
        if (!canceled) setLocaleReady(true);
      }
    }
    setLocaleReady(false);
    initLocale();
    return () => {
      canceled = true;
    };
  }, [setLocale]);

  if (!localeReady) {
    return null;
  }

  return (
    <AppLayout auth={auth} onChangeLocale={changeLocale}>
      {!oauthAuth ? <DevAuthSwitcher profileKey={profileKey} onChange={changeProfile} auth={auth} /> : null}
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
          path="/pending-applications"
          element={
            auth.role === "admin" ? (
              <PendingApplicationsPage auth={auth} />
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
      </Routes>
    </AppLayout>
  );
}
