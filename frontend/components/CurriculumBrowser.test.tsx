import "@testing-library/jest-dom/vitest";
import { QueryProvider } from "./QueryProvider";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../lib/api";
import { CurriculumBrowser } from "./CurriculumBrowser";

vi.mock("../lib/api", () => ({
  getBooks: vi.fn(),
  getChapters: vi.fn(),
  getCurricula: vi.fn(),
  getGrades: vi.fn(),
  getSubjects: vi.fn(),
  getTopics: vi.fn(),
}));

describe("CurriculumBrowser", () => {
  beforeEach(() => {
    vi.mocked(api.getCurricula).mockResolvedValue({
      curricula: [
        {
          id: "punjab-board",
          name: "Punjab Board",
          description: "Test data",
          is_sample: false,
        },
        {
          id: "sample-placeholder",
          name: "Sample Curriculum (Placeholder)",
          description: "Sample only, not official curriculum.",
          is_sample: true,
        },
      ],
    });
    vi.mocked(api.getGrades).mockResolvedValue({
      items: [{ id: 9, name: "Grade 9" }],
    });
    vi.mocked(api.getSubjects).mockResolvedValue({
      items: [{ id: 12, name: "Mathematics" }],
    });
    vi.mocked(api.getBooks).mockResolvedValue({
      items: [{ id: 4, name: "Mathematics 9" }],
    });
    vi.mocked(api.getChapters).mockResolvedValue({
      items: [{ id: 5, name: "Number Systems" }],
    });
    vi.mocked(api.getTopics).mockResolvedValue({
      items: [{ id: 6, name: "Integers" }],
    });
  });

  it("loads real catalog levels and hides sample placeholder curricula", async () => {
    render(
      <QueryProvider>
        <CurriculumBrowser />
      </QueryProvider>,
    );

    await screen.findByRole("option", { name: "Punjab Board" });
    expect(
      screen.queryByRole("option", { name: "Sample Curriculum (Placeholder)" }),
    ).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Curriculum" }), {
      target: { value: "punjab-board" },
    });
    await screen.findByRole("option", { name: "Grade 9" });
    fireEvent.change(screen.getByRole("combobox", { name: "Grade" }), {
      target: { value: "9" },
    });
    await screen.findByRole("option", { name: "Mathematics" });
    fireEvent.change(screen.getByRole("combobox", { name: "Subject" }), {
      target: { value: "12" },
    });
    await screen.findByRole("option", { name: "Mathematics 9" });
    fireEvent.change(screen.getByRole("combobox", { name: "Book" }), {
      target: { value: "4" },
    });
    await screen.findByRole("option", { name: "Number Systems" });
    fireEvent.change(screen.getByRole("combobox", { name: "Chapter" }), {
      target: { value: "5" },
    });

    expect(
      await screen.findByRole("option", { name: "Integers" }),
    ).toBeInTheDocument();
    expect(api.getTopics).toHaveBeenCalledWith(5);
  });

  it("shows an empty state when the API has no curricula", async () => {
    vi.mocked(api.getCurricula).mockResolvedValue({ curricula: [] });

    render(
      <QueryProvider>
        <CurriculumBrowser />
      </QueryProvider>,
    );

    expect(
      await screen.findByText("No curriculum available."),
    ).toBeInTheDocument();
  });

  it("links to the external PCTB e-book directory without hosting book files", async () => {
    render(
      <QueryProvider>
        <CurriculumBrowser />
      </QueryProvider>,
    );

    const directoryLink = screen.getByRole("link", {
      name: "Browse PCTB e-books",
    });
    expect(directoryLink).toHaveAttribute(
      "href",
      "https://literaria.edu.pk/pctb-e-books/",
    );
    expect(directoryLink).toHaveAttribute("target", "_blank");
    expect(
      screen.getByText(/Books open at their linked source and are not hosted/),
    ).toBeInTheDocument();
  });
});
