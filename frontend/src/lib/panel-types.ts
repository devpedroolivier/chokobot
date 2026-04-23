export type ConversationMessage = {
  role: "cliente" | "ia" | "humano" | "contexto" | string;
  actor_label: string;
  content: string;
  timestamp_label: string;
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

export type AiState = {
  enabled: boolean;
  changed_at?: string | null;
  changed_by?: string | null;
};

export type StoreCutoff = {
  label: string;
  time_label: string;
  remaining_minutes: number;
  passed: boolean;
};

export type AiSchedulePulse = {
  enabled: boolean;
  active: boolean;
  off_label: string;
  on_label: string;
};

export type StorePulse = {
  is_open: boolean;
  closed_reason: "manual" | "day_off" | "outside_hours" | null;
  hours_label: string | null;
  cutoffs: StoreCutoff[];
  ai_schedule?: AiSchedulePulse;
};

export type TodaySummary = {
  orders_count: number;
  deliveries_count: number;
  pickups_count: number;
  revenue: number;
  revenue_label: string;
  next_time_label: string | null;
  next_tipo_label: string | null;
  next_cliente_nome: string | null;
};

export type PanelSnapshot = {
  conversations: WhatsAppCard[];
  ai_state?: AiState;
  store_pulse?: StorePulse;
  today_summary?: TodaySummary;
  attendants?: string[];
};

export type CustomerOrderHistoryItem = {
  id: number;
  categoria?: string | null;
  produto?: string | null;
  tamanho?: string | null;
  data_entrega?: string | null;
  horario?: string | null;
  valor_total?: number | null;
  criado_em?: string | null;
  status?: string | null;
  tipo?: string | null;
};

export type OrderDetails = {
  id: number;
  cliente_nome?: string | null;
  categoria?: string | null;
  produto?: string | null;
  tamanho?: string | null;
  massa?: string | null;
  recheio?: string | null;
  mousse?: string | null;
  adicional?: string | null;
  descricao?: string | null;
  fruta_ou_nozes?: string | null;
  kit_festou?: number | boolean | null;
  quantidade?: number | null;
  serve_pessoas?: number | null;
  data_entrega?: string | null;
  horario?: string | null;
  horario_retirada?: string | null;
  valor_total?: number | null;
  status?: string | null;
  criado_em?: string | null;
};
