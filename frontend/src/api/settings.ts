import { get } from "./client";

export function getZones() {
  return get<{ zones: string[] }>("/settings/zones");
}
