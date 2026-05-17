import type { SelectionHistoryRow } from "../../lib/api";

export function SelectionHistoryTable(props: { rows: SelectionHistoryRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Coin</th>
            <th>Rank</th>
            <th>Weight</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={`${row.rebalance_date}-${row.coin_id}`}>
              <td>{row.rebalance_date}</td>
              <td>{row.coin_id}</td>
              <td>{row.coin_rank}</td>
              <td>{(row.coin_weight * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
