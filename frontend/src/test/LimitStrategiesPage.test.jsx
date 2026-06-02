import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
