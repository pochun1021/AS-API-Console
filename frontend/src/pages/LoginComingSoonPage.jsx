import { useEffect, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import {
  formatApiKeyApplicationGoLiveAt,
  getApiKeyApplicationCountdown,
  isApiKeyApplicationLive,
  parseApiKeyApplicationGoLiveAt,
} from "../utils/apiKeyGoLive";
import { useLocale } from "../i18n/locale";
import { proceedToLogin } from "../utils/navigation";

function CountdownUnit({ label, value }) {
  const displayValue = String(value).padStart(2, "0");

  return (
    <Box
      sx={{
        minWidth: { xs: "calc(50% - 8px)", sm: 140 },
        flex: "1 1 140px",
        px: 2,
        py: 2.5,
        borderRadius: 3,
        border: "1px solid",
        borderColor: "divider",
        textAlign: "center",
      }}
    >
      <Typography
        key={`${label}-${displayValue}`}
        variant="h3"
        sx={{
          fontWeight: 900,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          animation: "countdownPop 320ms ease-out",
          "@keyframes countdownPop": {
            "0%": { opacity: 0, transform: "translateY(8px) scale(0.94)" },
            "100%": { opacity: 1, transform: "translateY(0) scale(1)" },
          },
        }}
      >
        {displayValue}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1, fontWeight: 700 }}>
        {label}
      </Typography>
    </Box>
  );
}

export default function LoginComingSoonPage() {
  const { locale, setLocale, t } = useLocale();
  const [now, setNow] = useState(() => new Date());
  const goLiveAt = parseApiKeyApplicationGoLiveAt();
  const countdown = getApiKeyApplicationCountdown(goLiveAt, now);

  useEffect(() => {
    if (isApiKeyApplicationLive(goLiveAt, now)) {
      proceedToLogin();
      return undefined;
    }

    const timer = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => window.clearInterval(timer);
  }, [goLiveAt, now]);

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: 2,
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 920 }}>
        <Card sx={{ border: "1px solid", borderColor: "divider" }}>
          <CardContent sx={{ p: { xs: 3, md: 5 } }}>
            <Stack spacing={3}>
              <Stack direction="row" justifyContent="flex-end" spacing={1}>
                <Button
                  variant={locale === "zh-TW" ? "contained" : "outlined"}
                  size="small"
                  onClick={() => setLocale("zh-TW")}
                >
                  {t("lang_zh", "中文")}
                </Button>
                <Button
                  variant={locale === "en" ? "contained" : "outlined"}
                  size="small"
                  onClick={() => setLocale("en")}
                >
                  {t("lang_en", "EN")}
                </Button>
              </Stack>
              <Stack spacing={1}>
                <Typography
                  variant="h4"
                  sx={{ letterSpacing: "0.12em", fontWeight: 900, color: "text.primary" }}
                >
                  {t("apply_coming_soon_teaser")}
                </Typography>
                <Typography variant="h4">{t("apply_coming_soon_title")}</Typography>
                <Typography variant="body1">{t("apply_coming_soon_message")}</Typography>
              </Stack>

              <Alert severity="info" sx={{ alignItems: "flex-start" }}>
                <Typography variant="h5" sx={{ fontWeight: 800, lineHeight: 1.3 }}>
                  {t("apply_coming_soon_launch_at", {
                    datetime: formatApiKeyApplicationGoLiveAt(goLiveAt, locale),
                  })}
                </Typography>
              </Alert>

              <Box
                sx={{
                  p: 3,
                  borderRadius: 3,
                  border: "1px solid",
                  borderColor: "divider",
                }}
                aria-label={t("apply_coming_soon_countdown", countdown)}
              >
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 800 }}>
                  {t("apply_coming_soon_countdown_label")}
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
                  <CountdownUnit label={t("apply_coming_soon_days")} value={countdown.days} />
                  <CountdownUnit label={t("apply_coming_soon_hours")} value={countdown.hours} />
                  <CountdownUnit label={t("apply_coming_soon_minutes")} value={countdown.minutes} />
                  <CountdownUnit label={t("apply_coming_soon_seconds")} value={countdown.seconds} />
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                  {t("login_coming_soon_hint")}
                </Typography>
              </Box>

              <Box>
                <Button variant="contained" onClick={proceedToLogin}>
                  {t("login_coming_soon_action")}
                </Button>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
