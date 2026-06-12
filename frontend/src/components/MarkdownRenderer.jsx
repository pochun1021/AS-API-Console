import { useEffect, useRef, useState, Fragment } from "react";
import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { Alert, Box, IconButton, Stack, Tooltip, Typography } from "@mui/material";
import { useLocale } from "../i18n/locale";

async function copyText(text) {
  if (!window.isSecureContext) {
    return { ok: false, reason: "insecure_context" };
  }

  if (!navigator?.clipboard?.writeText) {
    return { ok: false, reason: "clipboard_unavailable" };
  }

  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch (error) {
    if (error?.name === "NotAllowedError") {
      return { ok: false, reason: "permission_denied" };
    }

    return { ok: false, reason: "unknown" };
  }
}

function CodeBlock({ content }) {
  const { locale } = useLocale();
  const [copySucceeded, setCopySucceeded] = useState(false);
  const [copyError, setCopyError] = useState("");
  const resetTimerRef = useRef(null);
  const isZh = locale === "zh-TW";

  useEffect(() => () => {
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
    }
  }, []);

  async function onCopy() {
    setCopyError("");
    const result = await copyText(content);
    if (!result.ok) {
      if (result.reason === "insecure_context") {
        setCopyError(isZh ? "目前環境不支援自動複製，請手動複製。" : "Auto copy is unavailable in this environment. Please copy manually.");
      } else if (result.reason === "clipboard_unavailable") {
        setCopyError(isZh ? "目前瀏覽器不支援自動複製，請手動複製。" : "Clipboard API is unavailable. Please copy manually.");
      } else if (result.reason === "permission_denied") {
        setCopyError(isZh ? "剪貼簿權限被拒絕，請允許後再試。" : "Clipboard permission denied. Please allow and retry.");
      } else {
        setCopyError(isZh ? "目前無法複製程式碼，請手動複製。" : "Unable to copy code now. Please copy manually.");
      }
      return;
    }

    setCopySucceeded(true);
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
    }
    resetTimerRef.current = window.setTimeout(() => {
      setCopySucceeded(false);
    }, 1500);
  }

  return (
    <Stack spacing={1}>
      <Box
        component="div"
        sx={{
          position: "relative",
          borderRadius: 2,
          bgcolor: "#0f172a",
          color: "#e2e8f0",
          boxShadow: "inset 0 0 0 1px rgba(148, 163, 184, 0.18)"
        }}
      >
        <Box sx={{ display: "flex", justifyContent: "flex-end", px: 1, pt: 1 }}>
          <Tooltip title={copySucceeded ? (isZh ? "已複製" : "Copied") : (isZh ? "複製程式碼" : "Copy Code")}>
            <IconButton
              aria-label={copySucceeded ? (isZh ? "已複製程式碼" : "Copied Code") : (isZh ? "複製程式碼" : "Copy Code")}
              onClick={onCopy}
              size="small"
              sx={{ color: "#e2e8f0" }}
            >
              {copySucceeded ? <CheckIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
        </Box>
        <Box
          component="pre"
          sx={{
            m: 0,
            px: 2,
            pb: 1.5,
            overflowX: "auto",
            fontSize: 14,
            lineHeight: 1.6,
            fontFamily: "monospace"
          }}
        >
          <Box component="code">{content}</Box>
        </Box>
      </Box>
      {copyError ? <Alert severity="warning">{copyError}</Alert> : null}
    </Stack>
  );
}

function renderInline(text) {
  const parts = String(text || "").split(/(`[^`]+`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <Box
          key={`inline-code-${index}`}
          component="code"
          sx={{
            px: 0.75,
            py: 0.2,
            borderRadius: 1,
            bgcolor: "rgba(15, 23, 42, 0.08)",
            fontFamily: "monospace",
            fontSize: "0.92em"
          }}
        >
          {part.slice(1, -1)}
        </Box>
      );
    }
    return <Fragment key={`inline-text-${index}`}>{part}</Fragment>;
  });
}

function parseMarkdown(markdown) {
  const lines = String(markdown || "").replaceAll("\r\n", "\n").split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) {
        index += 1;
      }
      blocks.push({ type: "code", language, content: codeLines.join("\n") });
      continue;
    }

    if (trimmed.startsWith("## ")) {
      blocks.push({ type: "h2", content: trimmed.slice(3).trim() });
      index += 1;
      continue;
    }

    if (trimmed.startsWith("# ")) {
      blocks.push({ type: "h1", content: trimmed.slice(2).trim() });
      index += 1;
      continue;
    }

    if (trimmed.startsWith("- ")) {
      const items = [];
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        items.push(lines[index].trim().slice(2).trim());
        index += 1;
      }
      blocks.push({ type: "list", ordered: false, items });
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "list", ordered: true, items });
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;
    while (index < lines.length) {
      const nextTrimmed = lines[index].trim();
      if (
        !nextTrimmed ||
        nextTrimmed.startsWith("# ") ||
        nextTrimmed.startsWith("## ") ||
        nextTrimmed.startsWith("- ") ||
        nextTrimmed.startsWith("```")
      ) {
        break;
      }
      paragraphLines.push(nextTrimmed);
      index += 1;
    }
    blocks.push({ type: "paragraph", content: paragraphLines.join(" ") });
  }

  return blocks;
}

export default function MarkdownRenderer({ markdown }) {
  const blocks = parseMarkdown(markdown);

  return (
    <Stack spacing={2.25}>
      {blocks.map((block, index) => {
        if (block.type === "h1") {
          return (
            <Typography key={`block-${index}`} variant="h4">
              {renderInline(block.content)}
            </Typography>
          );
        }

        if (block.type === "h2") {
          return (
            <Typography key={`block-${index}`} variant="h5">
              {renderInline(block.content)}
            </Typography>
          );
        }

        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          return (
            <Box key={`block-${index}`} component={ListTag} sx={{ m: 0, pl: 3 }}>
              {block.items.map((item, itemIndex) => (
                <Box component="li" key={`list-item-${index}-${itemIndex}`} sx={{ mb: 0.75 }}>
                  <Typography variant="body1" sx={{ display: "inline-flex", gap: 0.5, flexWrap: "wrap" }}>
                    {renderInline(item)}
                  </Typography>
                </Box>
              ))}
            </Box>
          );
        }

        if (block.type === "code") {
          return <CodeBlock key={`block-${index}`} content={block.content} />;
        }

        return (
          <Typography key={`block-${index}`} variant="body1" sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {renderInline(block.content)}
          </Typography>
        );
      })}
    </Stack>
  );
}
