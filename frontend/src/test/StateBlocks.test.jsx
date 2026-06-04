import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocaleProvider } from "../i18n/locale";
import { ErrorBlock } from "../components/StateBlocks";

test("error block can expand and collapse error details", async () => {
  const user = userEvent.setup();

  render(
    <LocaleProvider>
      <ErrorBlock message={{ message: "載入失敗", details: "app.api.v1.api_keys:list_api_keys" }} />
    </LocaleProvider>
  );

  expect(screen.getByText("載入失敗")).toBeInTheDocument();
  expect(screen.getByText("app.api.v1.api_keys:list_api_keys")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Show details" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Show details" }));
  expect(screen.getByRole("button", { name: "Hide details" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Hide details" }));
  expect(screen.getByRole("button", { name: "Show details" })).toBeInTheDocument();
});
