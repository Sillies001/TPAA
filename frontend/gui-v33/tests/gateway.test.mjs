import assert from "node:assert/strict";
import test from "node:test";

import {
  AsyncGateway,
  GatewayError,
  collectCursorPages,
  validateMediaTicket,
  validateSeriesRange,
} from "../src/services/gateway.ts";

const jsonResponse = (value, status = 200) => new Response(JSON.stringify(value), {
  status,
  headers: { "Content-Type": "application/json" },
});

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

test("deduplicates identical inflight reads", async () => {
  let calls = 0;
  const gateway = new AsyncGateway(async () => {
    calls += 1;
    await sleep(10);
    return jsonResponse({ value: 1 });
  });
  gateway.setPartition("principal:A", "release:A");
  const [left, right] = await Promise.all([
    gateway.request({ path: "/same" }),
    gateway.request({ path: "/same" }),
  ]);
  assert.deepEqual(left, { value: 1 });
  assert.deepEqual(right, { value: 1 });
  assert.equal(calls, 1);
});

test("cancellation and timeout are distinct fail-closed errors", async () => {
  const fetcher = (_url, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });
  const gateway = new AsyncGateway(fetcher);
  gateway.setPartition("principal:A", null);
  const cancelled = gateway.request({ path: "/cancel", channel: "work", timeoutMs: 1000 });
  gateway.cancel("work");
  await assert.rejects(cancelled, (error) => error instanceof GatewayError && error.code === "ABORTED");
  await assert.rejects(
    gateway.request({ path: "/timeout", timeoutMs: 5 }),
    (error) => error instanceof GatewayError && error.code === "TIMEOUT" && error.retryable,
  );
});

test("superseded response is rejected as stale even when transport ignores abort", async () => {
  const gateway = new AsyncGateway(async (input) => {
    const slow = String(input).includes("version=old");
    await sleep(slow ? 30 : 2);
    return jsonResponse({ version: slow ? "old" : "new" });
  });
  gateway.setPartition("principal:A", "release:A");
  const old = gateway.latest("selection", { path: "/value", query: { version: "old" } });
  await sleep(1);
  const current = gateway.latest("selection", { path: "/value", query: { version: "new" } });
  assert.deepEqual(await current, { version: "new" });
  await assert.rejects(old, (error) => error instanceof GatewayError && error.code === "STALE_RESPONSE");
});

test("memory cache is isolated by principal and release partitions", async () => {
  let calls = 0;
  const gateway = new AsyncGateway(async () => jsonResponse({ call: ++calls }));
  gateway.setPartition("principal:A", "release:A");
  assert.deepEqual(await gateway.request({ path: "/cached", cacheTtlMs: 1000 }), { call: 1 });
  assert.deepEqual(await gateway.request({ path: "/cached", cacheTtlMs: 1000 }), { call: 1 });
  gateway.setPartition("principal:A", "release:B");
  assert.deepEqual(await gateway.request({ path: "/cached", cacheTtlMs: 1000 }), { call: 2 });
  gateway.setPartition("principal:B", "release:B");
  assert.deepEqual(await gateway.request({ path: "/cached", cacheTtlMs: 1000 }), { call: 3 });
});

test("large cursor collection paginates and detects loops", async () => {
  const values = Array.from({ length: 250 }, (_, index) => index);
  const collected = await collectCursorPages(async (cursor) => {
    const offset = cursor === null ? 0 : Number(cursor);
    const items = values.slice(offset, offset + 60);
    const next = offset + items.length;
    return { items, nextCursor: next < values.length ? String(next) : null };
  });
  assert.deepEqual(collected, values);
  await assert.rejects(
    collectCursorPages(async () => ({ items: [1], nextCursor: "same" })),
    (error) => error instanceof GatewayError && error.code === "CURSOR_LOOP",
  );
});

test("backend error shape preserves code, reason, provenance and retry policy", async () => {
  const gateway = new AsyncGateway(async () => jsonResponse({
    code: "BACKEND_UNAVAILABLE",
    reason_code: "DATABASE_NOT_READY",
    retryable: true,
    provenance: { authority_id: "GUI_ASYNC_GATEWAY_AUTHORITY" },
  }, 503));
  gateway.setPartition("principal:A", null);
  await assert.rejects(
    gateway.request({ path: "/failure" }),
    (error) => error instanceof GatewayError
      && error.code === "BACKEND_UNAVAILABLE"
      && error.reasonCode === "DATABASE_NOT_READY"
      && error.retryable
      && error.provenance.authority_id === "GUI_ASYNC_GATEWAY_AUTHORITY",
  );
});

test("range/LOD and media ticket validation reject unsafe inputs", () => {
  assert.equal(validateSeriesRange({
    releaseId: "release",
    parameter: "altitude",
    startSessionTimeUs: "10000000000000001",
    endSessionTimeUs: "10000000000000009",
    lod: "BALANCED",
    maxPoints: 2000,
  }).maxPoints, 2000);
  assert.throws(
    () => validateSeriesRange({
      releaseId: "release",
      parameter: "altitude",
      startSessionTimeUs: "2",
      endSessionTimeUs: "1",
      lod: "DETAIL",
      maxPoints: 2000,
    }),
    (error) => error instanceof GatewayError && error.code === "INVALID_RESPONSE",
  );
  const ticket = {
    schema: "TPAA_MEDIA_TICKET_V1",
    request_id: "request",
    provenance: {},
    ticket: "opaque-ticket",
    release_id: "release",
    media_id: "media",
    content_type: "video/mp4",
    size_bytes: 1024,
    range_supported: true,
    expires_at: new Date(Date.now() + 60_000).toISOString(),
  };
  assert.equal(validateMediaTicket(ticket).ticket, "opaque-ticket");
  assert.throws(
    () => validateMediaTicket({ ...ticket, ticket: "C:\\secret\\media.mp4" }),
    (error) => error instanceof GatewayError && error.code === "INVALID_RESPONSE",
  );
});
