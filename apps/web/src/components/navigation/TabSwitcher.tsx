export type ConsoleTab =
  | "overview"
  | "backtest"
  | "compare"
  | "history"
  | "universe"
  | "reports";

const tabs: { key: ConsoleTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "backtest", label: "Backtest" },
  { key: "compare", label: "Compare" },
  { key: "history", label: "History" },
  { key: "universe", label: "Universe" },
  { key: "reports", label: "Reports" },
];

export function TabSwitcher(props: {
  value: ConsoleTab;
  onChange: (value: ConsoleTab) => void;
}) {
  return (
    <nav className="topnav-tabs" role="tablist" aria-label="Console views">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={props.value === tab.key}
          className={props.value === tab.key ? "topnav-tab topnav-tab--active" : "topnav-tab"}
          onClick={() => props.onChange(tab.key)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
