import { Inbox } from "@/components/inbox";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

export default async function HomePage() {
  await requireAdminPageSession();
  const { snapshot, warning } = await fetchPanelSnapshot();
  return <Inbox snapshot={snapshot} warning={warning} />;
}
