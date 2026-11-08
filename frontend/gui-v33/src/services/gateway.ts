import {
  G3_GATEWAY_POLICY,
  G3_GATEWAY_ROUTES,
  type GuiBootstrapDTO,
  type GuiCatalogDTO,
  type GuiSelectorDTO,
  type MediaTicketDTO,
  type SeriesRangeRequest,
} from "../generated/g3-gateway.ts";
import {
  G4_BATCH_ROUTES,
  type BatchListDTO,
  type BatchRegistrationDTO,
  type ForceFormationContextDTO,
} from "../generated/g4-batch.ts";
import {
  G5_WEAPON_EVENT_ROUTES,
  type WeaponEventDetailDTO,
  type WeaponEventPerspectiveDTO,
  type WeaponEventWindowDTO,
} from "../generated/g5-weapon-event.ts";
import {
  G6_HISTORICAL_ROUTES,
  type HistoricalTrainingOverviewDTO,
} from "../generated/g6-historical.ts";
import {
  G7_BATCH_EVENTS_ROUTES,
  type BatchEventWorkbenchDTO,
} from "../generated/g7-batch-events.ts";
import {
  G8_CO_ATTACK_ROUTES,
  type CoAttackAnalysisDTO,
} from "../generated/g8-co-attack.ts";
import {
  G9_REPLAY_ROUTES,
  type ReplayContextDTO,
} from "../generated/g9-replay.ts";

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
  readonly headers?: Readonly<Record<string, string>>;
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
            ...spec.headers,
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
  batches: (): Promise<BatchListDTO> => gateway.latest("g4:batches", {
    path: G4_BATCH_ROUTES["gui.batches"].path,
    validate: (value): value is BatchListDTO =>
      isRecord(value)
      && value.schema === "TPAA_G4_BATCH_LIST_V1"
      && Array.isArray(value.items)
      && typeof value.total_count === "number",
  }),
  registerBatch: (
    idempotencyKey: string,
    body: Readonly<Record<string, unknown>>,
  ): Promise<BatchRegistrationDTO> => gateway.latest("g4:batch-register", {
    path: G4_BATCH_ROUTES["gui.batch.register"].path,
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body,
    validate: (value): value is BatchRegistrationDTO =>
      isRecord(value)
      && value.schema === "TPAA_G4_BATCH_REGISTRATION_V1"
      && typeof value.batch_id === "string"
      && typeof value.training_type_confirmed === "boolean",
  }),
  reviseBatchTrainingType: (
    batchId: string,
    body: Readonly<Record<string, unknown>>,
  ): Promise<BatchRegistrationDTO> => gateway.latest(`g4:batch-revise:${batchId}`, {
    path: G4_BATCH_ROUTES["gui.batch.training_type"].path.replace(
      "{batch_id}",
      encodeURIComponent(batchId),
    ),
    method: "POST",
    body,
    validate: (value): value is BatchRegistrationDTO =>
      isRecord(value)
      && value.schema === "TPAA_G4_BATCH_REGISTRATION_V1"
      && typeof value.batch_id === "string"
      && value.training_type_confirmed === true,
  }),
  context: (contextId: string): Promise<ForceFormationContextDTO> => gateway.latest(
    `g4:context:${contextId}`,
    {
      path: G4_BATCH_ROUTES["gui.context"].path.replace(
        "{context_id}",
        encodeURIComponent(contextId),
      ),
      validate: (value): value is ForceFormationContextDTO =>
        isRecord(value)
        && value.schema === "TPAA_G4_FORCE_FORMATION_CONTEXT_V1"
        && typeof value.context_id === "string"
        && Array.isArray(value.members),
    },
  ),
  reviseContext: (
    contextId: string,
    body: Readonly<Record<string, unknown>>,
  ): Promise<ForceFormationContextDTO> => gateway.latest(`g4:context-revise:${contextId}`, {
    path: G4_BATCH_ROUTES["gui.context.revise"].path.replace(
      "{context_id}",
      encodeURIComponent(contextId),
    ),
    method: "POST",
    body,
    validate: (value): value is ForceFormationContextDTO =>
      isRecord(value)
      && value.schema === "TPAA_G4_FORCE_FORMATION_CONTEXT_V1"
      && typeof value.context_id === "string"
      && Array.isArray(value.members),
  }),
  weaponEvent: (weaponEventId: string): Promise<WeaponEventDetailDTO> => gateway.latest(
    `g5:weapon-event:${weaponEventId}`,
    {
      path: G5_WEAPON_EVENT_ROUTES["gui.event.detail"].path.replace(
        "{weapon_event_id}",
        encodeURIComponent(weaponEventId),
      ),
      validate: (value): value is WeaponEventDetailDTO =>
        isRecord(value)
        && value.schema === "TPAA_G5_WEAPON_EVENT_DETAIL_V1"
        && value.weapon_event_id === weaponEventId,
    },
  ),
  weaponEventWindow: (
    weaponEventId: string,
    perspective: "shooter" | "target",
  ): Promise<WeaponEventWindowDTO> => gateway.latest(`g5:window:${weaponEventId}:${perspective}`, {
    path: G5_WEAPON_EVENT_ROUTES["gui.event.window"].path
      .replace("{weapon_event_id}", encodeURIComponent(weaponEventId))
      .replace("{perspective}", perspective),
    validate: (value): value is WeaponEventWindowDTO =>
      isRecord(value)
      && value.schema === "TPAA_G5_WEAPON_EVENT_WINDOW_V1"
      && value.weapon_event_id === weaponEventId
      && value.perspective === perspective,
  }),
  weaponEventPerspective: (
    weaponEventId: string,
    perspective: "shooter" | "target",
  ): Promise<WeaponEventPerspectiveDTO> => gateway.latest(
    `g5:perspective:${weaponEventId}:${perspective}`,
    {
      path: G5_WEAPON_EVENT_ROUTES["gui.event.perspective"].path
        .replace("{weapon_event_id}", encodeURIComponent(weaponEventId))
        .replace("{perspective}", perspective),
      validate: (value): value is WeaponEventPerspectiveDTO =>
        isRecord(value)
        && value.schema === "TPAA_G5_WEAPON_EVENT_PERSPECTIVE_V1"
        && value.weapon_event_id === weaponEventId
        && value.perspective === perspective,
    },
  ),
  historicalOverview: (
    query: {
      readonly startDate?: string;
      readonly endDate?: string;
      readonly model?: string;
      readonly trainingType?: string;
    } = {},
  ): Promise<HistoricalTrainingOverviewDTO> => gateway.latest("g6:overview", {
    path: G6_HISTORICAL_ROUTES["gui.overview"].path,
    query: {
      start_date: query.startDate,
      end_date: query.endDate,
      model: query.model,
      training_type: query.trainingType,
    },
    validate: (value): value is HistoricalTrainingOverviewDTO =>
      isRecord(value)
      && value.schema === "TPAA_G6_HISTORICAL_OVERVIEW_V1"
      && Array.isArray(value.batches)
      && typeof value.batch_set_fingerprint === "string",
  }),
  batchEvents: (
    batchId: string,
    query: {
      readonly category?: string;
      readonly adjudication?: string;
      readonly clusterId?: string;
      readonly entityId?: string;
      readonly episodeId?: string;
      readonly startTimeUs?: string;
      readonly endTimeUs?: string;
      readonly cursor?: string;
      readonly limit?: number;
    } = {},
  ): Promise<BatchEventWorkbenchDTO> => gateway.latest(`g7:batch-events:${batchId}`, {
    path: G7_BATCH_EVENTS_ROUTES["gui.batch.events"].path.replace(
      "{batch_id}",
      encodeURIComponent(batchId),
    ),
    query: {
      category: query.category,
      adjudication: query.adjudication,
      cluster_id: query.clusterId,
      entity_id: query.entityId,
      episode_id: query.episodeId,
      start_time_us: query.startTimeUs,
      end_time_us: query.endTimeUs,
      cursor: query.cursor,
      limit: query.limit,
    },
    validate: (value): value is BatchEventWorkbenchDTO =>
      isRecord(value)
      && value.schema === "TPAA_G7_BATCH_EVENT_WORKBENCH_V1"
      && typeof value.batch_id === "string"
      && Array.isArray(value.items),
  }),
  replayContext: (
    weaponEventId: string,
    query: { readonly releaseId: string; readonly contextId: string; readonly perspective: "shooter" | "target" },
  ): Promise<ReplayContextDTO> => gateway.latest(
    `g9:replay:${weaponEventId}:${query.releaseId}:${query.contextId}:${query.perspective}`,
    {
      path: G9_REPLAY_ROUTES["gui.replay"].path.replace(
        "{weapon_event_id}",
        encodeURIComponent(weaponEventId),
      ),
      query: {
        release_id: query.releaseId,
        context_id: query.contextId,
        perspective: query.perspective,
      },
      validate: (value): value is ReplayContextDTO =>
        isRecord(value)
        && value.schema === "TPAA_G9_REPLAY_CONTEXT_V1"
        && value.weapon_event_id === weaponEventId
        && value.release_id === query.releaseId
        && value.context_id === query.contextId
        && value.perspective === query.perspective,
    },
  ),
  coAttackAnalysis: (
    clusterId: string,
    query: { readonly contextId?: string } = {},
  ): Promise<CoAttackAnalysisDTO> => gateway.latest(`g8:co-attack:${clusterId}`, {
    path: G8_CO_ATTACK_ROUTES["gui.coattack"].path.replace(
      "{cluster_id}",
      encodeURIComponent(clusterId),
    ),
    query: { context_id: query.contextId },
    validate: (value): value is CoAttackAnalysisDTO =>
      isRecord(value)
      && value.schema === "TPAA_G8_CO_ATTACK_ANALYSIS_V1"
      && typeof value.cluster_id === "string",
  }),
});
