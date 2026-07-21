interface CheckboxGroupProps {
  label: string;
  options: readonly string[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}

export default function CheckboxGroup({
  label,
  options,
  selected,
  onChange,
}: CheckboxGroupProps) {
  function toggle(option: string) {
    const next = new Set(selected);
    if (next.has(option)) {
      next.delete(option);
    } else {
      next.add(option);
    }
    onChange(next);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
          {label}
        </span>
        <div className="flex gap-2 text-xs">
          <button
            type="button"
            onClick={() => onChange(new Set(options))}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onChange(new Set())}
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            None
          </button>
        </div>
      </div>
      <div className="max-h-40 overflow-y-auto rounded border border-gray-200 dark:border-gray-700 p-2 space-y-1">
        {options.map((option) => (
          <label
            key={option}
            className="flex items-center gap-2 text-sm cursor-pointer"
          >
            <input
              type="checkbox"
              checked={selected.has(option)}
              onChange={() => toggle(option)}
              className="rounded border-gray-300"
            />
            <span className="text-gray-800 dark:text-gray-100">{option}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
