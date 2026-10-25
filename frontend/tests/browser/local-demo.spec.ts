import { test, expect } from "@playwright/test";

test("local demo opens without a login and reaches the live planner", async ({ page }, info) => {
  test.skip(process.env.TEST_LOCAL_DEMO !== "true", "Requires the explicitly enabled local demo backend");
  const supabaseRequests: string[] = [];
  await page.route("**/*.supabase.co/**", async (route) => { supabaseRequests.push("request"); await route.abort(); });
  await page.goto("/");
  await expect(page.getByText("Local demo · sample people · saved on this computer")).toBeVisible();
  await expect(page.getByRole("main").getByText("Weekend crew (local demo)", { exact: true })).toBeVisible();
  await expect(page.getByText(/Let’s plan a New York trip/)).toBeVisible();
  await expect(page).not.toHaveURL(/\/login/);
  await page.getByRole("button", { name: "Add to chat" }).click();
  await page.getByRole("button", { name: "Planner", exact:true }).last().click();
  await expect(page.getByRole("dialog",{name:"Start a planner"})).toBeVisible();
  await expect(page.getByLabel("Topic",{exact:true})).toHaveValue("Dining");
  expect(supabaseRequests).toEqual([]);
  await page.screenshot({ path: info.outputPath("local-demo.png"), fullPage: true });
});
