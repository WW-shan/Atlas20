export type ConsoleTab = "overview" | "dashboard";

export function TabSwitcher(props: {
  value: ConsoleTab;
  onChange: (value: ConsoleTab) => void;
}) {
  return (
    <div className="tab-switcher" aria-label="Console views">
      {(["overview", "dashboard"] as const).map((tab) => (
        <button
          key={tab}
          type="button"
          className={props.value === tab ? "tab tab--active" : "tab"}
          onClick={() => props.onChange(tab)}
        >
          {tab === "overview" ? "Overview" : "Dashboard"}
        </button>
      ))}
    </div>
  );
}
