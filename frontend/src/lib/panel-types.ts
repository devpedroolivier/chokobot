export type Metric = {
  label: string;
  value: string;
  hint: string;
  tone?: string;
};

export type Alert = {
  tone: "danger" | "warning" | "muted" | string;
  title: string;
  description: string;
};

export type TelemetrySnapshot = {
  handoffs_by_reason: Metric[];
  post_purchase_fallbacks: Metric[];
  operational_metrics: Metric[];
};

export type ConversationMessage = {
  role: "cliente" | "ia" | "contexto" | string;
  actor_label: string;
  content: string;
  timestamp_label: string;
};

export type ProcessCard = {
  process_id?: number;
  order_id?: number | null;
  phone: string;
  cliente_nome: string;
  process_label: string;
  stage_label: string;
  stage_class: string;
  action_label: string;
  summary: string;
  missing_items: string[];
  origin_label: string;
  origin_class: string;
  owner_label: string;
  owner_class: string;
  owner_hint: string;
  next_step_hint?: string;
  risk_flags?: string[];
  business_state_slug?: string;
  business_state_label?: string;
  business_state_class?: string;
  updated_label: string;
  stage_slug?: string;
};

export type ProcessSection = {
  title: string;
  description: string;
  count: number;
  cards: ProcessCard[];
};

export type WhatsAppCard = {
  phone: string;
  order_id?: number | null;
  cliente_nome: string;
  stage_label: string;
  stage_class: string;
  last_message: string;
  last_seen_label: string;
  agent: string;
  is_human_handoff: boolean;
  automation_mode?: "manual" | "ai" | string;
  automation_label?: string;
  automation_hint?: string;
  owner_slug?: string;
  owner_label: string;
  owner_class: string;
  context_summary?: string;
  next_step_hint?: string;
  risk_flags?: string[];
  business_state_slug?: string;
  business_state_label?: string;
  business_state_class?: string;
  messages: ConversationMessage[];
};

export type KanbanItem = {
  id: number;
  cliente_nome: string;
  produto: string;
  categoria_label: string;
  status_label: string;
  status_badge_class: string;
  tipo_label: string;
  data_label: string;
  data_iso?: string;
  horario: string;
  valor_label: string;
  schedule_bucket: string;
  status_slug?: string;
  tipo_slug?: string;
  ready_status?: string;
  search_blob?: string;
};

export type KanbanColumn = {
  key: string;
  title: string;
  description: string;
  items: KanbanItem[];
};

export type DashboardSnapshot = {
  generated_at: string;
  reference_date: string;
  metrics: Metric[];
  kanban_columns: KanbanColumn[];
  filters?: {
    statuses: Array<{ value: string; label: string }>;
    types: Array<{ value: string; label: string }>;
    categories: Array<{ value: string; label: string }>;
    schedule_buckets: Array<{ value: string; label: string }>;
  };
};

export type PanelSnapshot = {
  dashboard: DashboardSnapshot;
  process_sections: ProcessSection[];
  whatsapp_cards: WhatsAppCard[];
  sync_overview: {
    metrics: Metric[];
    alerts: Alert[];
    telemetry?: TelemetrySnapshot;
  };
};

export type CustomerListSnapshot = {
  items: Array<{
    id: number;
    nome: string;
    telefone: string;
    criado_em: string | null;
  }>;
  count: number;
};

export type CustomerDetailsSnapshot = {
  item: {
    id: number;
    nome: string;
    telefone: string;
    criado_em: string | null;
  } | null;
};

export type OrderListSnapshot = {
  items: Array<{
    id: number;
    cliente_nome: string | null;
    cliente_telefone: string | null;
    categoria: string | null;
    massa: string | null;
    recheio: string | null;
    mousse: string | null;
    adicional: string | null;
    tamanho: string | null;
    gourmet: string | null;
    entrega: string | null;
    criado_em: string | null;
    status: string;
  }>;
  count: number;
};

export type OrderDetailsSnapshot = {
  item: {
    id: number;
    cliente_nome: string | null;
    categoria: string | null;
    produto: string | null;
    tamanho: string | null;
    massa: string | null;
    recheio: string | null;
    mousse: string | null;
    adicional: string | null;
    descricao: string | null;
    fruta_ou_nozes: string | null;
    kit_festou: boolean | null;
    quantidade: number | null;
    serve_pessoas: number | null;
    data_entrega: string | null;
    horario: string | null;
    horario_retirada: string | null;
    valor_total: number | null;
    status: string | null;
    criado_em: string | null;
  } | null;
};
