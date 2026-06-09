export function normalizeApiError(error, fallbackMessage = "請求失敗") {
  const payloadError = error?.payload?.error;
  return {
    message: payloadError?.message || fallbackMessage || error?.message || "請求失敗",
    details: payloadError?.details || "",
    code: payloadError?.code || "",
    retry_after_seconds:
      typeof error?.payload?.retry_after_seconds === "number" ? error.payload.retry_after_seconds : 0,
    next_allowed_at:
      typeof error?.payload?.next_allowed_at === "string" ? error.payload.next_allowed_at : null
  };
}
