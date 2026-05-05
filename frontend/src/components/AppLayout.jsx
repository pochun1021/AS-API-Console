import { AppBar, Box, Button, Container, Toolbar, Typography } from "@mui/material";
import { Link as RouterLink, useLocation } from "react-router-dom";

const navItems = [
  { label: "申請", path: "/apply" },
  { label: "API Keys", path: "/api-keys" },
  { label: "詳情", path: "/api-keys/:id", disabled: true },
  { label: "白名單管理", path: "/whitelists", disabled: true }
];

export default function AppLayout({ children }) {
  const location = useLocation();

  return (
    <Box sx={{ minHeight: "100vh", background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)" }}>
      <AppBar position="static" elevation={0}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            AS API Console
          </Typography>
          {navItems.map((item) => (
            <Button
              key={item.label}
              component={item.disabled ? "button" : RouterLink}
              to={item.disabled ? undefined : item.path}
              disabled={item.disabled}
              color={location.pathname.startsWith(item.path.replace(":id", "")) ? "secondary" : "inherit"}
              sx={{ ml: 1 }}
            >
              {item.label}
            </Button>
          ))}
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4 }}>
        {children}
      </Container>
    </Box>
  );
}
