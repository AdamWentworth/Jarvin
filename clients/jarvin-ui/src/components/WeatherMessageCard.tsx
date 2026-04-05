import {
  BoltIcon,
  CloudArrowDownIcon,
  CloudIcon,
  SunIcon,
} from "@heroicons/react/24/solid";
import type { WeatherToolPayload } from "../lib/types";

type WeatherMessageCardProps = {
  payload: WeatherToolPayload;
};

function iconForWeather(iconName: string) {
  switch (iconName) {
    case "sun":
      return <SunIcon aria-hidden="true" />;
    case "rain":
      return <CloudArrowDownIcon aria-hidden="true" />;
    case "storm":
      return <BoltIcon aria-hidden="true" />;
    case "cloud-sun":
    case "fog":
    case "snow":
    case "cloud":
    default:
      return <CloudIcon aria-hidden="true" />;
  }
}

function formatDegrees(value: number | null | undefined) {
  return value === null || value === undefined ? "\u2014" : `${Math.round(value)}\u00B0`;
}

export function WeatherMessageCard({ payload }: WeatherMessageCardProps) {
  return (
    <section className="weather-card" aria-label={`Weather for ${payload.location_label}`}>
      <div className={`weather-card-icon weather-icon-${payload.icon_name}`}>
        {iconForWeather(payload.icon_name)}
      </div>

      <div className="weather-card-main">
        <div className="weather-card-topline">
          <span className="weather-target">{payload.target_label}</span>
          {payload.date_label ? <span className="weather-date">{payload.date_label}</span> : null}
        </div>

        <div className="weather-location">{payload.location_label}</div>
        <div className="weather-summary">{payload.summary}</div>

        <div className="weather-primary-stats">
          <div className="weather-temp-block">
            <strong>{payload.temperature}</strong>
            <span>{payload.is_current_day ? `Feels like ${payload.feels_like}` : "Forecast"}</span>
          </div>

          <div className="weather-pill-grid">
            <div className="weather-pill">
              <span>High</span>
              <strong>{formatDegrees(payload.high_value)}</strong>
            </div>
            <div className="weather-pill">
              <span>Low</span>
              <strong>{formatDegrees(payload.low_value)}</strong>
            </div>
            <div className="weather-pill">
              <span>Rain</span>
              <strong>
                {payload.precipitation_probability === null || payload.precipitation_probability === undefined
                  ? "\u2014"
                  : `${payload.precipitation_probability}%`}
              </strong>
            </div>
            <div className="weather-pill">
              <span>Wind</span>
              <strong>{payload.wind}</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
