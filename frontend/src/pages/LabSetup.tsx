import { usePageTitle } from "../hooks/usePageTitle";

export default function LabSetup() {
  usePageTitle("Settings");

  return (
    <div className="space-y-8 max-w-3xl">
      <h1 className="text-xl font-bold text-text-primary">Settings</h1>

      {/* Arena Zones */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Arena Zones
        </h2>
        <p className="text-sm text-text-secondary">
          Define the zones in your arena (e.g. feeding area, nesting area,
          perch). Zone configuration will be available in a future update.
        </p>
      </section>

      {/* Camera Config */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Camera Configuration
        </h2>
        <p className="text-sm text-text-secondary">
          Set up camera positions, calibration, and resolution settings.
          Camera configuration will be available in a future update.
        </p>
      </section>

      {/* Behavior Rules */}
      <section className="bg-surface border border-border rounded-xl p-5">
        <h2 className="text-sm font-semibold text-text-primary mb-2">
          Behavior Rules
        </h2>
        <p className="text-sm text-text-secondary">
          Configure behavior detection thresholds and custom rules.
          Behavior rule configuration will be available in a future update.
        </p>
      </section>
    </div>
  );
}
