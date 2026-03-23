import { NextResponse } from "next/server";

import { getAdminSession } from "@/lib/admin-session";
import { fetchPanelSnapshot } from "@/lib/panel-api";

export async function GET() {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ detail: "admin_session_required" }, { status: 401 });
  }
  const result = await fetchPanelSnapshot();
  const statusCode = result.warning ? 503 : 200;
  return NextResponse.json(result, { status: statusCode });
}
