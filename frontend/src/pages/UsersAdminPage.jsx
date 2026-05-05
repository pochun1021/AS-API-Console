import { useEffect, useMemo, useState } from "react";
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

function roleColor(role) {
  return role === "admin" ? "warning" : "default";
}

export default function UsersAdminPage({ auth }) {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listUsers(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入使用者失敗");
    } finally {
      setLoading(false);
    }
  }

  async function search() {
    setBanner("");
    setSearching(true);
    try {
      if (!keyword.trim()) {
        await load();
        return;
      }
      const response = await apiClient.searchUsers(keyword, auth);
      setItems(response.items);
      if (response.items.length === 0) {
        setBanner("查無符合人員。");
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || "查詢使用者失敗");
    } finally {
      setSearching(false);
    }
  }

  async function grant(userId) {
    setBanner("");
    try {
      await apiClient.grantAdmin(userId, auth);
      setBanner("已授權為管理者。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "授權失敗");
    }
  }

  async function revoke(userId) {
    setBanner("");
    try {
      await apiClient.revokeAdmin(userId, auth);
      setBanner("已取消管理者權限。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "取消授權失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const currentUserBySysid = useMemo(
    () => items.find((item) => item.sysid === auth.sysid),
    [items, auth.sysid]
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">使用者管理</Typography>
        <ErrorBlock message="僅管理者可使用使用者管理功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">使用者管理</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="查詢關鍵字（sysid / 帳號 / 姓名 / email）"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              fullWidth
            />
            <Button variant="contained" onClick={search} disabled={searching} sx={{ whiteSpace: "nowrap" }}>
              {searching ? "查詢中..." : "查詢使用者"}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入使用者中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前沒有使用者資料。" /> : null}
          {!loading && !error && items.length > 0 ? (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>SysID</TableCell>
                  <TableCell>帳號</TableCell>
                  <TableCell>姓名</TableCell>
                  <TableCell>Email</TableCell>
                  <TableCell>角色</TableCell>
                  <TableCell align="right">操作</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => {
                  const isSelf = item.sysid === auth.sysid || currentUserBySysid?.id === item.id;
                  return (
                    <TableRow key={item.id}>
                      <TableCell>{item.sysid}</TableCell>
                      <TableCell>{item.account || "-"}</TableCell>
                      <TableCell>{item.name}</TableCell>
                      <TableCell>{item.email}</TableCell>
                      <TableCell>
                        <Chip size="small" label={item.role} color={roleColor(item.role)} />
                      </TableCell>
                      <TableCell align="right">
                        {item.role === "user" ? (
                          <Button variant="outlined" onClick={() => grant(item.id)}>
                            授權管理者
                          </Button>
                        ) : (
                          <Button
                            variant="outlined"
                            color="warning"
                            onClick={() => revoke(item.id)}
                            disabled={isSelf}
                          >
                            取消管理者
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
