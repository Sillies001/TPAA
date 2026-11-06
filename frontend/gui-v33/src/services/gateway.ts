import {
  G3_GATEWAY_POLICY,
  G3_GATEWAY_ROUTES,
  type GuiBootstrapDTO,
  type GuiCatalogDTO,
  type GuiSelectorDTO,
  type MediaTicketDTO,
  type SeriesRangeRequest,
} from "../generated/g3-gateway.ts";

export type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class GatewayError extends Error {
  readonly code: string;
  readonly status: number | null;
  readonly reasonCode: string;
  readonly retryable: boolean;
  readonly provenance: Readonly<Record<string, unknown>>;

  constructor(
    code: string,
    options: {
      status?: number | null;
      reasonCode?: string;
      retryable?: boolean;
      provenance?: Readonly<Record<string, unknown>>;
    } = {},
  ) {
    super(code);
    this.name = "GatewayError";
    this.code = code;
    this.status = options.status ?? null;
    this.reasonCode = options.reasonCode ?? code;
    this.retryable = options.retryable ?? false;
    this.provenance = options.provenance ?? {};
  }
}

export interface GatewayRequest<T> {
  readonly path: string;
  readonly method?: "GET" | "POST";
  readonly query?: Readonly<Record<string, string | number | null | undefined>>;
  readonly body?: unknown;
  readonly timeoutMs?: number;
  readonly cacheTtlMs?: number;
  readonly channel?: string;
  readonly signal?: AbortSignal;
  readonly validate?: (value: unknown) => value is T;
}

interface CacheEntry {
  readonly expiresAt: number;
  readonly value: unknown;
}

interface InflightEntry<T> {
  readonly controller: AbortController;
  readonly promise: Promise<T>;
}

const canonicalQuery = (
  query: GatewayRequest<unknown>["query"],
): string => {
  const params = new URLSearchParams();
  Object.entries(query ?? {})
    .filter(([, value]) => value !== null && value !== undefined)
    .sort(([left], [right]) => left.localeCompare(right))
    .forEach(([key, value]) => params.set(key, String(value)));
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
};

const stableBody = (body: unknown): string => {
  if (body === undefined) return "";
  if (body === null || typeof body !== "object") return JSON.stringify(body);
  if (Array.isArray(body)) return `[${body.map(stableBody).join(",")}]`;
  return `{${Object.entries(body as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${JSON.stringify(key)}:${stableBody(value)}`)
    .join(",")}}`;
};

const gatewayErrorFromResponse = async (response: Response): Promise<GatewayError> => {
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  const record = payload && typeof payload === "object" ? payload as Record<string, unknown> : {};
  return new GatewayError(
    typeof record.code === "string" ? record.code : `HTTP_${response.status}`,
    {
      status: response.status,
      reasonCode: typeof record.reason_code === "string" ? record.reason_code : undefined,
      retryable: record.retryable === true || response.status >= 500,
      provenance: record.provenance && typeof record.provenance === "object"
        ? record.provenance as Readonly<Record<string, unknown>>
        : {},
    },
  );
};

export class AsyncGateway {
  private readonly fetcher: Fetcher;
  private partition = "UNBOUND";
  private readonly inflight = new Map<string, InflightEntry<unknown>>();
  private readonly cache = new Map<string, CacheEntry>();
  private readonly channelControllers = new Map<string, AbortController>();
  private readonly generations = new Map<string, number>();

  constructor(fetcher: Fetcher = globalThis.fetch.bind(globalThis)) {
    this.fetcher = fetcher;
  }

  setPartition(principalCacheKey: string, releaseId: string | null): void {
    if (!principalCacheKey) throw new GatewayError("INVALID_RESPONSE");
    const next = `${principalCacheKey}|release:${releaseId ?? "NONE"}`;
    if (next === this.partition) return;
    this.abortAll();
    this.cache.clear();
    this.generations.clear();
    this.partition = next;
  }

  cancel(channel: string): void {
    this.channelControllers.get(channel)?.abort("ABORTED");
    this.channelControllers.delete(channel);
  }

  abortAll(): void {
    for (const entry of this.inflight.values()) entry.controller.abort("ABORTED");
    this.inflight.clear();
    this.channelControllers.clear();
  }

  async request<T>(spec: GatewayRequest<T>): Promise<T> {
    const method = spec.method ?? "GET";
    const url = `${spec.path}${canonicalQuery(spec.query)}`;
    const body = stableBody(spec.body);
    const key = `${this.partition}|${method}|${url}|${body}`;
    const cached = this.cache.get(key);
    if (cached && cached.expiresAt > Date.now()) return cached.value as T;
    if (cached) this.cache.delete(key);
    const existing = this.inflight.get(key) as InflightEntry<T> | undefined;
    if (existing) return existing.promise;

    const controller = new AbortController();
    if (spec.channel) {
      this.channelControllers.get(spec.channel)?.abort("ABORTED");
      this.channelControllers.set(spec.channel, controller);
    }
    const externalAbort = (): void => controller.abort("ABORTED");
    spec.signal?.addEventListener("abort", externalAbort, { once: true });
    const maximumTimeout = G3_GATEWAY_POLICY.request_policy.maximum_timeout_ms;
    const timeoutMs = Math.min(
      Math.max(spec.timeoutMs ?? G3_GATEWAY_POLICY.request_policy.default_timeout_ms, 1),
      maximumTimeout,
    );
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort("TIMEOUT");
    }, timeoutMs);

    const promise = (async (): Promise<T> => {
      try {
        const response = await this.fetcher(url, {
          method,
          credentials: "same-origin",
          cache: "no-store",
          headers: {
            Accept: "application/json",
            ...(body ? { "Content-Type": "application/json" } : {}),
          },
          body: body || undefined,
          signal: controller.signal,
        });
        if (!response.ok) throw await gatewayErrorFromResponse(response);
        const value: unknown = await response.json();
        if (spec.validate && !spec.validate(value)) throw new GatewayError("INVALID_RESPONSE");
        const ttl = spec.cacheTtlMs ?? 0;
        if (ttl > 0) this.cache.set(key, { expiresAt: Date.now() + ttl, value });
        return value as T;
      } catch (error) {
        if (error instanceof GatewayError) throw error;
        if (controller.signal.aborted) {
          throw new GatewayError(timedOut ? "TIMEOUT" : "ABORTED", { retryable: timedOut });
        }
        throw new GatewayError("BACKEND_UNAVAILABLE", { retryable: true });
      } finally {
        clearTimeout(timeout);
        spec.signal?.removeEventListener("abort", externalAbort);
        this.inflight.delete(key);
        if (spec.channel && this.channelControllers.get(spec.channel) === controller) {
          this.channelControllers.delete(spec.channel);
        }
      }
    })();
    this.inflight.set(key, { controller, promise });
    return promise;
  }

  async latest<T>(channel: string, spec: GatewayRequest<T>): Promise<T> {
    const generation = (this.generations.get(channel) ?? 0) + 1;
    this.generations.set(channel, generation);
    const value = await this.request({ ...spec, channel });
    if (this.generations.get(channel) !== generation) {
      throw new GatewayError("STALE_RESPONSE");
    }
    return value;
  }
}

export const collectCursorPages = async <T>(
  fetchPage: (cursor: string | null, signal: AbortSignal) => Promise<{
    readonly items: readonly T[];
    readonly nextCursor: string | null;
  }>,
  options: { readonly signal?: AbortSignal; readonly maximumPages?: number } = {},
): Promise<readonly T[]> => {
  const controller = new AbortController();
  const abort = (): void => controller.abort("ABORTED");
  options.signal?.addEventListener("abort", abort, { once: true });
  const seen = new Set<string>();
  const items: T[] = [];
  let cursor: string | null = null;
  const maximumPages = options.maximumPages
    ?? G3_GATEWAY_POLICY.pagination_policy.maximum_pages_per_collection;
  try {
    for (let page = 0; page < maximumPages; page += 1) {
      if (controller.signal.aborted) throw new GatewayError("ABORTED");
      const result = await fetchPage(cursor, controller.signal);
      items.push(...result.items);
      if (result.nextCursor === null) return items;
      if (seen.has(result.nextCursor)) throw new GatewayError("CURSOR_LOOP");
      seen.add(result.nextCursor);
      cursor = result.nextCursor;
    }
    throw new GatewayError("CURSOR_LOOP");
  } finally {
    options.signal?.removeEventListener("abort", abort);
  }
};

export const validateSeriesRange = (request: SeriesRangeRequest): SeriesRangeRequest => {
  const decimal = /^-?\d+$/;
  if (!decimal.test(request.startSessionTimeUs) || !decimal.test(request.endSessionTimeUs)) {
    throw new GatewayError("INVALID_RESPONSE");
  }
  if (BigInt(request.startSessionTimeUs) >= BigInt(request.endSessionTimeUs)) {
    throw new GatewayError("INVALID_RESPONSE");
  }
  if (
    request.maxPoints < 1
    || request.maxPoints > G3_GATEWAY_POLICY.range_policy.maximum_points
  ) {
    throw new GatewayError("INVALID_RESPONSE");
  }
  return request;
};

export const validateMediaTicket = (value: MediaTicketDTO, now = Date.now()): MediaTicketDTO => {
  if (
    !value.ticket
    || value.ticket.includes("/")
    || value.ticket.includes("\\")
    || !value.content_type
    || value.size_bytes < 0
    || value.range_supported !== true
    || Date.parse(value.expires_at) <= now
  ) {
    throw new GatewayError("INVALID_RESPONSE");
  }
  return value;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object";

const isBootstrap = (value: unknown): value is GuiBootstrapDTO =>
  isRecord(value)
  && value.schema === "TPAA_GUI_BOOTSTRAP_V1"
  && typeof value.cache_partition_key === "string"
  && isRecord(value.catalog)
  && isRecord(value.principal);

export const createGuiClient = (gateway: AsyncGateway) => ({
  bootstrap: (): Promise<GuiBootstrapDTO> => gateway.latest("bootstrap", {
    path: G3_GATEWAY_ROUTES["gui.bootstrap"].path,
    cacheTtlMs: G3_GATEWAY_POLICY.cache_policy.bootstrap_ttl_ms,
    validate: isBootstrap,
  }),
  catalog: (): Promise<GuiCatalogDTO> => gateway.latest("catalog", {
    path: G3_GATEWAY_ROUTES["gui.catalog"].path,
    cacheTtlMs: G3_GATEWAY_POLICY.cache_policy.catalog_ttl_ms,
    validate: (value): value is GuiCatalogDTO => isRecord(value) && value.schema === "TPAA_GUI_CATALOG_V1",
  }),
  selector: (
    selectorId: string,
    query: { readonly cursor?: string; readonly limit?: number; readonly releaseId?: string } = {},
  ): Promise<GuiSelectorDTO> => gateway.latest(`selector:${selectorId}`, {
    path: G3_GATEWAY_ROUTES["gui.selector"].path.replace("{selector_id}", encodeURIComponent(selectorId)),
    query: {
      cursor: query.cursor,
      limit: query.limit,
      release_id: query.releaseId,
    },
    cacheTtlMs: G3_GATEWAY_POLICY.cache_policy.selector_ttl_ms,
    validate: (value): value is GuiSelectorDTO =>
      isRecord(value)
      && value.schema === "TPAA_GUI_SELECTOR_V1"
      && value.selector_id === selectorId
      && Array.isArray(value.items),
  }),
});
