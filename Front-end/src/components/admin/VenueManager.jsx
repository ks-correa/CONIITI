import { useCallback, useEffect, useMemo, useState } from 'react';
import {
    FiArchive, FiExternalLink, FiFileText, FiFilm, FiMapPin, FiPlus,
    FiRefreshCw, FiTrash2, FiX,
} from 'react-icons/fi';

import {
    createVenue, createVenueResource, deleteVenue, deleteVenueResource,
    getVenues, updateVenue,
} from '../../services/agendaService';
import AssetPicker from './AssetPicker';
import styles from '../../styles/components/VenueManager.module.css';


const EMPTY_VENUE = { name: '', description: '', capacity: 1, is_active: true };
const EMPTY_RESOURCE = {
    resource_type: 'video', title: '', description: '', alt_text: '',
    source: 'asset', asset_id: '', external_url: '', mime_type: '',
    captions_asset_id: '', captions_asset: null, captions_url: '',
    transcript_asset_id: '', transcript_asset: null, transcript_url: '',
    display_order: 0, is_active: true,
};


function SupplementalAssetField({
    kind, heading, selectedId, selectedAsset, externalUrl, onAssetSelect, onExternalUrlChange,
}) {
    const isCaptions = kind === 'captions';

    return (
        <section className={styles.supplementalField} aria-label={heading}>
            <AssetPicker
                selectedId={selectedId || null}
                contentType={isCaptions ? 'text/vtt' : 'text'}
                onSelect={onAssetSelect}
                heading={heading}
            />
            {selectedId && (
                <div className={styles.assetSelection} role="status">
                    <FiFileText aria-hidden="true" />
                    <div>
                        <strong>Seleccionado desde Files</strong>
                        <span>{selectedAsset?.original_name || selectedId}</span>
                    </div>
                    {selectedAsset?.url && (
                        <a href={selectedAsset.url} target="_blank" rel="noreferrer">
                            Vista previa <FiExternalLink aria-hidden="true" />
                        </a>
                    )}
                    <button type="button" onClick={() => onAssetSelect(null)} aria-label={`Quitar ${heading.toLowerCase()}`}>
                        <FiX aria-hidden="true" /> Quitar
                    </button>
                </div>
            )}
            <label>
                O usar URL externa
                <input
                    type="url"
                    value={externalUrl}
                    onChange={(event) => onExternalUrlChange(event.target.value)}
                    placeholder={isCaptions ? 'https://ejemplo.org/subtitulos.vtt' : 'https://ejemplo.org/transcripcion.txt'}
                />
            </label>
            <small>
                {isCaptions
                    ? 'Usa WebVTT (.vtt). Seleccionar un asset reemplaza la URL externa.'
                    : 'Usa una transcripción de texto almacenada en Files o una URL externa.'}
            </small>
        </section>
    );
}


function ResourceSupplement({ label, assetId, resolvedUrl, legacyUrl }) {
    const effectiveUrl = resolvedUrl || legacyUrl;
    if (!assetId && !effectiveUrl) return null;

    return (
        <span className={styles.resourceSupplement}>
            <FiFileText aria-hidden="true" />
            {label}: {assetId ? 'Files' : 'URL externa'}
            {effectiveUrl && (
                <a href={effectiveUrl} target="_blank" rel="noreferrer">
                    Abrir <FiExternalLink aria-hidden="true" />
                </a>
            )}
        </span>
    );
}


export default function VenueManager() {
    const [venues, setVenues] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [venueForm, setVenueForm] = useState(EMPTY_VENUE);
    const [resourceForm, setResourceForm] = useState(EMPTY_RESOURCE);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const selected = useMemo(() => venues.find((venue) => venue.id === selectedId), [venues, selectedId]);

    const refresh = useCallback(async () => {
        try {
            const data = await getVenues({ manage: true });
            setVenues(data);
            setSelectedId((current) => data.some((venue) => venue.id === current) ? current : data[0]?.id ?? null);
            setError('');
        } catch (loadError) {
            setError(loadError.message);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    const createNewVenue = async (event) => {
        event.preventDefault();
        setBusy(true);
        try {
            const created = await createVenue({ ...venueForm, capacity: Number(venueForm.capacity) });
            setVenueForm(EMPTY_VENUE);
            await refresh();
            setSelectedId(created.id);
        } catch (requestError) {
            setError(requestError.message);
        } finally { setBusy(false); }
    };

    const toggleActive = async (venue) => {
        try {
            await updateVenue(venue.id, { is_active: !venue.is_active });
            await refresh();
        } catch (requestError) { setError(requestError.message); }
    };

    const editSelected = (field, value) => {
        setVenues((current) => current.map((venue) => (
            venue.id === selectedId ? { ...venue, [field]: value } : venue
        )));
    };

    const saveVenue = async (event) => {
        event.preventDefault();
        if (!selected) return;
        setBusy(true);
        try {
            await updateVenue(selected.id, {
                name: selected.name,
                description: selected.description || null,
                capacity: Number(selected.capacity),
                is_active: selected.is_active,
            });
            await refresh();
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setBusy(false);
        }
    };

    const removeVenue = async (venue) => {
        if (!window.confirm(`¿Retirar la sede ${venue.name}?`)) return;
        try {
            await deleteVenue(venue.id);
            await refresh();
        } catch (requestError) { setError(requestError.message); }
    };

    const addResource = async (event) => {
        event.preventDefault();
        if (!selected) return;
        if (resourceForm.source === 'asset' && !resourceForm.asset_id) {
            setError('Selecciona o sube un archivo de Files para este recurso.');
            return;
        }
        setBusy(true);
        const payload = {
            resource_type: resourceForm.resource_type,
            title: resourceForm.title,
            description: resourceForm.description || null,
            alt_text: resourceForm.alt_text || null,
            asset_id: resourceForm.source === 'asset' ? resourceForm.asset_id : null,
            external_url: resourceForm.source === 'external' ? resourceForm.external_url : null,
            mime_type: resourceForm.mime_type || null,
            captions_asset_id: resourceForm.captions_asset_id || null,
            captions_url: resourceForm.captions_url || null,
            transcript_asset_id: resourceForm.transcript_asset_id || null,
            transcript_url: resourceForm.transcript_url || null,
            display_order: Number(resourceForm.display_order) || 0,
            is_active: true,
        };
        try {
            await createVenueResource(selected.id, payload);
            setResourceForm(EMPTY_RESOURCE);
            await refresh();
        } catch (requestError) { setError(requestError.message); }
        finally { setBusy(false); }
    };

    const removeResource = async (resource) => {
        if (!window.confirm(`¿Retirar el recurso ${resource.title}?`)) return;
        try {
            await deleteVenueResource(selected.id, resource.id);
            await refresh();
        } catch (requestError) { setError(requestError.message); }
    };

    return (
        <section className={styles.manager} aria-labelledby="venue-manager-title">
            <header className={styles.heading}>
                <div><FiMapPin /><div><h2 id="venue-manager-title">Sedes y recursos CES</h2><p>Una sede se reutiliza desde todas sus sesiones.</p></div></div>
                <button type="button" onClick={refresh}><FiRefreshCw /> Actualizar</button>
            </header>
            {error && <p className={styles.error} role="alert">{error}</p>}

            <div className={styles.layout}>
                <aside className={styles.sidebar}>
                    <form onSubmit={createNewVenue} className={styles.form}>
                        <h3><FiPlus /> Nueva sede</h3>
                        <label>Nombre<input value={venueForm.name} onChange={(event) => setVenueForm({ ...venueForm, name: event.target.value })} required /></label>
                        <label>Descripción<textarea value={venueForm.description} onChange={(event) => setVenueForm({ ...venueForm, description: event.target.value })} /></label>
                        <label>Capacidad<input type="number" min="1" value={venueForm.capacity} onChange={(event) => setVenueForm({ ...venueForm, capacity: event.target.value })} required /></label>
                        <button type="submit" disabled={busy}>Crear sede</button>
                    </form>
                    <div className={styles.venueList}>
                        {venues.map((venue) => (
                            <button type="button" key={venue.id} className={venue.id === selectedId ? styles.selectedVenue : ''} onClick={() => setSelectedId(venue.id)}>
                                <strong>{venue.name}</strong><span>Cap. {venue.capacity} · {venue.is_active ? 'Activa' : 'Inactiva'}</span>
                            </button>
                        ))}
                    </div>
                </aside>

                <div className={styles.content}>
                    {!selected ? <p className={styles.empty}>Crea o selecciona una sede.</p> : (
                        <>
                            <div className={styles.venueHeader}>
                                <div><h3>{selected.name}</h3><p>{selected.description || 'Sin descripción'}</p></div>
                                <div>
                                    <button type="button" onClick={() => toggleActive(selected)}><FiArchive /> {selected.is_active ? 'Desactivar' : 'Activar'}</button>
                                    <button type="button" className={styles.danger} onClick={() => removeVenue(selected)}><FiTrash2 /> Retirar</button>
                                </div>
                            </div>

                            <form onSubmit={saveVenue} className={`${styles.form} ${styles.resourceForm}`}>
                                <h3>Editar sede</h3>
                                <label>Nombre<input value={selected.name} onChange={(event) => editSelected('name', event.target.value)} required /></label>
                                <label>Descripción<textarea value={selected.description ?? ''} onChange={(event) => editSelected('description', event.target.value)} /></label>
                                <label>Capacidad<input type="number" min="1" value={selected.capacity} onChange={(event) => editSelected('capacity', event.target.value)} required /></label>
                                <button type="submit" disabled={busy}>Guardar cambios de sede</button>
                            </form>

                            <div className={styles.resources}>
                                <h3><FiFilm /> Recursos</h3>
                                {selected.resources?.length === 0 && <p>No hay recursos.</p>}
                                {selected.resources?.map((resource) => (
                                    <article key={resource.id}>
                                        <div>
                                            <strong>{resource.title}</strong>
                                            <span>{resource.resource_type} · {resource.state}</span>
                                            <ResourceSupplement
                                                label="Subtítulos"
                                                assetId={resource.captions_asset_id}
                                                resolvedUrl={resource.captions_resolved_url}
                                                legacyUrl={resource.captions_url}
                                            />
                                            <ResourceSupplement
                                                label="Transcripción"
                                                assetId={resource.transcript_asset_id}
                                                resolvedUrl={resource.transcript_resolved_url}
                                                legacyUrl={resource.transcript_url}
                                            />
                                        </div>
                                        <button type="button" onClick={() => removeResource(resource)} aria-label={`Retirar ${resource.title}`}><FiTrash2 /></button>
                                    </article>
                                ))}
                            </div>

                            <form onSubmit={addResource} className={`${styles.form} ${styles.resourceForm}`}>
                                <h3>Agregar recurso</h3>
                                <label>Tipo<select value={resourceForm.resource_type} onChange={(event) => setResourceForm({
                                    ...resourceForm,
                                    resource_type: event.target.value,
                                    ...(resourceForm.source === 'asset' ? { asset_id: '', mime_type: '' } : {}),
                                    ...(event.target.value === 'video' ? {} : {
                                        captions_asset_id: '', captions_asset: null, captions_url: '',
                                        transcript_asset_id: '', transcript_asset: null, transcript_url: '',
                                    }),
                                })}>
                                    {['video', 'image', 'poster', 'document', 'link'].map((type) => <option key={type}>{type}</option>)}
                                </select></label>
                                <label>Título<input value={resourceForm.title} onChange={(event) => setResourceForm({ ...resourceForm, title: event.target.value })} required /></label>
                                <label>Origen<select value={resourceForm.source} onChange={(event) => setResourceForm({ ...resourceForm, source: event.target.value })}><option value="asset">Asset de Files</option><option value="external">URL externa permitida</option></select></label>
                                {resourceForm.source === 'asset' ? (
                                    <AssetPicker
                                        selectedId={resourceForm.asset_id || null}
                                        contentType={resourceForm.resource_type === 'video'
                                            ? 'video'
                                            : ['image', 'poster'].includes(resourceForm.resource_type)
                                                ? 'image'
                                                : 'application'}
                                        onSelect={(asset) => setResourceForm({
                                            ...resourceForm,
                                            asset_id: asset?.id ?? '',
                                            mime_type: asset?.content_type ?? '',
                                        })}
                                        heading={`Archivo para ${resourceForm.title || 'el recurso'}`}
                                    />
                                ) : (
                                    <label>URL externa<input type="url" value={resourceForm.external_url} onChange={(event) => setResourceForm({ ...resourceForm, external_url: event.target.value })} required /></label>
                                )}
                                <label>Texto alternativo<input value={resourceForm.alt_text} onChange={(event) => setResourceForm({ ...resourceForm, alt_text: event.target.value })} required={['video', 'image', 'poster'].includes(resourceForm.resource_type)} /></label>
                                {resourceForm.resource_type === 'video' && <SupplementalAssetField
                                    kind="captions"
                                    heading="Subtítulos"
                                    selectedId={resourceForm.captions_asset_id}
                                    selectedAsset={resourceForm.captions_asset}
                                    externalUrl={resourceForm.captions_url}
                                    onAssetSelect={(asset) => setResourceForm((current) => ({
                                        ...current,
                                        captions_asset_id: asset?.id ?? '',
                                        captions_asset: asset ?? null,
                                        captions_url: '',
                                    }))}
                                    onExternalUrlChange={(value) => setResourceForm((current) => ({
                                        ...current,
                                        captions_asset_id: '',
                                        captions_asset: null,
                                        captions_url: value,
                                    }))}
                                />}
                                {resourceForm.resource_type === 'video' && <SupplementalAssetField
                                    kind="transcript"
                                    heading="Transcripción"
                                    selectedId={resourceForm.transcript_asset_id}
                                    selectedAsset={resourceForm.transcript_asset}
                                    externalUrl={resourceForm.transcript_url}
                                    onAssetSelect={(asset) => setResourceForm((current) => ({
                                        ...current,
                                        transcript_asset_id: asset?.id ?? '',
                                        transcript_asset: asset ?? null,
                                        transcript_url: '',
                                    }))}
                                    onExternalUrlChange={(value) => setResourceForm((current) => ({
                                        ...current,
                                        transcript_asset_id: '',
                                        transcript_asset: null,
                                        transcript_url: value,
                                    }))}
                                />}
                                <label>Orden<input type="number" min="0" value={resourceForm.display_order} onChange={(event) => setResourceForm({ ...resourceForm, display_order: event.target.value })} /></label>
                                <button type="submit" disabled={busy}>Guardar recurso</button>
                                <small>Los assets quedan pendientes hasta que Agenda confirme y reclame la referencia en Files.</small>
                            </form>
                        </>
                    )}
                </div>
            </div>
        </section>
    );
}
