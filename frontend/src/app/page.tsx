import { DashboardShell } from "@/components/dashboard-shell";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

export default async function HomePage() {
  await requireAdminPageSession();
  const { snapshot, warning } = await fetchPanelSnapshot();

  return <DashboardShell snapshot={snapshot} warning={warning} />;
}
