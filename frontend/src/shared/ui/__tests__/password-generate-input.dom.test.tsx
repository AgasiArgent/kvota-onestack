import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PasswordGenerateInput } from "@/shared/ui/password-generate-input";

describe("PasswordGenerateInput", () => {
  it("calls onChange with a 12-char password when generate is clicked", () => {
    const onChange = vi.fn();
    render(<PasswordGenerateInput value="" onChange={onChange} />);
    fireEvent.click(screen.getByTitle("Сгенерировать пароль"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toHaveLength(12);
  });

  it("calls onChange when the user types", () => {
    const onChange = vi.fn();
    render(<PasswordGenerateInput value="" onChange={onChange} />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "hunter2!" },
    });
    expect(onChange).toHaveBeenCalledWith("hunter2!");
  });

  it("disables the copy button when value is empty", () => {
    render(<PasswordGenerateInput value="" onChange={() => {}} />);
    expect(screen.getByTitle("Скопировать пароль")).toBeDisabled();
  });
});
