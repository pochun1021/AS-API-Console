import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";
import { useNavigate, useParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";

function statusColor(status) {
  if (status === "active") return "success";
  if (status === "revoked") return "warning";
  return "default";
}

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

export default function ApiKeyDetailPage({ auth }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.getApiKeyById(id, auth);
      setItem(response.item);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入 API Key 詳情失敗");
    } finally {
      setLoading(false);
    }
  }

  async function revoke() {
    setBanner("");
    try {
      await apiClient.revokeApiKey(id, auth);
      setBanner("金鑰已停用。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "停用金鑰失敗");
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  return (
    <Stack spacing={3}>
      <Typography variant="h4">API Key 詳情</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}
      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入單筆 API Key 中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && item ? (
            <Stack spacing={2}>
              <Typography>ID: {item.id}</Typography>
              <Box>
                狀態: <Chip size="small" label={item.status} color={statusColor(item.status)} />
              </Box>
              <Typography>申請日期: {item.application_date}</Typography>
              <Typography>生效時長: {item.duration_months} 個月</Typography>
              <Typography>建立時間: {formatDateTime(item.created_at)}</Typography>
              <Typography>到期時間: {formatDateTime(item.expires_at)}</Typography>
              <Typography>
                遮罩金鑰 / 前綴: {item.masked_key} ({item.key_prefix})
              </Typography>
              {auth.role === "admin" ? <Typography>擁有者: {item.owner_account || "-"}</Typography> : null}
              <Stack direction="row" spacing={1}>
                <Button variant="outlined" onClick={() => navigate("/api-keys")}>
                  返回清單
                </Button>
                {item.status === "active" ? (
                  <Button variant="contained" color="warning" onClick={revoke}>
                    停用金鑰
                  </Button>
                ) : null}
              </Stack>
            </Stack>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
