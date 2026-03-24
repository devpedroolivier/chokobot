import { OperationsShell } from "@/components/operations-shell";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

export default async function OperationsPage() {
  await requireAdminPageSession();
  const { snapshot, warning } = await fetchPanelSnapshot();

  return <OperationsShell snapshot={snapshot} warning={warning} />;
}
