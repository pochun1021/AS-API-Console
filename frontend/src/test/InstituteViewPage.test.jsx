import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InstituteViewPage from "../pages/InstituteViewPage";
import { setApiProvider } from "../api/client";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

test("admin can load institute data", async () => {
  setApiProvider({
    listInstitutes: async () => ({
      items: [
        { inst_code: "01", inst_name: "Institute A", abb_inst_name: "Inst A", einst_name: "Institute A", division: "D1" }
      ],
      total: 1
    })
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("單位代碼資料檢視")).toBeInTheDocument();
  expect(await screen.findByText("01")).toBeInTheDocument();
  expect(screen.getByText("目前有效單位代碼筆數：1")).toBeInTheDocument();
});

test("empty state is shown when no data", async () => {
  setApiProvider({
    listInstitutes: async () => ({ items: [], total: 0 })
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("目前沒有單位代碼資料。")).toBeInTheDocument();
});

test("error state is shown when request fails", async () => {
  setApiProvider({
    listInstitutes: async () => {
      throw new Error("failed");
    }
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("載入單位代碼資料失敗")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  render(<InstituteViewPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用單位代碼資料檢視功能。")).toBeInTheDocument();
});

test("admin can trigger manual sync and reload data", async () => {
  const user = userEvent.setup();
  let listCalls = 0;
  setApiProvider({
    listInstitutes: async () => {
      listCalls += 1;
      return {
        items: [{ inst_code: "01", inst_name: "Institute A", abb_inst_name: "Inst A", einst_name: "Institute A", division: "D1" }],
        total: 1
      };
    },
    syncInstitutes: async () => ({
      fetched_count: 10,
      inserted_count: 1,
      updated_count: 2,
      unchanged_count: 7,
      deactivated_count: 0
    })
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("單位代碼資料檢視")).toBeInTheDocument();
  await screen.findByText("01");
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText("同步完成：fetched=10, inserted=1, updated=2, unchanged=7, deactivated=0")).toBeInTheDocument();
  expect(listCalls).toBe(2);
});

test("manual sync shows error message on failure", async () => {
  const user = userEvent.setup();
  setApiProvider({
    listInstitutes: async () => ({ items: [], total: 0 }),
    syncInstitutes: async () => {
      throw new Error("failed");
    }
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("目前沒有單位代碼資料。")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText("手動同步失敗")).toBeInTheDocument();
});
