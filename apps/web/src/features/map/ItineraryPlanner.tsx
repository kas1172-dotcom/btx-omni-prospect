import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { importLibrary } from "@googlemaps/js-api-loader";
import { api } from "../../api/client";
import type { Itinerary, ItineraryStop } from "../../types/api";
import { Button, Disclosure, Drawer, Empty, LoadingStatus, Notice, SelectInput, StatusBadge, Textarea, TextInput } from "../../components/UI";
import type { MapMarker } from "./mapModel";

export interface ItineraryPlannerHandle {
  add: (marker: MapMarker) => void;
  open: () => void;
}

type Draft = Pick<Itinerary, "title" | "origin_label" | "origin_latitude" | "origin_longitude" | "stops"> & { version: number | null };
const empty: Draft = { title: "Customer visit itinerary", origin_label: "", origin_latitude: null, origin_longitude: null, stops: [], version: null };
const input = (value: string) => value.trim() || null;
const routeFailureMessage = (error: unknown) => {
  const message = error instanceof Error ? error.message : "";
  if (message.includes("PERMISSION_DENIED") || message.includes("Routes API")) return "Driving estimates are unavailable because the route service is not enabled. Your itinerary remains editable and can still be saved.";
  if (message.includes("no drive estimate")) return message;
  return "Google Maps could not provide drive estimates. Your itinerary remains editable and can still be saved.";
};

async function routeLeg(origin: google.maps.LatLngLiteral, stop: ItineraryStop) {
  const { Route } = await importLibrary("routes");
  const { routes } = await Route.computeRoutes({
    origin,
    destination: { lat: Number(stop.latitude), lng: Number(stop.longitude) },
    travelMode: "DRIVING",
    fields: ["distanceMeters", "durationMillis"],
  });
  const route = routes?.[0];
  if (route?.distanceMeters == null || route.durationMillis == null) throw new Error("The route provider returned no drive estimate for this stop.");
  return {
    ...stop,
    travel_distance_miles: Math.round((route.distanceMeters / 1609.344) * 10) / 10,
    travel_duration_minutes: Math.round(route.durationMillis / 60_000),
    route_provider: "GOOGLE_MAPS_ROUTES" as const,
    route_retrieved_at: new Date().toISOString(),
  };
}

export const ItineraryPlanner = forwardRef<ItineraryPlannerHandle>(function ItineraryPlanner(_, ref) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(empty);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [routing, setRouting] = useState(false);
  const [failure, setFailure] = useState<string>();
  const [saved, setSaved] = useState<string>();
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api.currentItinerary(controller.signal)
      .then(({ itinerary }) => {
        if (itinerary) setDraft({ title: itinerary.title, origin_label: itinerary.origin_label, origin_latitude: itinerary.origin_latitude, origin_longitude: itinerary.origin_longitude, stops: itinerary.stops, version: itinerary.version });
        setDirty(false);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) { setFailure(error instanceof Error ? error.message : "Itinerary could not be loaded."); setLoading(false); }
      });
    return () => controller.abort();
  }, []);

  useImperativeHandle(ref, () => ({
    open: () => setOpen(true),
    add: (marker) => {
      if (!marker.accountId || !marker.facilityId) return;
      setDraft((current) => current.stops.some((stop) => stop.facility_id === marker.facilityId)
        ? current
        : { ...current, stops: [...current.stops, { id: `stop-${marker.facilityId}`, account_id: marker.accountId!, facility_id: marker.facilityId!, site_name: marker.siteName ?? marker.label, organization_name: marker.organizationName ?? marker.label, address: marker.address ?? "", latitude: String(marker.latitude), longitude: String(marker.longitude), purpose: "", contact_name: "", meeting_status: "NOT_REQUESTED", visit_brief: "", travel_distance_miles: null, travel_duration_minutes: null, route_provider: null, route_retrieved_at: null }] });
      setSaved(undefined);
      setDirty(true);
      setOpen(true);
    },
  }), []);

  const editStop = (id: string, patch: Partial<ItineraryStop>) => { setDirty(true); setSaved(undefined); setDraft((current) => ({ ...current, stops: current.stops.map((stop) => stop.id === id ? { ...stop, ...patch, travel_distance_miles: patch.travel_distance_miles ?? (patch.latitude || patch.longitude ? null : stop.travel_distance_miles), travel_duration_minutes: patch.travel_duration_minutes ?? (patch.latitude || patch.longitude ? null : stop.travel_duration_minutes), route_provider: patch.latitude || patch.longitude ? null : stop.route_provider, route_retrieved_at: patch.latitude || patch.longitude ? null : stop.route_retrieved_at } : stop) })); };
  const move = (index: number, by: number) => { setDirty(true); setSaved(undefined); setDraft((current) => {
    const target = index + by;
    if (target < 0 || target >= current.stops.length) return current;
    const stops = [...current.stops];
    [stops[index], stops[target]] = [stops[target], stops[index]];
    return { ...current, stops };
  }); };
  const estimate = async () => {
    const lat = Number(draft.origin_latitude); const lng = Number(draft.origin_longitude);
    if (!draft.origin_latitude || !draft.origin_longitude || !Number.isFinite(lat) || !Number.isFinite(lng)) { setFailure("Enter valid origin coordinates before requesting drive estimates."); return; }
    setFailure(undefined); setRouting(true);
    try {
      let origin = { lat, lng };
      const stops: ItineraryStop[] = [];
      for (const stop of draft.stops) {
        const routed = await routeLeg(origin, stop);
        stops.push(routed);
        origin = { lat: Number(stop.latitude), lng: Number(stop.longitude) };
      }
      setDraft((current) => ({ ...current, stops }));
      setDirty(true); setSaved(undefined);
    } catch (error) {
      setFailure(routeFailureMessage(error));
    } finally { setRouting(false); }
  };
  const save = async () => {
    setFailure(undefined); setSaving(true);
    try {
      const itinerary = await api.saveItinerary({
        title: draft.title,
        origin_label: draft.origin_label,
        origin_latitude: input(draft.origin_latitude ?? ""),
        origin_longitude: input(draft.origin_longitude ?? ""),
        stops: draft.stops,
        expected_version: draft.version,
        idempotency_key: crypto.randomUUID(),
      });
      setDraft({ title: itinerary.title, origin_label: itinerary.origin_label, origin_latitude: itinerary.origin_latitude, origin_longitude: itinerary.origin_longitude, stops: itinerary.stops, version: itinerary.version });
      setSaved(`Saved version ${itinerary.version}`);
      setDirty(false);
    } catch (error) { setFailure(error instanceof Error ? error.message : "Itinerary could not be saved."); }
    finally { setSaving(false); }
  };

  return <Drawer open={open} onClose={() => setOpen(false)} titleId="itinerary-title" className="itinerary-drawer">
    <header><div><span className="eyebrow">Seller trip plan</span><h2 id="itinerary-title">Itinerary</h2></div><Button variant="ghost" onClick={() => setOpen(false)}>Close</Button></header>
    {loading ? <LoadingStatus>Opening your saved itinerary…</LoadingStatus> : <>
      {failure && <Notice tone="warning" title="Itinerary needs attention">{failure}</Notice>}
      {saved && <Notice title="Itinerary saved">{saved}. The plan is private to the signed-in seller.</Notice>}
      <div className="itinerary-state"><StatusBadge value={saving ? "Saving" : dirty ? "Pending changes" : draft.version ? "Saved" : "Not saved"} tone={saving || dirty ? "warning" : draft.version ? "success" : "neutral"} /><span>{draft.version ? `Version ${draft.version}` : "Private seller plan"}</span></div>
      <TextInput label="Itinerary name" value={draft.title} onChange={(event) => { setDirty(true); setSaved(undefined); setDraft({ ...draft, title: event.target.value }); }} />
      <TextInput id="itinerary-origin" label="Origin" placeholder="BTX facility or departure point" value={draft.origin_label} onChange={(event) => { setDirty(true); setSaved(undefined); setDraft({ ...draft, origin_label: event.target.value }); }} helper="Name the departure point. Driving estimates require provider-ready coordinates in Route details." />
      <Disclosure title="Route-provider details"><div className="itinerary-origin"><TextInput label="Origin latitude" inputMode="decimal" value={draft.origin_latitude ?? ""} onChange={(event) => { setDirty(true); setSaved(undefined); setDraft({ ...draft, origin_latitude: event.target.value || null }); }} /><TextInput label="Origin longitude" inputMode="decimal" value={draft.origin_longitude ?? ""} onChange={(event) => { setDirty(true); setSaved(undefined); setDraft({ ...draft, origin_longitude: event.target.value || null }); }} /></div><p>Coordinates are used only by the configured route-provider contract. Straight-line proximity is never substituted for driving distance.</p></Disclosure>
      <div className="itinerary-heading"><div><span className="eyebrow">Ordered stops</span><h3>{draft.stops.length} selected</h3></div><Button onClick={estimate} loading={routing} disabled={!draft.stops.length}>Estimate drive route</Button></div>
      {draft.stops.length ? <ol className="itinerary-stops">{draft.stops.map((stop, index) => <li key={stop.id}>
        <div className="itinerary-stop-head"><span>{index + 1}</span><div><strong>{stop.organization_name || stop.site_name}</strong><small>{stop.site_name}</small><small>{stop.address ? `${stop.address} · complete street address unavailable` : "Complete street address unavailable; verified map location retained."}</small></div><div><Button size="icon" aria-label={`Move ${stop.site_name} earlier`} disabled={index === 0} onClick={() => move(index, -1)}>↑</Button><Button size="icon" aria-label={`Move ${stop.site_name} later`} disabled={index === draft.stops.length - 1} onClick={() => move(index, 1)}>↓</Button><Button size="icon" aria-label={`Remove ${stop.site_name}`} onClick={() => { setDirty(true); setSaved(undefined); setDraft((current) => ({ ...current, stops: current.stops.filter((item) => item.id !== stop.id) })); }}>×</Button></div></div>
        {stop.route_provider ? <p className="itinerary-route"><strong>{stop.travel_distance_miles} miles · {stop.travel_duration_minutes} minutes driving</strong><span>Provider route retrieved {new Date(stop.route_retrieved_at!).toLocaleString()}</span></p> : <p className="itinerary-route"><strong>Route timing unavailable</strong><span>No route-provider result is stored. The stop remains saved; straight-line proximity is not driving distance.</span></p>}
        <TextInput label="Visit purpose" value={stop.purpose} onChange={(event) => editStop(stop.id, { purpose: event.target.value })} />
        <TextInput label="Contact or role target" value={stop.contact_name} onChange={(event) => editStop(stop.id, { contact_name: event.target.value })} />
        <SelectInput label="Meeting status" value={stop.meeting_status} onChange={(event) => editStop(stop.id, { meeting_status: event.target.value as ItineraryStop["meeting_status"] })}><option value="NOT_REQUESTED">Not requested</option><option value="PROPOSED">Proposed</option><option value="CONFIRMED">Confirmed</option><option value="CANCELED">Canceled</option></SelectInput>
        <Textarea label="Visit brief" value={stop.visit_brief} onChange={(event) => editStop(stop.id, { visit_brief: event.target.value })} />
      </li>)}</ol> : <Empty>Select a verified customer or prospect site on the map, then choose Add to itinerary.</Empty>}
      <div className="itinerary-save"><p>Meeting status is explicit; proposed or not requested never means confirmed.</p><Button variant="primary" loading={saving} disabled={!draft.title.trim() || !dirty} onClick={save}>Save itinerary</Button></div>
    </>}
  </Drawer>;
});
