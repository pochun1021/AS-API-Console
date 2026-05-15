import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, MenuItem, Select, Stack, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { apiClient } from "../api/client";
import { useLocale } from "../i18n/locale";

export default function PendingApplicationsPage({ auth }) {
  const { t, gridLocaleText } = useLocale();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const resp = await apiClient.listPendingApplications(auth);
      setRows(resp.items || []);
    } catch (e) {
      setError(e?.payload?.error?.message || t("pending_load_failed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function updateMode(id, mode) {
    await apiClient.updateApplicationIssuanceMode(id, mode, auth);
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, selected_issuance_mode: mode } : row)));
  }

  async function issueNow(id) {
    try {
      await apiClient.issueApplication(id, auth);
      await load();
    } catch (e) {
      setError(e?.payload?.error?.message || t("pending_issue_failed"));
      await load();
    }
  }

  const columns = [
    { field: "account", headerName: t("common_account"), flex: 1 },
    { field: "name", headerName: t("common_name"), flex: 1 },
    { field: "application_date", headerName: t("pending_col_application_date"), flex: 1 },
    { field: "purpose", headerName: t("pending_col_purpose"), flex: 1.5 },
    {
      field: "selected_issuance_mode",
      headerName: t("pending_col_mode"),
      flex: 1,
      renderCell: (params) => (
        <Select
          size="small"
          value={params.row.selected_issuance_mode || ""}
          displayEmpty
          onChange={(event) => updateMode(params.row.id, event.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="">{t("pending_select_mode")}</MenuItem>
          <MenuItem value="budget">budget</MenuItem>
          <MenuItem value="rate_limit">rate_limit</MenuItem>
        </Select>
      )
    },
    {
      field: "actions",
      headerName: t("common_actions"),
      sortable: false,
      filterable: false,
      width: 160,
      renderCell: (params) => (
        <Button
          variant="contained"
          size="small"
          disabled={!params.row.selected_issuance_mode}
          onClick={() => issueNow(params.row.id)}
        >
          {t("pending_issue_now")}
        </Button>
      )
    }
  ];

  return (
    <Stack spacing={2}>
      <Typography variant="h4">{t("pending_title")}</Typography>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <Card>
        <CardContent>
          <Box sx={{ height: 560 }}>
            <DataGrid
              loading={loading}
              rows={rows}
              columns={columns}
              getRowId={(row) => row.id}
              pageSizeOptions={[10, 20, 50]}
              initialState={{ pagination: { paginationModel: { pageSize: 10, page: 0 } } }}
              localeText={gridLocaleText}
            />
          </Box>
        </CardContent>
      </Card>
    </Stack>
  );
}
