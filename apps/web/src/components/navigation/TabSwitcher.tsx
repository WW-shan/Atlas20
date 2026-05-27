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
  const focusTab = (index: number) => {
    const next = tabs[index];
    props.onChange(next.key);
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLButtonElement>(`[data-console-tab="${next.key}"]`)?.focus();
    });
  };

  return (
    <div className="topnav-tabs" role="tablist" aria-label="Console views">
      {tabs.map((tab, index) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={props.value === tab.key}
          data-console-tab={tab.key}
          className={props.value === tab.key ? "topnav-tab topnav-tab--active" : "topnav-tab"}
          onClick={() => props.onChange(tab.key)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight") {
              event.preventDefault();
              focusTab((index + 1) % tabs.length);
            } else if (event.key === "ArrowLeft") {
              event.preventDefault();
              focusTab((index - 1 + tabs.length) % tabs.length);
            } else if (event.key === "Home") {
              event.preventDefault();
              focusTab(0);
            } else if (event.key === "End") {
              event.preventDefault();
              focusTab(tabs.length - 1);
            }
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
