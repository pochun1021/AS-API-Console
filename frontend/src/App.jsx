import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { mockAuthContext } from "./authContext";
import ApplyPage from "./pages/ApplyPage";
import MyApiKeysPage from "./pages/MyApiKeysPage";
import { DetailPlaceholder, WhitelistAdminPlaceholder } from "./pages/Placeholders";

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/apply" replace />} />
        <Route path="/apply" element={<ApplyPage auth={mockAuthContext} />} />
        <Route path="/api-keys" element={<MyApiKeysPage auth={mockAuthContext} />} />
        <Route path="/api-keys/:id" element={<DetailPlaceholder />} />
        <Route path="/whitelists" element={<WhitelistAdminPlaceholder />} />
      </Routes>
    </AppLayout>
  );
}
