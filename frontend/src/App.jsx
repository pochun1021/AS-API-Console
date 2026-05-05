import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { mockAuthContext } from "./authContext";
import ApiKeyDetailPage from "./pages/ApiKeyDetailPage";
import ApplyPage from "./pages/ApplyPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import UsersAdminPage from "./pages/UsersAdminPage";
import WhitelistAdminPage from "./pages/WhitelistAdminPage";

export default function App() {
  return (
    <AppLayout auth={mockAuthContext}>
      <Routes>
        <Route path="/" element={<Navigate to="/apply" replace />} />
        <Route path="/apply" element={<ApplyPage auth={mockAuthContext} />} />
        <Route path="/api-keys" element={<MyApiKeysPage auth={mockAuthContext} />} />
        <Route path="/api-keys/:id" element={<ApiKeyDetailPage auth={mockAuthContext} />} />
        <Route
          path="/whitelists"
          element={
            mockAuthContext.role === "admin" ? (
              <WhitelistAdminPage auth={mockAuthContext} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
        <Route
          path="/users"
          element={
            mockAuthContext.role === "admin" ? (
              <UsersAdminPage auth={mockAuthContext} />
            ) : (
              <Navigate to="/apply" replace />
            )
          }
        />
      </Routes>
    </AppLayout>
  );
}
