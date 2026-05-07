import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";
import { useLocale } from "../i18n/locale";

const navItems = [
  { labelKey: "nav_apply", path: "/apply", roles: ["user", "admin"] },
  { labelKey: "nav_api_keys", path: "/api-keys", roles: ["user", "admin"] },
  { labelKey: "nav_whitelists", path: "/whitelists", roles: ["admin"] },
  { labelKey: "nav_admins", path: "/users", roles: ["admin"] },
  { labelKey: "nav_dashboard", path: "/admin-dashboard", roles: ["admin"] }
];

export default function AppLayout({ children, auth, onChangeLocale = () => {} }) {
  const location = useLocation();
  const { locale, t } = useLocale();
  const visibleNavItems = navItems.filter((item) => item.roles.includes(auth.role));

  return (
    <Box sx={{ minHeight: "100vh", background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)" }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            AS API Console
          </Typography>
          <Button
            color="inherit"
            sx={{ mr: { xs: 0.5, sm: 1 }, minWidth: 0 }}
            onClick={() => onChangeLocale(locale === "zh-TW" ? "en" : "zh-TW")}
          >
            {locale === "zh-TW" ? t("lang_en", "EN") : t("lang_zh", "中文")}
          </Button>
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
        </Toolbar>
      </AppBar>
      <Container maxWidth={false} sx={{ py: 4, px: { xs: 2, md: 4 } }}>
        <Box sx={{ maxWidth: 1840, mx: "auto", width: "100%", display: "flex", flexDirection: "column", gap: 3 }}>
          {children}
        </Box>
      </Container>
    </Box>
  );
}
