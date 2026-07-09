import { Suspense } from "react";
import { Stack } from "@mui/material";
import { LoadingBlock } from "./StateBlocks";
import { useLocale } from "../i18n/locale";
import { lazyWithReload } from "../utils/lazyWithReload";
import guideEn from "../../../docs/service-usage-guide.en.md?raw";
import guideZhTw from "../../../docs/service-usage-guide.zh-TW.md?raw";

const MarkdownRenderer = lazyWithReload("MarkdownRenderer", () => import("./MarkdownRenderer"));

export default function ServiceUsageGuide() {
  const { locale, t } = useLocale();
  const guideMarkdown = locale === "zh-TW" ? guideZhTw : guideEn;

  return (
    <Stack spacing={2} sx={{ minWidth: 0 }}>
      <Suspense fallback={<LoadingBlock text={t("common_loading")} />}>
        <MarkdownRenderer markdown={guideMarkdown} />
      </Suspense>
    </Stack>
  );
}
