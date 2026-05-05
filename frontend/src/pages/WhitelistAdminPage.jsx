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
  TextField,
  Typography
} from "@mui/material";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

function statusColor(status) {
  return status === "active" ? "success" : "default";
}

export default function WhitelistAdminPage({ auth }) {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [searching, setSearching] = useState(false);
  const [editingRemark, setEditingRemark] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listWhitelists(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入白名單失敗");
    } finally {
      setLoading(false);
    }
  }

  async function searchCandidates() {
    setBanner("");
    setSearching(true);
    try {
      const response = await apiClient.searchUsers(keyword, auth);
      setCandidates(response.items);
      if (response.items.length === 0) {
        setBanner("查無符合人員。");
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || "查詢人員失敗");
      setCandidates([]);
    } finally {
      setSearching(false);
    }
  }

  async function createItem(candidate) {
    setBanner("");
    try {
      await apiClient.createWhitelist({ email: candidate.email, sysid: candidate.sysid, name: candidate.name }, auth);
      setBanner("白名單已新增。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "新增白名單失敗");
    }
  }

  async function updateItem(id, payload) {
    setBanner("");
    try {
      await apiClient.updateWhitelist(id, payload, auth);
      setBanner("白名單已更新。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "更新白名單失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">白名單管理</Typography>
        <ErrorBlock message="僅管理者可使用白名單管理功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">白名單管理</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Card>
        <CardContent>
          <Stack spacing={2}>
            <Typography variant="h6">新增白名單人員</Typography>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label="查詢關鍵字（sysid / 姓名 / email）"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                fullWidth
              />
              <Button variant="contained" onClick={searchCandidates} disabled={searching} sx={{ whiteSpace: "nowrap" }}>
                {searching ? "查詢中..." : "查詢人員"}
              </Button>
            </Stack>
            {candidates.length > 0 ? (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>SysID</TableCell>
                    <TableCell>姓名</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell align="right">操作</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {candidates.map((candidate) => (
                    <TableRow key={candidate.id}>
                      <TableCell>{candidate.sysid}</TableCell>
                      <TableCell>{candidate.name}</TableCell>
                      <TableCell>{candidate.email}</TableCell>
                      <TableCell align="right">
                        <Button variant="outlined" onClick={() => createItem(candidate)}>
                          加入白名單
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : null}
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入白名單中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前沒有白名單資料。" /> : null}
          {!loading && !error && items.length > 0 ? (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>SysID</TableCell>
                  <TableCell>姓名</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>狀態</TableCell>
                  <TableCell>備註</TableCell>
                  <TableCell>建立時間</TableCell>
                  <TableCell>更新時間</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.sysid || "-"}</TableCell>
                    <TableCell>{item.name || "-"}</TableCell>
                    <TableCell>{item.email}</TableCell>
                    <TableCell>
                      <Chip size="small" label={item.status} color={statusColor(item.status)} />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        value={editingRemark[item.id] ?? item.remark}
                        onChange={(e) => setEditingRemark((prev) => ({ ...prev, [item.id]: e.target.value }))}
                      />
                    </TableCell>
                    <TableCell>{formatDateTime(item.created_at)}</TableCell>
                    <TableCell>{formatDateTime(item.updated_at)}</TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Button
                          variant="outlined"
                          onClick={() =>
                            updateItem(item.id, { status: item.status === "active" ? "inactive" : "active" })
                          }
                        >
                          {item.status === "active" ? "停用" : "啟用"}
                        </Button>
                        <Button
                          variant="contained"
                          onClick={() => updateItem(item.id, { remark: editingRemark[item.id] ?? item.remark })}
                        >
                          儲存備註
                        </Button>
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
