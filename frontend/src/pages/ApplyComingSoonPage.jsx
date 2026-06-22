import { useEffect, useState } from "react";
import { Alert, Box, Card, CardContent, Stack, Typography } from "@mui/material";
import { useLocation, useNavigate } from "react-router-dom";
import { useLocale } from "../i18n/locale";
import {
  formatApiKeyApplicationGoLiveAt,
  getApiKeyApplicationCountdown,
  parseApiKeyApplicationGoLiveAt,
} from "../utils/apiKeyGoLive";

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

export default function ApplyComingSoonPage() {
  const { locale, t } = useLocale();
  const navigate = useNavigate();
  const location = useLocation();
  const [now, setNow] = useState(() => new Date());
  const goLiveAt = parseApiKeyApplicationGoLiveAt(location.state?.goLiveAt);
  const countdown = getApiKeyApplicationCountdown(goLiveAt, now);

  useEffect(() => {
    if (countdown.isLive) {
      navigate("/apply", { replace: true });
      return undefined;
    }

    const timer = window.setInterval(() => {
      setNow(new Date());
    }, 1000);
    return () => window.clearInterval(timer);
  }, [countdown.isLive, navigate]);

  return (
    <Box sx={{ width: { xs: "100%", md: "920px" }, mx: "auto" }}>
      <Card
        sx={{
          overflow: "hidden",
          border: "1px solid",
          borderColor: "divider",
        }}
      >
        <CardContent sx={{ p: { xs: 3, md: 5 } }}>
          <Stack spacing={3}>
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
              <Stack spacing={1}>
                <Typography variant="h5" sx={{ fontWeight: 800, lineHeight: 1.3 }}>
                  {t("apply_coming_soon_launch_at", {
                    datetime: formatApiKeyApplicationGoLiveAt(goLiveAt, locale),
                  })}
                </Typography>
              </Stack>
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
                {t("apply_coming_soon_hint")}
              </Typography>
            </Box>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
