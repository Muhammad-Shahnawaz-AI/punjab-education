import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminBooksPage from "./AdminBooksPage";

const apiMocks = vi.hoisted(() => ({
  cancelAdminBookUpload: vi.fn(),
  deleteAdminBook: vi.fn(),
  getAdminBookUploadPolicy: vi.fn(),
  getAdminBooks: vi.fn(),
  getCurricula: vi.fn(),
  getGrades: vi.fn(),
  getSubjects: vi.fn(),
  retryAdminBookProcessing: vi.fn(),
  uploadAdminBook: vi.fn(),
}));

vi.mock("../lib/api", () => apiMocks);

const policy = {
  max_size_bytes: 20 * 1024 * 1024 * 1024,
  part_size_bytes: 8 * 1024 * 1024,
  max_concurrent_uploads: 2,
  provider: "local",
};
const book = {
  book_id: 42,
  title: "Grade 9 Mathematics",
  filename: "math.pdf",
  file_size: 5,
  grade: 9,
  subject: "Mathematics",
  curriculum: "Punjab Curriculum",
  author: null,
  language: "English",
  edition: null,
  description: null,
  upload_date: "2026-10-09T00:00:00Z",
  upload_status: "completed",
  processing_status: "queued",
  processing_stage: "queued",
  processing_progress: 0,
  page_count: 0,
  ocr_used: false,
  last_error: null,
  retry_count: 0,
  checksum_sha256: null,
};

describe("AdminBooksPage", () => {
  beforeEach(() => {
    apiMocks.getAdminBookUploadPolicy.mockReset().mockResolvedValue(policy);
    apiMocks.getAdminBooks.mockReset().mockResolvedValue([]);
    apiMocks.getCurricula.mockReset().mockResolvedValue({
      curricula: [{ id: "punjab", name: "Punjab Curriculum", description: "", is_sample: false }],
    });
    apiMocks.getGrades.mockReset().mockResolvedValue({ items: [{ id: 9, name: "Grade 9" }] });
    apiMocks.getSubjects.mockReset().mockResolvedValue({ items: [{ id: 4, name: "Mathematics" }] });
    apiMocks.uploadAdminBook.mockReset();
    apiMocks.cancelAdminBookUpload.mockReset().mockResolvedValue(undefined);
    apiMocks.retryAdminBookProcessing.mockReset().mockResolvedValue(book);
    apiMocks.deleteAdminBook.mockReset().mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  async function selectAuthorizedPdf() {
    render(<AdminBooksPage />);
    const file = new File(["%PDF-sample"], "math.pdf", { type: "application/pdf" });
    fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
      target: { files: [file] },
    });
    fireEvent.change(screen.getByLabelText("Source / publisher"), {
      target: { value: "Punjab Board" },
    });
    fireEvent.change(screen.getByLabelText("Source URL (HTTPS)"), {
      target: { value: "https://example.org/math.pdf" },
    });
    fireEvent.change(screen.getByLabelText("Rights basis / permission details"), {
      target: { value: "Written permission granted for educational use." },
    });
    fireEvent.click(screen.getByLabelText(/I confirm this material may be stored/));
    await screen.findByText("math.pdf · 11 B");
    await waitFor(() => {
      expect(screen.getByLabelText("Grade / class")).toHaveValue("9");
      expect(screen.getByLabelText("Subject")).toHaveValue("4");
    });
    return file;
  }

  it("reports an upload failure and resumes through the retry action", async () => {
    const file = await selectAuthorizedPdf();
    apiMocks.uploadAdminBook
      .mockImplementationOnce(
        async (
          _file: File,
          _metadata: unknown,
          options: {
            onSession: (id: string) => void;
            onProgress: (loaded: number, total: number) => void;
          },
        ) => {
          options.onSession("upload-1");
          options.onProgress(5, file.size);
          throw new Error("Connection interrupted");
        },
      )
      .mockImplementationOnce(
        async (
          _file: File,
          _metadata: unknown,
          options: {
            existingSessionId?: string;
            onProgress: (loaded: number, total: number) => void;
          },
        ) => {
          expect(options.existingSessionId).toBe("upload-1");
          options.onProgress(file.size, file.size);
          await new Promise((resolve) => setTimeout(resolve, 20));
          return { session: { id: "upload-1" }, book };
        },
      );

    fireEvent.click(screen.getByRole("button", { name: "Upload queued books" }));
    expect(await screen.findByText("Connection interrupted")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry math.pdf" }));

    expect(await screen.findByText(/server-side PDF processing is underway/)).toBeInTheDocument();
    expect(apiMocks.uploadAdminBook).toHaveBeenCalledTimes(2);
    expect(apiMocks.getAdminBooks).toHaveBeenCalled();
  });

  it("pauses an active transfer and cancels its resumable session", async () => {
    await selectAuthorizedPdf();
    apiMocks.uploadAdminBook.mockImplementation(
      async (
        _file: File,
        _metadata: unknown,
        options: {
          signal: AbortSignal;
          onSession: (id: string) => void;
          onProgress: (loaded: number, total: number) => void;
        },
      ) => {
        options.onSession("upload-2");
        options.onProgress(5, 10);
        return new Promise((_resolve, reject) => {
          options.signal.addEventListener(
            "abort",
            () => reject(new DOMException("Upload paused.", "AbortError")),
            { once: true },
          );
        });
      },
    );

    fireEvent.click(screen.getByRole("button", { name: "Upload queued books" }));
    await screen.findByRole("button", { name: "Pause math.pdf" });
    fireEvent.click(screen.getByRole("button", { name: "Pause math.pdf" }));
    await screen.findByText(/Paused; resume to continue/);
    fireEvent.click(screen.getByRole("button", { name: "Cancel math.pdf" }));

    await waitFor(() => expect(apiMocks.cancelAdminBookUpload).toHaveBeenCalledWith("upload-2"));
    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
  });
});
