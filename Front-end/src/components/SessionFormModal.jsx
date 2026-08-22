import { useEffect, useMemo, useState } from 'react';
import { FiStar, FiX } from 'react-icons/fi';

import SpeakerDocuments from './SpeakerDocuments';
import { getAgendaConfiguration, getVenues } from '../services/agendaService';
import styles from '../styles/components/SessionFormModal.module.css';
import {
    SESSION_EVENT_TYPE, SESSION_MODALITY, SESSION_STATUS, SESSION_TRACK,
} from '../types/session';


const EMPTY_FORM = {
    titulo: '', ponente: '', afiliacion: '', descripcion_ponente: '',
    foto_ponente_url: '', es_conferencista_principal: false,
    track: SESSION_TRACK.IA, event_type: SESSION_EVENT_TYPE.CONFERENCE,
    dia: '', hora_inicio: '', hora_fin: '', salon: '', venue_id: '',
    modalidad: SESSION_MODALITY.PRESENCIAL,
    status_logistico: SESSION_STATUS.NORMAL,
    link_virtual: '', descripcion: '', cupos_totales: 0,
};


function initialForm(session) {
    if (!session) return { ...EMPTY_FORM };
    return {
        ...EMPTY_FORM,
        ...session,
        venue_id: session.venue_id || session.venue?.id || '',
    };
}


function sessionPayload(form) {
    return {
        titulo: form.titulo,
        ponente: form.ponente,
        afiliacion: form.afiliacion || null,
        descripcion_ponente: form.descripcion_ponente || null,
        foto_ponente_url: form.foto_ponente_url || null,
        es_conferencista_principal: Boolean(form.es_conferencista_principal),
        track: form.track,
        event_type: form.event_type,
        dia: form.dia,
        hora_inicio: form.hora_inicio,
        hora_fin: form.hora_fin,
        salon: form.salon || null,
        venue_id: form.venue_id || null,
        modalidad: form.modalidad,
        status_logistico: form.status_logistico,
        link_virtual: form.link_virtual || null,
        descripcion: form.descripcion || null,
        cupos_totales: Number(form.cupos_totales) || 0,
    };
}


export default function SessionFormModal({ session, onSave, onClose }) {
    const [form, setForm] = useState(() => initialForm(session));
    const [venues, setVenues] = useState([]);
    const [configuration, setConfiguration] = useState(null);
    const [metadataError, setMetadataError] = useState('');
    const [saving, setSaving] = useState(false);
    const selectedVenue = useMemo(
        () => venues.find((venue) => venue.id === form.venue_id),
        [form.venue_id, venues],
    );

    useEffect(() => {
        let active = true;
        Promise.all([getVenues({ manage: true }), getAgendaConfiguration()])
            .then(([venueData, configData]) => {
                if (!active) return;
                setVenues(venueData.filter((venue) => venue.is_active || venue.id === form.venue_id));
                setConfiguration(configData);
                setForm((current) => ({
                    ...current,
                    dia: current.dia || configData.conference_days[0] || '',
                }));
            })
            .catch((error) => active && setMetadataError(error.message));
        return () => { active = false; };
    }, [form.venue_id]);

    const handleChange = (event) => {
        const { name, value, type, checked } = event.target;
        if (name === 'venue_id') {
            const venue = venues.find((item) => item.id === value);
            setForm((previous) => ({
                ...previous,
                venue_id: value,
                salon: venue?.name || previous.salon,
                cupos_totales: venue && Number(previous.cupos_totales) > venue.capacity
                    ? venue.capacity
                    : previous.cupos_totales,
            }));
            return;
        }
        setForm((previous) => ({
            ...previous,
            [name]: type === 'checkbox' ? checked : value,
        }));
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        setSaving(true);
        try {
            await onSave(sessionPayload(form));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className={styles.overlay} onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
            <div className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="session-form-title">
                <div className={styles.modalHeader}>
                    <h2 id="session-form-title">{session ? 'Editar sesión' : 'Nueva sesión'}</h2>
                    <button type="button" className={styles.closeBtn} onClick={onClose} aria-label="Cerrar"><FiX /></button>
                </div>
                <form onSubmit={handleSubmit}>
                    <div className={styles.modalBody}>
                        {metadataError && <p role="alert" className={styles.formError}>{metadataError}</p>}
                        <div className={styles.grid}>
                            <div className={`${styles.fieldGroup} ${styles.fullWidth}`}>
                                <label htmlFor="session-title">Título *</label>
                                <input id="session-title" name="titulo" value={form.titulo} onChange={handleChange} required />
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-speaker">Ponente *</label>
                                <input id="session-speaker" name="ponente" value={form.ponente} onChange={handleChange} required />
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-affiliation">Afiliación</label>
                                <input id="session-affiliation" name="afiliacion" value={form.afiliacion || ''} onChange={handleChange} />
                            </div>
                            <div className={`${styles.fieldGroup} ${styles.fullWidth}`}>
                                <label htmlFor="speaker-description">Descripción del ponente</label>
                                <textarea id="speaker-description" name="descripcion_ponente" value={form.descripcion_ponente || ''} onChange={handleChange} />
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="speaker-photo">Enlace de la foto</label>
                                <input id="speaker-photo" name="foto_ponente_url" type="url" value={form.foto_ponente_url || ''} onChange={handleChange} />
                                {form.foto_ponente_url && <img src={form.foto_ponente_url} alt="Vista previa del ponente" className={styles.photoPreview} />}
                            </div>
                            <div className={`${styles.fieldGroup} ${styles.checkboxGroup}`}>
                                <input type="checkbox" id="main-speaker" name="es_conferencista_principal" checked={Boolean(form.es_conferencista_principal)} onChange={handleChange} />
                                <label htmlFor="main-speaker" className={styles.checkboxLabel}><FiStar /> Conferencista principal</label>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-track">Área temática *</label>
                                <select id="session-track" name="track" value={form.track} onChange={handleChange} required>
                                    {Object.values(SESSION_TRACK).map((value) => <option key={value}>{value}</option>)}
                                </select>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-type">Tipo de actividad *</label>
                                <select id="session-type" name="event_type" value={form.event_type} onChange={handleChange} required>
                                    {Object.values(SESSION_EVENT_TYPE).map((value) => <option key={value}>{value}</option>)}
                                </select>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-day">Día *</label>
                                <select id="session-day" name="dia" value={form.dia} onChange={handleChange} required disabled={!configuration}>
                                    {!configuration && form.dia && <option value={form.dia}>{form.dia}</option>}
                                    {configuration?.conference_days.map((day) => <option key={day} value={day}>{day}</option>)}
                                </select>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-start">Hora de inicio *</label>
                                <input id="session-start" name="hora_inicio" type="time" value={form.hora_inicio} onChange={handleChange} required />
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-end">Hora de cierre *</label>
                                <input id="session-end" name="hora_fin" type="time" value={form.hora_fin} onChange={handleChange} required />
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-venue">Sede *</label>
                                <select id="session-venue" name="venue_id" value={form.venue_id} onChange={handleChange} required={!form.salon}>
                                    <option value="">Sala heredada / sin normalizar</option>
                                    {venues.map((venue) => <option key={venue.id} value={venue.id}>{venue.name} (cap. {venue.capacity})</option>)}
                                </select>
                                {!form.venue_id && (
                                    <input name="salon" value={form.salon || ''} onChange={handleChange} required placeholder="Nombre temporal de la sala" />
                                )}
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-capacity">Cupos totales</label>
                                <input id="session-capacity" name="cupos_totales" type="number" min="0" max={selectedVenue?.capacity ?? 10000} value={form.cupos_totales} onChange={handleChange} />
                                {selectedVenue && <small>Capacidad máxima: {selectedVenue.capacity}</small>}
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-modality">Modalidad *</label>
                                <select id="session-modality" name="modalidad" value={form.modalidad} onChange={handleChange} required>
                                    {Object.values(SESSION_MODALITY).map((value) => <option key={value}>{value}</option>)}
                                </select>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="session-status">Estado logístico</label>
                                <select id="session-status" name="status_logistico" value={form.status_logistico} onChange={handleChange}>
                                    {Object.values(SESSION_STATUS).map((value) => <option key={value}>{value}</option>)}
                                </select>
                            </div>
                            <div className={styles.fieldGroup}>
                                <label htmlFor="virtual-link">Enlace virtual</label>
                                <input id="virtual-link" name="link_virtual" type="url" value={form.link_virtual || ''} onChange={handleChange} />
                            </div>
                            <div className={`${styles.fieldGroup} ${styles.fullWidth}`}>
                                <label htmlFor="session-description">Descripción</label>
                                <textarea id="session-description" name="descripcion" value={form.descripcion || ''} onChange={handleChange} />
                            </div>
                        </div>
                        <SpeakerDocuments ponente={form.ponente} sessionId={session?.id ?? null} sessionExists={Boolean(session?.id)} canManage />
                    </div>
                    <div className={styles.modalFooter}>
                        <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancelar</button>
                        <button type="submit" className={styles.saveBtn} disabled={saving || Boolean(metadataError)}>{saving ? 'Guardando...' : 'Guardar'}</button>
                    </div>
                </form>
            </div>
        </div>
    );
}
