import { Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { apiClient } from "./api/client";
import AppLayout from "./components/AppLayout";
import { LoadingBlock } from "./components/StateBlocks";
import { clearOAuthAuthContext, readOAuthAuthContext } from "./authContext";
import { detectSystemLocale, useLocale } from "./i18n/locale";
import { lazyWithReload } from "./utils/lazyWithReload";
import { redirectToLogin } from "./utils/navigation";

function redirectToPublicHome() {
  if (typeof window === "undefined") return;
  window.location.assign("/main/");
}

const ApplyPage = lazyWithReload("ApplyPage", () => import("./pages/ApplyPage"));
const ApplyComingSoonPage = lazyWithReload("ApplyComingSoonPage", () => import("./pages/ApplyComingSoonPage"));
const LoginComingSoonPage = lazyWithReload("LoginComingSoonPage", () => import("./pages/LoginComingSoonPage"));
const LoginDeniedPage = lazyWithReload("LoginDeniedPage", () => import("./pages/LoginDeniedPage"));
const LoginErrorPage = lazyWithReload("LoginErrorPage", () => import("./pages/LoginErrorPage"));
const MyApiKeysPage = lazyWithReload("MyApiKeysPage", () => import("./pages/MyApiKeysPage"));
const AdminPage = lazyWithReload("AdminPage", () => import("./pages/AdminPage"));
const AdminDashboardPage = lazyWithReload("AdminDashboardPage", () => import("./pages/AdminDashboardPage"));
const LimitStrategiesPage = lazyWithReload("LimitStrategiesPage", () => import("./pages/LimitStrategiesPage"));
const InstituteViewPage = lazyWithReload("InstituteViewPage", () => import("./pages/InstituteViewPage"));
const ModelsPage = lazyWithReload("ModelsPage", () => import("./pages/ModelsPage"));
const OperationAuditLogsPage = lazyWithReload("OperationAuditLogsPage", () => import("./pages/OperationAuditLogsPage"));
const PublicServiceGuidePage = lazyWithReload("PublicServiceGuidePage", () => import("./pages/PublicServiceGuidePage"));
const SystemAnnouncementsPage = lazyWithReload("SystemAnnouncementsPage", () => import("./pages/SystemAnnouncementsPage"));
const UsagePage = lazyWithReload("UsagePage", () => import("./pages/UsagePage"));
const WhitelistAdminPage = lazyWithReload("WhitelistAdminPage", () => import("./pages/WhitelistAdminPage"));
const SERVICE_GUIDE_AUTH_HINT_KEY = "as-api-console-service-guide-auth-hint";

function hasServiceGuideAuthHint() {
  if (typeof window === "undefined") return false;
  return window.sessionStorage.getItem(SERVICE_GUIDE_AUTH_HINT_KEY) === "1";
}

function setServiceGuideAuthHint() {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SERVICE_GUIDE_AUTH_HINT_KEY, "1");
}

function clearServiceGuideAuthHint() {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SERVICE_GUIDE_AUTH_HINT_KEY);
}

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const [auth, setAuth] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [logoutInProgress, setLogoutInProgress] = useState(false);
  const [localeReady, setLocaleReady] = useState(false);
  const { setLocale, t } = useLocale();
  const isLoginDeniedRoute = location.pathname === "/login-denied";
  const isLoginErrorRoute = location.pathname === "/login-error";
  const isLoginComingSoonRoute = location.pathname === "/login-coming-soon";
  const isPublicRootRoute = location.pathname === "/" && !auth && !hasServiceGuideAuthHint();
  const isServiceGuideRoute = location.pathname === "/usage-examples";
  const isPublicServiceGuideRoute = isServiceGuideRoute && !auth && !hasServiceGuideAuthHint();

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
      clearServiceGuideAuthHint();
      setAuth(null);
      setLogoutInProgress(false);
      redirectToPublicHome();
    }
  }

  useEffect(() => {
    let canceled = false;
    async function bootstrapAuth() {
      if (isLoginDeniedRoute || isLoginErrorRoute || isLoginComingSoonRoute || isPublicRootRoute || isPublicServiceGuideRoute) {
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
          setServiceGuideAuthHint();
          setAuth(currentUser);
        }
      } catch (error) {
        if (canceled) return;
        if (isServiceGuideRoute && !(error?.status >= 500)) {
          clearServiceGuideAuthHint();
          setLocale(detectSystemLocale());
          setLocaleReady(true);
          return;
        }
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
  }, [isLoginDeniedRoute, isLoginErrorRoute, isLoginComingSoonRoute, isPublicRootRoute, isPublicServiceGuideRoute, isServiceGuideRoute, navigate, setLocale]);

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

  if (isLoginDeniedRoute || isLoginErrorRoute || isLoginComingSoonRoute) {
    return (
      <Suspense fallback={<LoadingBlock text={t("common_loading")} />}>
        <Routes>
          <Route path="/login-coming-soon" element={<LoginComingSoonPage />} />
          <Route path="/login-denied" element={<LoginDeniedPage />} />
          <Route path="/login-error" element={<LoginErrorPage />} />
          <Route path="*" element={<Navigate to="/login-denied" replace />} />
        </Routes>
      </Suspense>
    );
  }

  if (isPublicRootRoute) {
    return (
      <Suspense fallback={<LoadingBlock text={t("common_loading")} />}>
        <Routes>
          <Route path="/" element={<PublicServiceGuidePage />} />
        </Routes>
      </Suspense>
    );
  }

  if (isPublicServiceGuideRoute) {
    return (
      <Suspense fallback={<LoadingBlock text={t("common_loading")} />}>
        <Routes>
          <Route path="/usage-examples" element={<PublicServiceGuidePage />} />
        </Routes>
      </Suspense>
    );
  }

  if (!authReady || !auth || !localeReady) {
    return null;
  }

  return (
    <AppLayout
      auth={auth}
      onChangeLocale={changeLocale}
      onLogout={handleLogout}
      logoutInProgress={logoutInProgress}
    >
      <Suspense fallback={<LoadingBlock text={t("common_loading")} />}>
        <Routes>
          <Route path="/" element={<Navigate to="/announcements" replace />} />
          <Route path="/apply" element={<ApplyPage auth={auth} />} />
          <Route path="/apply/coming-soon" element={<ApplyComingSoonPage />} />
          <Route path="/api-keys" element={<MyApiKeysPage auth={auth} />} />
          <Route path="/usage" element={<UsagePage auth={auth} />} />
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
          <Route
            path="/announcements"
            element={<SystemAnnouncementsPage auth={auth} />}
          />
        </Routes>
      </Suspense>
    </AppLayout>
  );
}
