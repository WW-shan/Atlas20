import type { UniverseTimelinePayload } from "../../lib/api";

type Props = {
  data: UniverseTimelinePayload;
  height?: number;
};

function dayDelta(a: string, b: string): number {
  return Math.round((new Date(b).getTime() - new Date(a).getTime()) / 86_400_000);
}

export function UniverseTimeline({ data, height = 480 }: Props) {
  const { tokens, segments, rotations, range } = data;
  const totalDays = Math.max(1, dayDelta(range.start, range.end));
  const laneH = Math.max(8, Math.floor((height - 40) / Math.max(tokens.length, 1)));
  const innerH = laneH * tokens.length;
  const totalH = innerH + 40;
  const width = 1000;
  const padding = { left: 60, right: 16, top: 24 };
  const innerW = width - padding.left - padding.right;
  const xOf = (iso: string) => padding.left + (dayDelta(range.start, iso) / totalDays) * innerW;

  const rotationXs = rotations.map((r) => ({ x: xOf(r.ts), label: r.label }));

  return (
    <svg
      role="img"
      aria-label={`Universe composition timeline, ${tokens.length} tokens across ${totalDays} days`}
      viewBox={`0 0 ${width} ${totalH}`}
      style={{ width: "100%", height: totalH, display: "block" }}
    >
      {tokens.map((token, i) => {
        const y = padding.top + i * laneH;
        const isBtc = token === "BTC";
        const laneFill = i % 2 === 0 ? "rgba(148,163,184,0.04)" : "transparent";
        return (
          <g key={`lane-${token}`}>
            <rect x={padding.left} y={y} width={innerW} height={laneH - 1} fill={laneFill} />
            <text
              x={padding.left - 8}
              y={y + laneH / 2 + 3}
              textAnchor="end"
              fontFamily="var(--font-mono)"
              fontSize="10"
              fill={isBtc ? "var(--muted)" : "var(--text)"}
              opacity={isBtc ? 0.55 : 1}
              style={{ fontVariantNumeric: "tabular-nums" }}
            >
              {token}
            </text>
          </g>
        );
      })}

      {segments.map((seg, i) => {
        const laneIdx = tokens.indexOf(seg.token);
        if (laneIdx < 0) return null;
        const x1 = xOf(seg.start);
        const x2 = xOf(seg.end);
        const y = padding.top + laneIdx * laneH;
        const isBtc = seg.token === "BTC";
        return (
          <rect
            key={`seg-${i}`}
            data-token={seg.token}
            x={x1}
            y={y + 1}
            width={Math.max(2, x2 - x1)}
            height={laneH - 3}
            fill={isBtc ? "var(--muted)" : "var(--gold)"}
            opacity={isBtc ? 0.4 : 0.75}
            rx={1}
          >
            <title>{`${seg.token}: ${seg.start} → ${seg.end}`}</title>
          </rect>
        );
      })}

      {rotationXs.map((r, i) => (
        <g key={`rot-${i}`}>
          <line
            x1={r.x}
            x2={r.x}
            y1={padding.top}
            y2={padding.top + innerH}
            stroke="var(--violet)"
            strokeWidth="1"
            strokeDasharray="4 4"
            opacity="0.7"
          />
          <text
            x={r.x}
            y={padding.top - 8}
            textAnchor="middle"
            fontFamily="var(--font-mono)"
            fontSize="9"
            fill="var(--violet)"
            letterSpacing="0.08em"
            style={{ fontVariantNumeric: "tabular-nums" }}
          >
            {r.label}
          </text>
        </g>
      ))}

      <text
        x={padding.left}
        y={totalH - 8}
        fontFamily="var(--font-mono)"
        fontSize="10"
        fill="var(--muted)"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {range.start}
      </text>
      <text
        x={width - padding.right}
        y={totalH - 8}
        textAnchor="end"
        fontFamily="var(--font-mono)"
        fontSize="10"
        fill="var(--muted)"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {range.end}
      </text>
    </svg>
  );
}
