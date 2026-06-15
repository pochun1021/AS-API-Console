import { useState } from "react";
import CheckIcon from "@mui/icons-material/Check";
import LanguageOutlinedIcon from "@mui/icons-material/LanguageOutlined";
import LogoutOutlinedIcon from "@mui/icons-material/LogoutOutlined";
import { Alert, AppBar, Box, Button, Card, CardContent, Container, IconButton, Menu, MenuItem, Stack, Toolbar, Tooltip, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { useLocale } from "../i18n/locale";

const navItems = [
  { labelKey: "nav_announcements", path: "/announcements", roles: ["user", "admin"] },
  { labelKey: "nav_apply", path: "/apply", roles: ["user", "admin"] },
  { labelKey: "nav_api_keys", path: "/api-keys", roles: ["user", "admin"] },
  { labelKey: "nav_models", path: "/usage-examples", roles: ["user", "admin"] },
  { labelKey: "nav_whitelists", path: "/whitelists", roles: ["admin"] },
  { labelKey: "nav_limit_strategies", path: "/limit-strategies", roles: ["admin"] },
  { labelKey: "nav_admins", path: "/users", roles: ["admin"] },
  { labelKey: "nav_dashboard", path: "/admin-dashboard", roles: ["admin"] },
  { labelKey: "nav_operation_logs", path: "/operation-audit-logs", roles: ["admin"] },
  { labelKey: "nav_institute_view", path: "/institute-view", roles: ["admin"] }
];

function SystemInfoSurface({ announcementState, t }) {
  const state = announcementState || {};
  const items = Array.isArray(state.items) ? state.items : [];
  const hasVisibleSurface = items.length > 0 || state.loading || state.error;

  if (!hasVisibleSurface) {
    return null;
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack spacing={1.25}>
          <Typography variant="h6">{t("announcement_surface_title")}</Typography>
          {state.loading ? <Typography color="text.secondary">{t("announcement_surface_loading")}</Typography> : null}
          {!state.loading && state.error ? (
            <Alert
              severity="error"
              action={
                state.onRetry ? (
                  <Button color="inherit" size="small" onClick={state.onRetry}>{t("common_retry")}</Button>
                ) : null
              }
            >
              {state.error?.message || t("announcement_surface_error")}
            </Alert>
          ) : null}
          {!state.loading && !state.error && items.map((item) => (
            <Box key={item.id} sx={{ borderLeft: "4px solid", borderColor: "primary.main", pl: 1.5 }}>
              <Typography variant="subtitle1">{item.title}</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: "pre-wrap" }}>
                {item.body}
              </Typography>
            </Box>
          ))}
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function AppLayout({
  children,
  auth,
  onChangeLocale = () => {},
  onLogout = () => {},
  logoutInProgress = false,
  announcementState = { items: [], loading: false, error: "" }
}) {
  const location = useLocation();
  const { locale, t } = useLocale();
  const [localeMenuAnchor, setLocaleMenuAnchor] = useState(null);
  const visibleNavItems = navItems.filter((item) => item.roles.includes(auth.role));
  const localeMenuOpen = Boolean(localeMenuAnchor);
  const logoSrc = `${import.meta.env.BASE_URL}favicon.svg`;

  function openLocaleMenu(event) {
    setLocaleMenuAnchor(event.currentTarget);
  }

  function closeLocaleMenu() {
    setLocaleMenuAnchor(null);
  }

  function selectLocale(nextLocale) {
    onChangeLocale(nextLocale);
    closeLocaleMenu();
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)",
        display: "flex",
        flexDirection: "column"
      }}
    >
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Box sx={{ flexGrow: 1, display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
            <Box
              component="img"
              src={logoSrc}
              alt="AS API Console logo"
              sx={{ width: 32, height: 32, flexShrink: 0 }}
            />
            <Typography variant="h6" sx={{ minWidth: 0 }}>
              AS API Console
            </Typography>
          </Box>
          {visibleNavItems.map((item) => (
            <Button
              key={item.labelKey}
              component={RouterLink}
              to={item.path}
              color={location.pathname.startsWith(item.path.replace(":id", "")) ? "secondary" : "inherit"}
              sx={{
                ml: { xs: 0.5, sm: 1 },
                px: { xs: 1, sm: 1.5 },
                fontSize: { xs: "16px", sm: "18px" },
                whiteSpace: "nowrap"
              }}
            >
              {t(item.labelKey)}
            </Button>
          ))}
          <Box sx={{ display: "flex", alignItems: "center", ml: { xs: 0.5, sm: 1 } }}>
            <Tooltip title={locale === "zh-TW" ? "語言" : "Language"}>
              <IconButton
                aria-label={locale === "zh-TW" ? "語言" : "Language"}
                color="inherit"
                onClick={openLocaleMenu}
                sx={{ mr: 0.5 }}
              >
                <LanguageOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={localeMenuAnchor}
              open={localeMenuOpen}
              onClose={closeLocaleMenu}
              anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
              transformOrigin={{ vertical: "top", horizontal: "right" }}
            >
              <MenuItem selected={locale === "zh-TW"} onClick={() => selectLocale("zh-TW")}>
                <Box sx={{ minWidth: 44 }}>{t("lang_zh", "中文")}</Box>
                <Box
                  sx={{ width: 20, display: "inline-flex", justifyContent: "center", ml: 1 }}
                  data-testid="locale-check-zh-TW"
                >
                  {locale === "zh-TW" ? <CheckIcon fontSize="small" /> : null}
                </Box>
              </MenuItem>
              <MenuItem selected={locale === "en"} onClick={() => selectLocale("en")}>
                <Box sx={{ minWidth: 44 }}>{t("lang_en", "EN")}</Box>
                <Box
                  sx={{ width: 20, display: "inline-flex", justifyContent: "center", ml: 1 }}
                  data-testid="locale-check-en"
                >
                  {locale === "en" ? <CheckIcon fontSize="small" /> : null}
                </Box>
              </MenuItem>
            </Menu>
            <Tooltip title={locale === "zh-TW" ? "登出" : "Logout"}>
              <IconButton
                aria-label={locale === "zh-TW" ? "登出" : "Logout"}
                color="inherit"
                onClick={onLogout}
                disabled={logoutInProgress}
              >
                <LogoutOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Toolbar>
      </AppBar>
      <Container maxWidth={false} sx={{ py: { xs: 2, md: 2.5 }, px: { xs: 2, md: 3 }, display: "flex", flex: 1, minHeight: 0, overflow: "hidden" }}>
        <Box sx={{ maxWidth: 1840, mx: "auto", width: "100%", display: "flex", flexDirection: "column", gap: 2, flex: 1, minHeight: 0, overflow: "hidden" }}>
          <SystemInfoSurface announcementState={announcementState} t={t} />
          {children}
        </Box>
      </Container>
    </Box>
  );
}
