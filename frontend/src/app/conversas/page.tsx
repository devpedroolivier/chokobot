import { ConversationsShell } from "@/components/conversations-shell";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

export default async function ConversationsPage() {
  await requireAdminPageSession();
  const { snapshot, warning } = await fetchPanelSnapshot();

  return <ConversationsShell snapshot={snapshot} warning={warning} />;
}
