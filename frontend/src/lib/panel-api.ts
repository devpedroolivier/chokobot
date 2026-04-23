import "server-only";

import { headers } from "next/headers";

import type {
  AiState,
  PanelSnapshot,
  StorePulse,
  TodaySummary,
  WhatsAppCard,
} from "@/lib/panel-types";
import { getBackendAuthorizationHeader } from "@/lib/admin-session";

const EMPTY_SNAPSHOT: PanelSnapshot = {
  conversations: [],
};

function resolveBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || null;
}

type RawSnapshot = {
  whatsapp_cards?: WhatsAppCard[];
  ai_state?: AiState;
  store_pulse?: StorePulse;
  today_summary?: TodaySummary;
  attendants?: string[];
};

export async function fetchPanelSnapshot(): Promise<{ snapshot: PanelSnapshot; warning?: string }> {
  const baseUrl = resolveBackendBaseUrl();
  if (!baseUrl) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: "Defina PANEL_BACKEND_URL para conectar o Next.js ao snapshot do FastAPI.",
    };
  }

  const authHeader = await getBackendAuthorizationHeader();
  if (!authHeader) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: "Sessão do admin ausente. Faça login para acessar o painel.",
    };
  }

  const inboundHeaders = await headers();
  const requestId = inboundHeaders.get("x-request-id") || undefined;
  const response = await fetch(`${baseUrl}/painel/api/snapshot`, {
    cache: "no-store",
    headers: {
      Authorization: authHeader,
      ...(requestId ? { "X-Request-ID": requestId } : {}),
    },
  });

  if (!response.ok) {
    return {
      snapshot: EMPTY_SNAPSHOT,
      warning: `Falha ao carregar snapshot: HTTP ${response.status}.`,
    };
  }

  const raw = (await response.json()) as RawSnapshot;
  return {
    snapshot: {
      conversations: raw.whatsapp_cards || [],
      ai_state: raw.ai_state,
      store_pulse: raw.store_pulse,
      today_summary: raw.today_summary,
      attendants: raw.attendants,
    },
  };
}
