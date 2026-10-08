export default function LiveMonitorPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Live Market Surveillance & Heatmap</h1>
        <div className="flex items-center space-x-2 text-sm text-emerald-400">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>Feed Ingestion Active</span>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 col-span-2">
          <h2 className="text-lg font-semibold mb-3">Ticker Heatmap (by Manipulation Risk Score)</h2>
          <div className="h-64 flex items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded">
            Awaiting WebSocket Stream Data...
          </div>
        </div>
        <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
          <h2 className="text-lg font-semibold mb-3">Real-Time Alerts</h2>
          <div className="h-64 flex items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded">
            No Active Anomaly Triggers
          </div>
        </div>
      </div>
    </div>
  );
}
