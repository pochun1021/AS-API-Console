import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";

const navItems = [
  { label: "申請", path: "/apply", roles: ["user", "admin"] },
  { label: "API Keys", path: "/api-keys", roles: ["user", "admin"] },
  { label: "白名單管理", path: "/whitelists", roles: ["admin"] },
  { label: "使用者管理", path: "/users", roles: ["admin"] }
];

export default function AppLayout({ children, auth }) {
  const location = useLocation();
  const visibleNavItems = navItems.filter((item) => item.roles.includes(auth.role));

  return (
    <Box sx={{ minHeight: "100vh", background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)" }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            AS API Console
          </Typography>
          {visibleNavItems.map((item) => (
            <Button
              key={item.label}
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
              {item.label}
            </Button>
          ))}
        </Toolbar>
      </AppBar>
      <Container maxWidth={false} sx={{ py: 4, px: { xs: 2, md: 4 } }}>
        <Box sx={{ maxWidth: 1840, mx: "auto", width: "100%" }}>
          {children}
        </Box>
      </Container>
    </Box>
  );
}
