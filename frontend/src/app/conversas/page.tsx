import { ConversationsShell } from "@/components/conversations-shell";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

type ConversationsPageProps = {
  searchParams?: Promise<{ phone?: string }>;
};

export default async function ConversationsPage({ searchParams }: ConversationsPageProps) {
  await requireAdminPageSession();
  const { snapshot, warning } = await fetchPanelSnapshot();
  const filters = (await searchParams) || {};

  return <ConversationsShell snapshot={snapshot} warning={warning} initialSelectedPhone={filters.phone || ""} />;
}
