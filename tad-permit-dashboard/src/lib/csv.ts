interface CsvColumn<T> {
  key: keyof T;
  label: string;
  format?: (value: T[keyof T]) => string;
}

function escapeCsvField(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

// Generic over any row shape -- used for both the full permit table export
// and a single contractor's permit list, so the escaping/formatting logic
// only lives once.
export function toCsv<T>(rows: T[], columns: CsvColumn<T>[]): string {
  const formatCell = (row: T, col: CsvColumn<T>): string => {
    const value = row[col.key];
    if (col.format) return col.format(value);
    return value === null || value === undefined ? "" : String(value);
  };

  const header = columns.map((c) => escapeCsvField(c.label)).join(",");
  const lines = rows.map((row) => columns.map((c) => escapeCsvField(formatCell(row, c))).join(","));
  return [header, ...lines].join("\r\n");
}

// Triggers a browser file download for CSV text -- no server round trip,
// since the filtered permit list already lives in the browser.
export function downloadCsv(filename: string, csvContent: string): void {
  const blob = new Blob(["﻿" + csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
