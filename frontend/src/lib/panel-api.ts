import "server-only";

import { headers } from "next/headers";

import type {
  CustomerDetailsSnapshot,
  CustomerListSnapshot,
  OrderDetailsSnapshot,
  OrderListSnapshot,
  PanelSnapshot
} from "@/lib/panel-types";
import { getBackendAuthorizationHeader } from "@/lib/admin-session";

const EMPTY_SNAPSHOT: PanelSnapshot = {
  dashboard: {
    generated_at: "-",
    reference_date: "-",
    metrics: [],
    kanban_columns: []
  },
  process_sections: [],
  whatsapp_cards: [],
  sync_overview: {
    metrics: [],
    alerts: []
  }
};

const EMPTY_CUSTOMERS: CustomerListSnapshot = {
  items: [],
  count: 0
};

const EMPTY_CUSTOMER_DETAILS: CustomerDetailsSnapshot = {
  item: null
};

const EMPTY_ORDERS: OrderListSnapshot = {
  items: [],
  count: 0
};

const EMPTY_ORDER_DETAILS: OrderDetailsSnapshot = {
  item: null
};

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

export async function fetchPanelSnapshot(): Promise<{ snapshot: PanelSnapshot; warning?: string }> {
  const baseUrl = resolveBackendBaseUrl();
  if (!baseUrl) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: "Defina PANEL_BACKEND_URL para conectar o Next.js ao snapshot do FastAPI."
    };
  }

  const authHeader = await getBackendAuthorizationHeader();
  if (!authHeader) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: "Sessão do admin ausente. Faça login no admin moderno para acessar o painel."
    };
  }

  const inboundHeaders = await headers();
  const requestId = inboundHeaders.get("x-request-id") || undefined;
  const response = await fetch(`${baseUrl}/painel/api/snapshot`, {
    cache: "no-store",
    headers: {
      Authorization: authHeader,
      ...(requestId ? { "X-Request-ID": requestId } : {})
    }
  });

  if (!response.ok) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: `Falha ao carregar snapshot do painel: HTTP ${response.status}.`
    };
  }

  return {
    snapshot: (await response.json()) as PanelSnapshot
  };
}

async function fetchBackendJson<T>(
  path: string,
  fallback: T,
): Promise<{ data: T; warning?: string }> {
  const baseUrl = resolveBackendBaseUrl();
  if (!baseUrl) {
    return {
      data: fallback,
      warning: "Defina PANEL_BACKEND_URL para conectar o Next.js ao FastAPI."
    };
  }

  const authHeader = await getBackendAuthorizationHeader();
  if (!authHeader) {
    return {
      data: fallback,
      warning: "Sessão do admin ausente. Faça login no admin moderno."
    };
  }

  const inboundHeaders = await headers();
  const requestId = inboundHeaders.get("x-request-id") || undefined;
  const response = await fetch(`${baseUrl}${path}`, {
    cache: "no-store",
    headers: {
      Authorization: authHeader,
      ...(requestId ? { "X-Request-ID": requestId } : {})
    }
  });

  if (!response.ok) {
    return {
      data: fallback,
      warning: `Falha ao carregar ${path}: HTTP ${response.status}.`
    };
  }

  return { data: (await response.json()) as T };
}

export async function fetchCustomersSnapshot(): Promise<{ data: CustomerListSnapshot; warning?: string }> {
  return fetchBackendJson("/painel/api/clientes", EMPTY_CUSTOMERS);
}

export async function fetchCustomerDetailsSnapshot(
  customerId: string,
): Promise<{ data: CustomerDetailsSnapshot; warning?: string }> {
  return fetchBackendJson(`/painel/api/clientes/${customerId}`, EMPTY_CUSTOMER_DETAILS);
}

export async function fetchOrdersSnapshot(): Promise<{ data: OrderListSnapshot; warning?: string }> {
  return fetchBackendJson("/painel/api/encomendas", EMPTY_ORDERS);
}

export async function fetchOrderDetailsSnapshot(
  orderId: string,
): Promise<{ data: OrderDetailsSnapshot; warning?: string }> {
  return fetchBackendJson(`/painel/api/encomendas/${orderId}`, EMPTY_ORDER_DETAILS);
}
