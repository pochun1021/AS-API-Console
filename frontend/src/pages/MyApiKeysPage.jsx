import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { Link as RouterLink } from "react-router-dom";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";

function statusColor(status) {
  if (status === "active") return "success";
  if (status === "revoked") return "warning";
  return "default";
}

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

export default function MyApiKeysPage({ auth }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listApiKeys(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入 API Key 清單失敗");
    } finally {
      setLoading(false);
    }
  }

  async function revoke(id) {
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
  }, []);

  return (
    <Stack spacing={3}>
      <Typography variant="h4">API Keys</Typography>
      {banner && <Alert severity="info">{banner}</Alert>}
      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入你的金鑰歷史紀錄中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前尚無 API Key 紀錄。" /> : null}
          {!loading && !error && items.length > 0 ? (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>申請日期</TableCell>
                  <TableCell>生效時長</TableCell>
                  <TableCell>狀態</TableCell>
                  <TableCell>建立時間</TableCell>
                  <TableCell>到期時間</TableCell>
                  <TableCell>遮罩金鑰 / 前綴</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.application_date}</TableCell>
                    <TableCell>{item.duration_months} 個月</TableCell>
                    <TableCell><Chip size="small" label={item.status} color={statusColor(item.status)} /></TableCell>
                    <TableCell>{formatDateTime(item.created_at)}</TableCell>
                    <TableCell>{formatDateTime(item.expires_at)}</TableCell>
                    <TableCell>{item.masked_key} ({item.key_prefix})</TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button component={RouterLink} to={`/api-keys/${item.id}`} variant="text">
                          詳情
                        </Button>
                        {item.status === "active" ? (
                          <Button variant="outlined" color="warning" onClick={() => revoke(item.id)}>
                            停用
                          </Button>
                        ) : null}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
