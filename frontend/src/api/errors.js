export function normalizeApiError(error, fallbackMessage = "請求失敗") {
  const payloadError = error?.payload?.error;
  return {
    message: payloadError?.message || error?.message || fallbackMessage,
    details: payloadError?.details || ""
  };
}
