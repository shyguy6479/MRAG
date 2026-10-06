import { useId } from "react";
export type BarDatum = { label: string; value: number; comparison?: number };
export function BarChart({
  title,
  description,
  data,
  unit = "%",
  max,
  legend,
}: {
  title: string;
  description: string;
  data: BarDatum[];
  unit?: string;
  max?: number;
  legend?: [string, string];
}) {
  const id = useId();
  const ceiling =
    max ?? Math.max(...data.flatMap((d) => [d.value, d.comparison || 0]), 1);
  return (
    <section className="chart-container" aria-labelledby={id}>
      <h3 id={id}>{title}</h3>
      <p>{description}</p>
      {legend && (
        <div className="chart-legend">
          <span>
            <i />
            {legend[0]}
          </span>
          <span>
            <i />
            {legend[1]}
          </span>
        </div>
      )}
      <div className="chart-bars">
        {data.map((item) => (
          <div className="chart-bar-row" key={item.label}>
            <span>{item.label}</span>
            <div>
              <div className="chart-track">
                <i
                  style={{
                    width: `${Math.max(0, (item.value / ceiling) * 100)}%`,
                  }}
                  title={`${item.value.toFixed(2)} ${unit}`}
                />
              </div>
              {item.comparison !== undefined && (
                <div className="chart-track comparison">
                  <i
                    style={{
                      width: `${Math.max(0, (item.comparison / ceiling) * 100)}%`,
                    }}
                    title={`${item.comparison.toFixed(2)} ${unit}`}
                  />
                </div>
              )}
            </div>
            <code>
              {item.value.toFixed(unit === "ms" ? 1 : 2)}
              {unit}
              {item.comparison !== undefined && (
                <small>
                  {item.comparison.toFixed(unit === "ms" ? 1 : 2)}
                  {unit}
                </small>
              )}
            </code>
          </div>
        ))}
      </div>
      <div className="chart-axis">
        <span>0 {unit}</span>
        <span>
          {ceiling.toFixed(ceiling < 10 ? 1 : 0)} {unit}
        </span>
      </div>
    </section>
  );
}
