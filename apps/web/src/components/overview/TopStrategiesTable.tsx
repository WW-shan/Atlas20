import type { StrategySummary } from "../../lib/api";
import { formatMultiple, formatPercent, formatNumber } from "../../lib/format";

export function TopStrategiesTable(props: { rows: StrategySummary[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Multiple</th>
            <th>CAGR</th>
            <th>Sharpe</th>
            <th>Max DD</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.strategy}>
              <td>{row.strategy}</td>
              <td>{formatMultiple(row.multiple)}</td>
              <td>{formatPercent(row.cagr)}</td>
              <td>{formatNumber(row.sharpe)}</td>
              <td>{formatPercent(row.max_drawdown)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
