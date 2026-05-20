import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FilePlus2 } from "lucide-react";

import { Card } from "../../components/ui/Card";
import { SectionHeader } from "../../components/ui/SectionHeader";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorBanner } from "../../components/ui/ErrorBanner";
import { Pill } from "../../components/ui/Pill";
import { Skeleton } from "../../components/ui/Skeleton";
import { FeaturedDigestHero } from "../../components/reports/FeaturedDigestHero";
import { ReportCard } from "../../components/reports/ReportCard";
import { NewReportModal } from "./NewReportModal";

import {
  downloadDigestUrl,
  downloadReportUrl,
  fallbackFeaturedDigest,
  fallbackOptions,
  generateReport,
  getFeaturedDigest,
  getOptions,
  listReports,
} from "../../lib/api";
import type { GenerateReportRequest, ReportFormat } from "../../lib/api";
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
  const [digestDownloadPending, setDigestDownloadPending] = useState(false);
  const [reportDownloadPendingId, setReportDownloadPendingId] = useState<string | undefined>(undefined);
  const [newReportOpen, setNewReportOpen] = useState(false);
  const [reportToast, setReportToast] = useState<string | undefined>(undefined);

  const featured = useQuery({
    queryKey: qk.reports.featured(),
    queryFn: getFeaturedDigest,
  });

  const archive = useQuery({
    queryKey: qk.reports.archive(sort),
    queryFn: () => listReports(sort),
    placeholderData: (previous) => previous,
  });

  const options = useQuery({
    queryKey: qk.options(),
    queryFn: getOptions,
    initialData: fallbackOptions,
  });

  const sorted = useMemo(() => {
    const list = [...(archive.data ?? [])];
    switch (sort) {
      case "recent": return list.sort((a, b) => b.generated_at.localeCompare(a.generated_at));
      case "oldest": return list.sort((a, b) => a.generated_at.localeCompare(b.generated_at));
      case "size":   return list.sort((a, b) => b.size_bytes - a.size_bytes);
      case "type":   return list.sort((a, b) => a.report_type.localeCompare(b.report_type));
    }
  }, [archive.data, sort]);

  useEffect(() => {
    if (!reportToast) return;
    const timer = window.setTimeout(() => setReportToast(undefined), 4000);
    return () => window.clearTimeout(timer);
  }, [reportToast]);

  const handleDownloadAll = () => {
    if (digestDownloadPending) return;
    setDigestDownloadPending(true);
    try {
      window.open(downloadDigestUrl("bundle"), "_blank", "noopener,noreferrer");
    } finally {
      setDigestDownloadPending(false);
    }
  };

  const handleDownloadOne = (id: string, fmt?: ReportFormat) => {
    if (reportDownloadPendingId) return;
    setReportDownloadPendingId(id);
    try {
      window.open(downloadReportUrl(id, fmt ?? format), "_blank", "noopener,noreferrer");
    } finally {
      setReportDownloadPendingId(undefined);
    }
  };

  const handleNewReport = () => {
    setNewReportOpen(true);
  };

  const handleGenerateReport = async (payload: GenerateReportRequest) => {
    await generateReport(payload);
    setReportToast("Report queued for generation");
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24, padding: 24 }}>
      {reportToast && (
        <div
          role="status"
          aria-live="polite"
          style={{
            alignSelf: "flex-end",
            padding: "8px 12px",
            borderRadius: "var(--radius-input)",
            border: "1px solid rgba(34,197,94,0.35)",
            background: "rgba(34,197,94,0.10)",
            color: "var(--text)",
            fontSize: 12,
            fontWeight: 700,
          }}
        >
          {reportToast}
        </div>
      )}
      {featured.isLoading && <FeaturedDigestLoading />}
      {featured.isError && (
        <FeaturedDigestError onRetry={() => { void featured.refetch(); }} />
      )}
      {featured.data && !featured.isError && (
        <FeaturedDigestHero
          digest={featured.data}
          selectedFormat={format}
          onSelectFormat={setFormat}
          onDownloadAll={handleDownloadAll}
          downloadLoading={digestDownloadPending}
        />
      )}

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
              <Button variant="outline-violet" size="sm" onClick={handleNewReport}>
                <FilePlus2 size={13} aria-hidden="true" />
                + NEW REPORT
              </Button>
            </div>
          }
        >
          REPORTS ARCHIVE
        </SectionHeader>
        {archive.isError && (
          <div style={{ marginBottom: 16 }}>
            <ErrorBanner
              message="Unable to load reports archive."
              onRetry={() => { void archive.refetch(); }}
            />
          </div>
        )}
        {archive.isLoading && <ArchiveSkeleton />}
        {!archive.isLoading && !archive.isError && sorted.length === 0 && (
          <EmptyState title="No reports archived yet" />
        )}
        {!archive.isLoading && sorted.length > 0 && (
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
                <ReportCard
                  entry={entry}
                  onDownload={handleDownloadOne}
                  downloadBusy={reportDownloadPendingId === entry.id}
                  downloadsDisabled={Boolean(reportDownloadPendingId)}
                />
              </div>
            ))}
          </div>
        )}
      </Card>
      <NewReportModal
        open={newReportOpen}
        presets={options.data?.presets ?? fallbackOptions.presets}
        onClose={() => setNewReportOpen(false)}
        onGenerate={handleGenerateReport}
      />
    </div>
  );
}

function FeaturedDigestLoading() {
  return (
    <Card variant="hero" ariaLabel="Featured digest hero">
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 24, alignItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Pill tone="gold-outline" size="xs">FEATURED DIGEST</Pill>
            <span
              role="status"
              aria-label="Loading featured digest"
              style={{
                width: 14,
                height: 14,
                borderRadius: "50%",
                border: "2px solid var(--border)",
                borderTopColor: "var(--violet)",
                animation: "spin 0.8s linear infinite",
              }}
            />
          </div>
          <Skeleton variant="text" width="45%" height="28px" />
          <Skeleton variant="text" width="70%" />
        </div>
        <Button variant="gold" loading>DOWNLOAD ALL · BUNDLE</Button>
      </div>
    </Card>
  );
}

function FeaturedDigestError({ onRetry }: { onRetry: () => void }) {
  return (
    <Card variant="hero" ariaLabel="Featured digest hero">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
          <Pill tone="gold-outline" size="xs">FEATURED DIGEST</Pill>
          <Button variant="gold" disabled>DOWNLOAD ALL · BUNDLE</Button>
        </div>
        <ErrorBanner message="Unable to load featured digest." onRetry={onRetry} />
      </div>
    </Card>
  );
}

function ArchiveSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} data-testid="archive-skeleton-row">
          <Skeleton variant="card" height="76px" />
        </div>
      ))}
    </div>
  );
}
