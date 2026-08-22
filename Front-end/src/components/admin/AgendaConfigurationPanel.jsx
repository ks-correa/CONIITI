import { useEffect, useState } from 'react';
import { FiCalendar, FiRefreshCw, FiSave } from 'react-icons/fi';

import { getAgendaConfiguration, updateAgendaConfiguration } from '../../services/agendaService';
import { useEventTheme } from '../../context/EventThemeContext';
import styles from '../../styles/components/AdminManagement.module.css';


const EMPTY_DRAFT = {
    edition_label: '',
    timezone: 'America/Bogota',
    conference_days: '',
};


function toDraft(configuration) {
    return {
        edition_label: configuration.edition_label ?? '',
        timezone: configuration.timezone ?? 'America/Bogota',
        conference_days: (configuration.conference_days ?? []).join('\n'),
    };
}


export default function AgendaConfigurationPanel() {
    const { refreshAgendaConfiguration } = useEventTheme();
    const [configuration, setConfiguration] = useState(null);
    const [draft, setDraft] = useState(EMPTY_DRAFT);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        let active = true;
        getAgendaConfiguration()
            .then((data) => {
                if (!active) return;
                setConfiguration(data);
                setDraft(toDraft(data));
                setError('');
            })
            .catch((requestError) => {
                if (active) setError(requestError.message);
            })
            .finally(() => {
                if (active) setLoading(false);
            });
        return () => { active = false; };
    }, []);

    const refresh = async () => {
        setLoading(true);
        setSuccess('');
        try {
            const data = await getAgendaConfiguration();
            setConfiguration(data);
            setDraft(toDraft(data));
            setError('');
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    };

    const save = async (event) => {
        event.preventDefault();
        const conferenceDays = [...new Set(
            draft.conference_days
                .split(/[\n,]/)
                .map((value) => value.trim())
                .filter(Boolean),
        )].sort();
        if (conferenceDays.length === 0) {
            setError('Agrega al menos un día del congreso en formato AAAA-MM-DD.');
            return;
        }

        setSaving(true);
        setSuccess('');
        try {
            const updated = await updateAgendaConfiguration({
                edition_label: draft.edition_label.trim(),
                timezone: draft.timezone.trim(),
                conference_days: conferenceDays,
            }, configuration?.etag);
            setConfiguration(updated);
            setDraft(toDraft(updated));
            await refreshAgendaConfiguration();
            setError('');
            setSuccess('Calendario publicado. Las páginas públicas ya usan esta versión.');
        } catch (requestError) {
            setError(requestError.status === 412
                ? 'Otra persona actualizó el calendario. Recárgalo antes de volver a guardar.'
                : requestError.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <section className={styles.section} aria-labelledby="agenda-configuration-title">
            <header className={styles.header}>
                <div>
                    <h2 id="agenda-configuration-title"><FiCalendar /> Calendario oficial</h2>
                    <p>Agenda es la única fuente para la edición, los días válidos y la zona horaria.</p>
                </div>
                <button type="button" className={styles.secondaryButton} onClick={refresh} disabled={loading}>
                    <FiRefreshCw /> Recargar
                </button>
            </header>

            {error && <p className={styles.error} role="alert">{error}</p>}
            {success && <p className={styles.success} role="status">{success}</p>}

            <form className={styles.card} onSubmit={save}>
                <div className={styles.grid}>
                    <div className={styles.field}>
                        <label htmlFor="agenda-edition-label">Nombre de la edición</label>
                        <input
                            id="agenda-edition-label"
                            value={draft.edition_label}
                            onChange={(event) => setDraft({ ...draft, edition_label: event.target.value })}
                            minLength="2"
                            maxLength="255"
                            required
                            disabled={loading}
                        />
                    </div>
                    <div className={styles.field}>
                        <label htmlFor="agenda-timezone">Zona horaria IANA</label>
                        <input
                            id="agenda-timezone"
                            value={draft.timezone}
                            onChange={(event) => setDraft({ ...draft, timezone: event.target.value })}
                            placeholder="America/Bogota"
                            required
                            disabled={loading}
                        />
                    </div>
                </div>
                <div className={styles.field}>
                    <label htmlFor="agenda-days">Días del congreso</label>
                    <textarea
                        id="agenda-days"
                        value={draft.conference_days}
                        onChange={(event) => setDraft({ ...draft, conference_days: event.target.value })}
                        placeholder={'2026-10-01\n2026-10-02\n2026-10-03'}
                        required
                        disabled={loading}
                    />
                    <small className={styles.muted}>Un día por línea, en formato AAAA-MM-DD. No podrás retirar un día que ya tenga sesiones.</small>
                </div>
                <div className={styles.actions}>
                    <button type="submit" className={styles.primaryButton} disabled={loading || saving || !configuration?.etag}>
                        <FiSave /> {saving ? 'Publicando…' : 'Publicar calendario'}
                    </button>
                    {configuration && <span className={styles.muted}>Versión {configuration.version}</span>}
                </div>
            </form>
        </section>
    );
}
