import {readFile} from "node:fs/promises";
import {expect, test} from "@playwright/test";

test("renders disjoint reader boxes, navigates and inspects the graph", async ({page}) => {
  await page.goto("/");
  await expect(page.getByText("Synthetic data")).toBeVisible();
  const diagram = page.getByRole("group", {name: "Reader transition diagram"});
  await expect(diagram).toBeVisible();
  await expect(diagram.getByRole("button", {name: /^Reader /})).toHaveCount(6);
  const bounds = (await diagram.boundingBox())!;
  const initial = await diagram.getAttribute("viewBox");
  await page.mouse.move(bounds.x + 12, bounds.y + 12);
  await page.mouse.down();
  await page.mouse.move(bounds.x + 62, bounds.y + 34);
  await page.mouse.up();
  expect(await diagram.getAttribute("viewBox")).not.toEqual(initial);
  await page.getByRole("button", {name: "Fit"}).click();
  const overlaps = await diagram.locator(".reader rect").evaluateAll(elements =>
    elements.some((element, index) => {
      const box = element.getBoundingClientRect();
      return elements.slice(index + 1).some(other => {
        const next = other.getBoundingClientRect();
        return Math.min(box.right, next.right) - Math.max(box.left, next.left) > 1 &&
          Math.min(box.bottom, next.bottom) - Math.max(box.top, next.top) > 1;
      });
    }),
  );
  expect(overlaps).toBe(false);
  await diagram.getByRole("button", {name: "A to B", exact: true}).press("Enter");
  const details = page.getByRole("complementary", {name: "Graph details"});
  await expect(details.getByRole("heading", {name: "A → B"})).toBeVisible();
  await expect(details.getByText("6 min", {exact: true})).toHaveCount(4);

  await page.getByLabel("Find a reader").fill("D");
  await page.locator(".search-results").getByRole("button", {name: "D P / L1"}).click();
  await expect(details.getByRole("heading", {name: "D", exact: true})).toBeVisible();
  const before = await diagram.getAttribute("viewBox");
  await page.getByRole("button", {name: "Zoom in"}).click();
  expect(await diagram.getAttribute("viewBox")).not.toEqual(before);
  const lineFilter = page.getByRole("combobox", {name: "Line", exact: true});
  await lineFilter.selectOption({label: "P / L2"});
  await expect(diagram.getByRole("button", {name: /^Reader /})).toHaveCount(3);
  await expect(page.getByText("3 readers · 0 links")).toBeVisible();
  await lineFilter.selectOption({label: "All lines"});
  await page.getByLabel("Min. transitions").fill("2");
  await expect(page.getByText("6 readers · 0 links")).toBeVisible();
});

test("exports the unfiltered layout and serves a versioned graph", async ({page, request}) => {
  const response = await request.get("/api/topology");
  expect(response.ok()).toBe(true);
  const etag = response.headers().etag;
  expect((await request.get("/api/topology", {headers: {"If-None-Match": etag}})).status()).toBe(304);
  await page.goto("/");
  await page.getByRole("combobox", {name: "Line", exact: true}).selectOption({label: "P / L2"});
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", {name: "Export layout"}).click();
  const download = await downloadEvent;
  const layout = JSON.parse(await readFile((await download.path())!, "utf-8"));
  expect(layout.engine).toBe("elk-layered");
  expect(layout.topologyId).toBe(etag.slice(1, -1));
  expect(Object.keys(layout.nodes)).toHaveLength(6);
  expect(Object.keys(layout.edges)).toHaveLength(2);
});

test("fits the graph controls on a narrow screen", async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await page.goto("/");
  await expect(page.getByRole("group", {name: "Reader transition diagram"})).toBeVisible();
  const [pageWidth, viewportWidth] = await page.evaluate(() =>
    [document.documentElement.scrollWidth, window.innerWidth]);
  expect(pageWidth).toBe(viewportWidth);
  await expect(page.getByRole("button", {name: "Zoom in"})).toBeVisible();
});

test("keeps all readers available when a larger graph uses the grouped grid", async ({page, request}) => {
  const graph = await (await request.get("/api/topology")).json();
  const sample = graph.nodes[0];
  for (let index = 0; index < 221; index++) {
    graph.nodes.push({...sample, id: `synthetic-${index}`, label: `Extra ${index}`, lineId: "L3"});
  }
  await page.route("**/api/topology", route => route.fulfill({json: graph}));
  await page.goto("/");
  const diagram = page.getByRole("group", {name: "Reader transition diagram"});
  await expect(diagram.getByRole("button", {name: /^Reader /})).toHaveCount(227);
  await page.getByRole("combobox", {name: "Line", exact: true}).selectOption({label: "P / L3"});
  await expect(diagram.getByRole("button", {name: /^Reader /})).toHaveCount(221);
});

test("picks up new weights while keeping layout and zoom", async ({page, request}) => {
  const first = await (await request.get("/api/topology")).json();
  const second = structuredClone(first);
  second.topologyId = "a".repeat(64);
  second.quality.includedPairs = 7;
  second.edges[0].transitionCount += 5;
  let current = first;
  await page.route("**/api/topology", route => route.fulfill({json: current}));
  await page.goto("/");
  const diagram = page.getByRole("group", {name: "Reader transition diagram"});
  await expect(diagram).toBeVisible();
  await page.getByRole("button", {name: "Zoom in"}).click();
  const viewport = await diagram.getAttribute("viewBox");
  const stats = page.getByRole("region", {name: "Graph metrics"});
  current = second;
  await expect(stats.getByText("7", {exact: true})).toBeVisible({timeout: 6500});
  expect(await diagram.getAttribute("viewBox")).toBe(viewport);
});
