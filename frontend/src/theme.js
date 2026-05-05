import { createTheme } from "@mui/material";

export const appTheme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#0b3c5d" },
    secondary: { main: "#ff6b35" },
    background: {
      default: "#f4f7fb",
      paper: "#ffffff"
    }
  },
  typography: {
    fontFamily: "'IBM Plex Sans', 'Noto Sans TC', sans-serif"
  },
  shape: { borderRadius: 10 }
});
