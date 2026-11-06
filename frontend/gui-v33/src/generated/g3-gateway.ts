// @generated from CB-1.8.0 GUI_ASYNC_GATEWAY_AUTHORITY; DO NOT EDIT.

export type GatewayStatus = "READY" | "EMPTY" | "DEGRADED" | "ERROR" | "FORBIDDEN" | "N_A";
export type GatewayLod = "SUMMARY" | "BALANCED" | "DETAIL";

export interface GatewayProvenance {
  readonly authorityId: string;
  readonly authorityVersion: string;
  readonly coreBaseline: string;
  readonly generatedAt?: string;
}

export interface GatewayEnvelope {
  readonly schema: string;
  readonly request_id: string;
  readonly reason_code?: string;
  readonly provenance: Readonly<Record<string, unknown>>;
}

export interface GuiCatalogDTO extends GatewayEnvelope {
  readonly catalog_version: string;
  readonly views: readonly Readonly<Record<string, unknown>>[];
  readonly modules: readonly Readonly<Record<string, unknown>>[];
  readonly features: readonly Readonly<Record<string, unknown>>[];
  readonly selectors: readonly Readonly<Record<string, unknown>>[];
  readonly routes: Readonly<Record<string, unknown>>;
}

export interface GuiBootstrapDTO extends GatewayEnvelope {
  readonly catalog: GuiCatalogDTO;
  readonly principal: Readonly<Record<string, unknown>>;
  readonly cache_partition_key: string;
  readonly selectors: readonly Readonly<Record<string, unknown>>[];
}

export interface GuiSelectorDTO extends GatewayEnvelope {
  readonly selector_id: string;
  readonly query_context_id: string;
  readonly items: readonly Readonly<Record<string, unknown>>[];
  readonly next_cursor: string | null;
  readonly total_count: number;
}

export interface SeriesRangeRequest {
  readonly releaseId: string;
  readonly parameter: string;
  readonly startSessionTimeUs: string;
  readonly endSessionTimeUs: string;
  readonly lod: GatewayLod;
  readonly maxPoints: number;
}

export interface MediaTicketDTO extends GatewayEnvelope {
  readonly ticket: string;
  readonly release_id: string;
  readonly media_id: string;
  readonly content_type: string;
  readonly size_bytes: number;
  readonly range_supported: boolean;
  readonly expires_at: string;
}

export const G3_GATEWAY_ROUTES = {
  "gui.bootstrap": {
    "method": "GET",
    "path": "/api/v1/gui/bootstrap",
    "responseDto": "GuiBootstrapDTO"
  },
  "gui.catalog": {
    "method": "GET",
    "path": "/api/v1/gui/catalog",
    "responseDto": "GuiCatalogDTO"
  },
  "gui.selector": {
    "method": "GET",
    "path": "/api/v1/gui/selectors/{selector_id}",
    "responseDto": "GuiSelectorDTO"
  }
} as const;
export const G3_GATEWAY_POLICY = {
  "cache_policy": {
    "bootstrap_ttl_ms": 0,
    "catalog_ttl_ms": 60000,
    "clear_on_partition_change": true,
    "cross_principal": "FORBIDDEN",
    "cross_release": "FORBIDDEN",
    "partition_keys": [
      "principal_cache_key",
      "release_id"
    ],
    "selector_ttl_ms": 15000,
    "storage": "SESSION_MEMORY_ONLY"
  },
  "error_policy": {
    "codes": [
      "ABORTED",
      "TIMEOUT",
      "STALE_RESPONSE",
      "CURSOR_INVALID",
      "CURSOR_LOOP",
      "CONTEXT_REQUIRED",
      "FORBIDDEN",
      "NOT_FOUND",
      "BACKEND_UNAVAILABLE",
      "INVALID_RESPONSE",
      "SYSTEM_ERROR"
    ],
    "dto": "GuiGatewayErrorDTO",
    "reason_and_provenance_required": true,
    "unknown": "SYSTEM_ERROR_FAIL_CLOSED"
  },
  "media_ticket_policy": {
    "absolute_path": "FORBIDDEN",
    "content_type_required": true,
    "range_required": true,
    "size_required": true,
    "ticket": "OPAQUE_SHORT_LIVED"
  },
  "pagination_policy": {
    "cursor": "OPAQUE_VERSIONED",
    "cursor_loop_policy": "ERROR",
    "default_limit": 50,
    "maximum_limit": 100,
    "maximum_pages_per_collection": 100
  },
  "range_policy": {
    "default_max_points": 2000,
    "lod_values": [
      "SUMMARY",
      "BALANCED",
      "DETAIL"
    ],
    "maximum_points": 10000,
    "preserve_event_anchors": true,
    "preserve_extrema": true,
    "session_time_transport": "DECIMAL_STRING"
  },
  "request_policy": {
    "cancel_superseded": true,
    "deduplicate_inflight": true,
    "default_timeout_ms": 8000,
    "discard_stale_response": true,
    "maximum_timeout_ms": 30000,
    "retry_unsafe_methods": false
  }
} as const;
