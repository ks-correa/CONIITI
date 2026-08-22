import { useEffect, useMemo, useState } from 'react';
import { FiGlobe, FiRefreshCw, FiSave } from 'react-icons/fi';

import { useAuth } from '../../context/AuthContext';
import { useEventTheme } from '../../context/EventThemeContext';
import styles from '../../styles/components/GuestCountryPanel.module.css';


function fromConfiguration(guest) {
    return {
        id: guest.id,
        country: guest.country,
        colors: guest.colors,
        siteAccentsEnabled: guest.site_accents_enabled,
        agendaParticlesEnabled: guest.agenda_particles_enabled,
    };
}

export default function GuestCountryPanel() {
    const { user } = useAuth();
    const { agendaConfig, siteConfig, presets, saveConfiguration, refreshConfiguration } = useEventTheme();
    const [draft, setDraft] = useState(() => fromConfiguration(siteConfig.guest_country));
    const [status, setStatus] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setDraft(fromConfiguration(siteConfig.guest_country));
    }, [siteConfig]);
    const selectedPresetId = useMemo(
        () => (presets.some((preset) => preset.id === draft.id) ? draft.id : 'custom'),
        [draft.id, presets],
    );

    if (user?.role !== 'superuser') return null;

    const handlePresetChange = (event) => {
        const preset = presets.find((item) => item.id === event.target.value);
        if (preset) setDraft((current) => ({ ...current, ...preset }));
    };

    const handleColorChange = (index, value) => setDraft((current) => ({
        ...current,
        id: 'custom',
        colors: current.colors.map((color, colorIndex) => (colorIndex === index ? value : color)),
    }));

    const handleSave = async (event) => {
        event.preventDefault();
        setSaving(true);
        setStatus('');
        try {
            await saveConfiguration({
                ...siteConfig,
                guest_country: {
                    id: draft.id,
                    country: draft.country,
                    colors: draft.colors,
                    site_accents_enabled: draft.siteAccentsEnabled,
                    agenda_particles_enabled: draft.agendaParticlesEnabled,
                },
            }, `Personalización del país invitado: ${draft.country}`);
            setStatus('Personalización publicada para todos los visitantes.');
        } catch (error) {
            setStatus(error.status === 412
                ? 'Otra persona publicó cambios. Actualiza la configuración antes de volver a guardar.'
                : error.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <section className={styles.panel}>
            <div className={styles.header}>
                <div>
                    <span className={styles.eyebrow}><FiGlobe /> País invitado</span>
                    <h2>Personalización visual</h2>
                    <p>Los cambios se guardan en Files y se publican globalmente, no en este navegador.</p>
                </div>
                <div className={styles.previewFlag} aria-hidden="true">
                    {draft.colors.map((color, index) => <span key={`${color}-${index}`} style={{ backgroundColor: color }} />)}
                </div>
            </div>

            <div className={styles.contentGrid}>
                <form className={styles.form} onSubmit={handleSave}>
                    <div className={styles.fieldGroup}>
                        <label htmlFor="guest-preset">Preset de país</label>
                        <select id="guest-preset" value={selectedPresetId} onChange={handlePresetChange}>
                            {presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.country}</option>)}
                            <option value="custom" disabled>Personalizado</option>
                        </select>
                    </div>
                    <div className={styles.twoColumns}>
                        <div className={styles.fieldGroup}>
                            <label htmlFor="guest-country">Nombre visible</label>
                            <input id="guest-country" value={draft.country} onChange={(event) => setDraft((current) => ({ ...current, id: 'custom', country: event.target.value }))} />
                        </div>
                        <div className={styles.fieldGroup}>
                            <label htmlFor="agenda-edition">Edición oficial (Agenda)</label>
                            <input id="agenda-edition" value={agendaConfig?.edition_label ?? 'No disponible'} readOnly />
                        </div>
                    </div>
                    <fieldset className={styles.colorSet}>
                        <legend>Colores de bandera</legend>
                        {draft.colors.map((color, index) => (
                            <label key={`${index}-${color}`} className={styles.colorControl}>
                                <span>Color {index + 1}</span>
                                <input type="color" value={color} onChange={(event) => handleColorChange(index, event.target.value)} />
                                <code>{color}</code>
                            </label>
                        ))}
                    </fieldset>
                    <div className={styles.switchGrid}>
                        <label className={styles.switchRow}>
                            <input type="checkbox" checked={draft.siteAccentsEnabled} onChange={(event) => setDraft((current) => ({ ...current, siteAccentsEnabled: event.target.checked }))} />
                            <span>Acentos del país en el sitio</span>
                        </label>
                        <label className={styles.switchRow}>
                            <input type="checkbox" checked={draft.agendaParticlesEnabled} onChange={(event) => setDraft((current) => ({ ...current, agendaParticlesEnabled: event.target.checked }))} />
                            <span>Partículas en la agenda</span>
                        </label>
                    </div>
                    <div className={styles.actions}>
                        <button type="submit" className={styles.primaryBtn} disabled={saving}><FiSave /> {saving ? 'Publicando…' : 'Publicar cambios'}</button>
                        <button type="button" className={styles.ghostBtn} onClick={() => refreshConfiguration()}><FiRefreshCw /> Recargar</button>
                    </div>
                    {status && <p className={styles.savedMessage} role="status">{status}</p>}
                </form>
                <aside className={styles.preview}>
                    <div className={styles.previewTop}><span>{agendaConfig?.edition_label ?? 'Edición por confirmar'}</span><strong>{draft.country}</strong></div>
                    <div className={styles.previewAgenda}>
                        {draft.agendaParticlesEnabled && <div className={styles.previewParticle} />}
                        <div><span className={styles.previewPill}>Agenda</span><h2>Conferencias y talleres</h2><p>Vista previa de los acentos globales.</p></div>
                    </div>
                    <div className={styles.previewCards}>{draft.colors.map((color, index) => <span key={`${color}-${index}`} style={{ backgroundColor: color }} />)}</div>
                </aside>
            </div>
        </section>
    );
}
