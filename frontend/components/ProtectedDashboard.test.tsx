import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedDashboard } from "./ProtectedDashboard";

const mocks = vi.hoisted(() => ({
  pathname: "/",
  replace: vi.fn(),
  user: null as {
    id: number;
    email: string;
    role: "admin" | "teacher" | "student";
  } | null,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ replace: mocks.replace }),
}));
vi.mock("./AuthProvider", () => ({
  useAuth: () => ({
    user: mocks.user,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

describe("ProtectedDashboard public preview", () => {
  beforeEach(() => {
    mocks.pathname = "/";
    mocks.replace.mockReset();
    mocks.user = null;
  });

  it("allows unauthenticated visitors into read-only dashboard preview", () => {
    render(
      <ProtectedDashboard>
        <div>Live overview</div>
      </ProtectedDashboard>,
    );

    expect(screen.getByText("Live overview")).toBeInTheDocument();
    expect(screen.getAllByText(/read-only/i).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("link", { name: /sign in for admin actions/i }),
    ).toHaveAttribute("href", "/login");
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("continues requiring authentication for privileged admin routes", async () => {
    mocks.pathname = "/admin/users";

    render(
      <ProtectedDashboard>
        <div>Private user management</div>
      </ProtectedDashboard>,
    );

    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));
    expect(
      screen.queryByText("Private user management"),
    ).not.toBeInTheDocument();
  });
});
