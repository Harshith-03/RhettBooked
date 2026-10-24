import { beforeEach, describe, expect, it } from "vitest";
import { applyTheme, getInitialTheme, setTheme } from "../theme";

describe("theme controller", () => {
  beforeEach(() => {
    sessionStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("applyTheme sets data-theme on <html>", () => {
    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("setTheme remembers the choice for the session", () => {
    setTheme("dark");
    expect(sessionStorage.getItem("eventtwin-theme")).toBe("dark");
    expect(getInitialTheme()).toBe("dark");
  });

  it("defaults to light when no preference and no stored choice", () => {
    // setup.ts stubs matchMedia to matches:false (i.e. not dark).
    expect(getInitialTheme()).toBe("light");
  });
});
