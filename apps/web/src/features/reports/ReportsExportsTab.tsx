import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Card } from "../../components/ui/Card";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Button } from "../../components/ui/Button";
import { FeaturedDigestHero } from "../../components/reports/FeaturedDigestHero";
import { ReportCard } from "../../components/reports/ReportCard";

import {
  downloadDigest,
  downloadReport,
  fallbackFeaturedDigest,
  fallbackReports,
  getFeaturedDigest,
  listReports,
} from "../../lib/api";
import type { ReportFormat } from "../../lib/api";
import type { ReportSortKey } from "../../components/ui/types";
import { qk } from "../../lib/qk";

const SORT_OPTIONS: { key: ReportSortKey; label: string }[] = [
  { key: "recent", label: "Most recent" },
  { key: "oldest", label: "Oldest" },
  { key: "size",   label: "Size" },
  { key: "type",   label: "Type" },
];

export function ReportsExportsTab() {
  const [sort, setSort] = useState<ReportSortKey>("recent");
  const [format, setFormat] = useState<ReportFormat>(fallbackFeaturedDigest.defaultFormat);
  const apiEnabled = import.meta.env.MODE !== "test";

  const featured = useQuery({
    queryKey: qk.reports.featured(),
    queryFn: getFeaturedDigest,
    initialData: fallbackFeaturedDigest,
    enabled: apiEnabled,
  });

  const archive = useQuery({
    queryKey: qk.reports.archive(sort),
    queryFn: () => listReports(sort),
    initialData: fallbackReports,
    enabled: apiEnabled,
  });

  const fData = featured.data ?? fallbackFeaturedDigest;
  const aData = archive.data ?? fallbackReports;

  const sorted = useMemo(() => {
    const list = [...aData];
    switch (sort) {
      case "recent": return list.sort((a, b) => b.generated_at.localeCompare(a.generated_at));
      case "oldest": return list.sort((a, b) => a.generated_at.localeCompare(b.generated_at));
      case "size":   return list.sort((a, b) => b.size_bytes - a.size_bytes);
      case "type":   return list.sort((a, b) => a.report_type.localeCompare(b.report_type));
    }
  }, [aData, sort]);

  const openDownload = (url: string) => {
    if (typeof window !== "undefined") window.open(url, "_blank", "noopener,noreferrer");
  };

  const handleDownloadAll = () => {
    // Bundle archive (all formats); single-format download lives on individual cards
    downloadDigest("bundle").then((r) => openDownload(r.url)).catch(() => {});
  };

  const handleDownloadOne = (id: string, fmt?: ReportFormat) => {
    // Honor the page-level format selection when card doesn't override
    downloadReport(id, fmt ?? format).then((r) => openDownload(r.url)).catch(() => {});
  };

  const handleNewReport = () => {
    // Modal spec deferred (SPEC §14) — stub for now
    // eslint-disable-next-line no-console
    console.log("[reports] + NEW REPORT clicked");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      <FeaturedDigestHero
        digest={fData}
        selectedFormat={format}
        onSelectFormat={setFormat}
        onDownloadAll={handleDownloadAll}
      />

      <Card ariaLabel="Reports archive">
        <SectionHeader
          rightSlot={
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <span className="muted" style={{ fontSize: 11 }}>Sort:</span>
              <div role="tablist" aria-label="Archive sort" style={{ display: "flex", gap: 2, border: "1px solid var(--border)", borderRadius: "var(--radius-input)", padding: 2 }}>
                {SORT_OPTIONS.map((opt) => {
                  const active = opt.key === sort;
                  return (
                    <button
                      key={opt.key}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      data-sort={opt.key}
                      onClick={() => setSort(opt.key)}
                      style={{
                        padding: "4px 10px",
                        fontSize: 11,
                        border: "none",
                        borderRadius: 3,
                        background: active ? "rgba(139,92,246,0.10)" : "transparent",
                        color: active ? "var(--violet)" : "var(--muted)",
                        fontWeight: active ? 700 : 400,
                        cursor: "pointer",
                        fontFamily: "var(--font-sans)",
                        letterSpacing: "0.04em",
                      }}
                    >
                      {opt.label}
                    </button>
                  );
                })}
              </div>
              <Button variant="outline-violet" size="sm" onClick={handleNewReport}>+ NEW REPORT</Button>
            </div>
          }
        >
          REPORTS ARCHIVE
        </SectionHeader>
        <div
          role="list"
          aria-label="Reports archive list"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 16,
          }}
        >
          {sorted.map((entry) => (
            <div role="listitem" key={entry.id}>
              <ReportCard entry={entry} onDownload={handleDownloadOne} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
