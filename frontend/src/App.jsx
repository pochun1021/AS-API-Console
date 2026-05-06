import { useMemo, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import DevAuthSwitcher from "./components/DevAuthSwitcher";
import { devAuthProfiles } from "./authContext";
import ApplyPage from "./pages/ApplyPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import UsersAdminPage from "./pages/UsersAdminPage";
import WhitelistAdminPage from "./pages/WhitelistAdminPage";

const STORAGE_KEY = "as-api-console-dev-auth-profile";

function readStoredProfileKey() {
  if (typeof window === "undefined") {
    return "admin";
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "admin" || stored === "user") {
    return stored;
  }
  return "admin";
}

export default function App() {
  const [profileKey, setProfileKey] = useState(readStoredProfileKey);

  const auth = useMemo(() => devAuthProfiles[profileKey] || devAuthProfiles.admin, [profileKey]);

  function changeProfile(nextKey) {
    setProfileKey(nextKey);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, nextKey);
    }
  }

  return (
    <AppLayout auth={auth}>
      <DevAuthSwitcher profileKey={profileKey} onChange={changeProfile} auth={auth} />
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
          path="/users"
          element={
            auth.role === "admin" ? (
              <UsersAdminPage auth={auth} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
      </Routes>
    </AppLayout>
  );
}
