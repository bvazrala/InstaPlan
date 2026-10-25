import { test, expect } from "@playwright/test";
import { option, status, trip } from "../fixtures";

test("live comparison, responsive costs, sorting and capacity-confirmed picking", async ({ page }, info) => {
  let picked = false;
  let acknowledgment: boolean | undefined;
  let optionReads = 0;
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const options = [option({ title: "New York shared apartment", id: "a" }), option({ id: "b", title: "New York garden rental", groupTotal: 730.01, maxTravelHours: 4, fairestRank: 2,
    people: option().people.map((person, index) => ({ ...person, cost: person.cost! + 10, subtotal: person.subtotal! + 10, hours: [1.5, 3, 4][index] })) })];
  await page.route("**/trips/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    const headers = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };
    if (route.request().method() === "OPTIONS") { await route.fulfill({ status: 204, headers }); return; }
    if(path.endsWith('/planner')) {await route.fulfill({status:404,json:{detail:'Planner not found'},headers});return;}
    let body: unknown;
    if (path.endsWith("/pick")) { acknowledgment = route.request().postDataJSON().acknowledgeCapacity; picked = true; body = { ...trip, id: "qa-trip", stage: "picked", pickedOptionId: "a" }; }
    else if (path.endsWith("/options/status")) body = status;
    else if (path.endsWith("/options")) { body = options; optionReads++; }
    else if (path.endsWith("/facts")) body = [];
    else body = { ...trip, id: "qa-trip", pickedOptionId: picked ? "a" : null, stage: picked ? "picked" : "options" };
    await route.fulfill({ json: body, headers });
  });
  await page.route("**/chats/**/members", (route) => route.fulfill({ json: [
    { id: "alice", name: "Alice", hue: 260 }, { id: "bob", name: "Bob", hue: 40 }, { id: "cara", name: "Cara", hue: 180 },
  ], headers: { "access-control-allow-origin": "*" } }));
  await page.route("**/health", (route) => route.fulfill({ json: { ok: true, demoMode: true, demoUserId: "demo-you" }, headers: { "access-control-allow-origin": "*" } }));
  await page.goto("/trip/qa-trip");
  await expect(page.getByRole("heading", { name: "2 options" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  const before = optionReads;
  await page.getByRole("tab", { name: "Cheapest" }).click();
  await expect(page.getByRole("article").first()).toHaveAttribute("aria-label", "New York shared apartment");
  await page.getByRole("tab", { name: "Fastest" }).click();
  await expect(page.getByRole("article").first()).toHaveAttribute("aria-label", "New York garden rental");
  await page.getByRole("tab", { name: "Balanced" }).click();
  await page.getByRole("slider").fill("1");
  await expect(page.getByRole("article").first()).toHaveAttribute("aria-label", "New York shared apartment");
  await page.getByRole("tab", { name: "Fairest" }).click();
  expect(optionReads).toBe(before);
  await expect(page.getByText(/333[.,]33/)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("options.png"), fullPage: true });
  const first = page.getByRole("article").first();
  await expect(first.getByRole("button", { name: "Pick this option" })).toBeDisabled();
  await first.getByRole("checkbox").check();
  await first.getByRole("button", { name: "Pick this option" }).click();
  await expect(page.getByText("Your group has picked an option. The selection is saved.")).toBeVisible();
  expect(acknowledgment).toBe(true);
  expect(errors).toEqual([]);
});
