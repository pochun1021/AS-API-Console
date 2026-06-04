import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import LimitStrategiesPage from "../pages/LimitStrategiesPage";
import { setApiProvider } from "../api/client";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

test("admin can save zero rate limits", async () => {
  const user = userEvent.setup();
  const updateLimitStrategyConfig = vi.fn(async () => ({
    budget_max_budget: "1000",
    budget_duration: "monthly",
    rate_limit_tpm: 0,
    rate_limit_rpm: 0
  }));

  setApiProvider({
    getLimitStrategyConfig: async () => ({
      budget_max_budget: "1000",
      budget_duration: "monthly",
      rate_limit_tpm: 10000,
      rate_limit_rpm: 500
    }),
    updateLimitStrategyConfig
  });

  render(<LimitStrategiesPage auth={adminAuth} />);

  const tpmInput = await screen.findByLabelText("tpm_limit");
  const rpmInput = screen.getByLabelText("rpm_limit");

  await user.clear(tpmInput);
  await user.type(tpmInput, "0");
  await user.clear(rpmInput);
  await user.type(rpmInput, "0");
  await user.click(screen.getByRole("button", { name: "儲存" }));

  expect(updateLimitStrategyConfig).toHaveBeenCalledWith(
    {
      budget_max_budget: "1000",
      budget_duration: "monthly",
      rate_limit_tpm: 0,
      rate_limit_rpm: 0
    },
    adminAuth
  );
});

test("digits-only fields reject non-ascii numeric input", async () => {
  const user = userEvent.setup();
  const updateLimitStrategyConfig = vi.fn();

  setApiProvider({
    getLimitStrategyConfig: async () => ({
      budget_max_budget: "1000",
      budget_duration: "monthly",
      rate_limit_tpm: 10000,
      rate_limit_rpm: 500
    }),
    updateLimitStrategyConfig
  });

  render(<LimitStrategiesPage auth={adminAuth} />);

  const tpmInput = await screen.findByLabelText("tpm_limit");
  await user.clear(tpmInput);
  await user.type(tpmInput, "12e3");
  expect(tpmInput).toHaveValue("123");

  const budgetInput = screen.getByLabelText("max_budget");
  await user.clear(budgetInput);
  await user.paste("１２３");
  expect(await screen.findByText("此欄位僅接受 0-9 數字。")).toBeInTheDocument();
  expect(budgetInput).toHaveValue("");
  expect(updateLimitStrategyConfig).not.toHaveBeenCalled();
});
