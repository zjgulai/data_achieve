import type { PlatformPackage } from "@/lib/api/platform-packages";

export type PackageFilters = Readonly<{
  query: string;
  method: string;
  status: "all" | "verified" | "pending" | "disabled";
}>;

export function filterPlatformPackages(
  packages: readonly PlatformPackage[],
  filters: PackageFilters,
): readonly PlatformPackage[] {
  const query = filters.query.trim().toLocaleLowerCase("zh-CN");
  return packages.filter((platformPackage) => {
    if (filters.method && !platformPackage.methods.includes(filters.method)) {
      return false;
    }
    if (
      filters.status !== "all" &&
      !platformPackage.endpoints.some((endpoint) => endpoint.status === filters.status)
    ) {
      return false;
    }
    if (!query) return true;
    const searchable = [
      platformPackage.platform_id,
      platformPackage.display_name,
      platformPackage.description,
      ...platformPackage.provider_groups,
      ...platformPackage.methods,
      ...platformPackage.content_types,
      ...platformPackage.endpoints.flatMap((endpoint) => [
        endpoint.endpoint_type,
        endpoint.label,
        endpoint.description,
      ]),
    ]
      .join(" ")
      .toLocaleLowerCase("zh-CN");
    return searchable.includes(query);
  });
}

export function collectMethods(
  packages: readonly PlatformPackage[],
): readonly string[] {
  return [...new Set(packages.flatMap((item) => item.methods))].sort();
}
