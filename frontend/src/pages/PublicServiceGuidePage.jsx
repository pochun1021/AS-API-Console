import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import ServiceUsageGuide from "../components/ServiceUsageGuide";
import { useLocale } from "../i18n/locale";
import { redirectToLogin } from "../utils/navigation";

function publicHeaderButtonSx(active = false) {
  if (active) {
    return {
      bgcolor: "#ffffff",
      color: "primary.main",
      borderColor: "#ffffff",
      fontWeight: 800,
      fontSize: { xs: "0.95rem", sm: "1.05rem" },
      px: { xs: 1.5, sm: 2 },
      py: 0.75,
      "&:hover": {
        bgcolor: "rgba(255, 255, 255, 0.9)",
        borderColor: "#ffffff",
      },
    };
  }

  return {
    color: "#ffffff",
    borderColor: "rgba(255, 255, 255, 0.82)",
    fontWeight: 800,
    fontSize: { xs: "0.95rem", sm: "1.05rem" },
    px: { xs: 1.5, sm: 2 },
    py: 0.75,
    "&:hover": {
      bgcolor: "rgba(255, 255, 255, 0.12)",
      borderColor: "#ffffff",
    },
  };
}

export default function PublicServiceGuidePage() {
  const { locale, setLocale, t } = useLocale();
  const logoSrc = `${import.meta.env.BASE_URL}favicon.svg`;

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box
        component="header"
        sx={{
          px: { xs: 2, md: 4 },
          py: 2,
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 1.5,
          bgcolor: "primary.main",
          color: "primary.contrastText",
        }}
      >
        <Box component="img" src={logoSrc} alt="AS API Console logo" sx={{ width: 32, height: 32 }} />
        <Typography variant="h6" sx={{ flex: "1 1 180px", minWidth: 0 }}>
          AS API Console
        </Typography>
        <Stack direction="row" sx={{ flex: "0 1 auto", flexWrap: "wrap", gap: 1 }}>
          <Button
            variant={locale === "zh-TW" ? "contained" : "outlined"}
            size="small"
            onClick={() => setLocale("zh-TW")}
            sx={publicHeaderButtonSx(locale === "zh-TW")}
          >
            {t("lang_zh", "中文")}
          </Button>
          <Button
            variant={locale === "en" ? "contained" : "outlined"}
            size="small"
            onClick={() => setLocale("en")}
            sx={publicHeaderButtonSx(locale === "en")}
          >
            {t("lang_en", "EN")}
          </Button>
          <Button variant="contained" size="small" onClick={redirectToLogin} sx={publicHeaderButtonSx(true)}>
            {t("public_guide_login")}
          </Button>
        </Stack>
      </Box>
      <Box component="main" sx={{ width: "100%", maxWidth: 1120, mx: "auto", px: 2, py: { xs: 2, md: 4 } }}>
        <Card sx={{ border: "1px solid", borderColor: "divider" }}>
          <CardContent sx={{ p: { xs: 2.5, md: 4 } }}>
            <ServiceUsageGuide />
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
