import { useCallback, useEffect, useState } from 'react';
import { FiClock, FiRefreshCw, FiSave } from 'react-icons/fi';

import { useAuth } from '../../context/AuthContext';
import { useEventTheme } from '../../context/EventThemeContext';
import { listSiteConfigurationRevisions } from '../../services/siteConfigService';
import BrandAssetsPanel from './BrandAssetsPanel';
import GuestCountryPanel from './GuestCountryPanel';
import ModuleVisibilityPanel from './ModuleVisibilityPanel';
import PageCopyPanel from './PageCopyPanel';
import styles from '../../styles/components/SiteSettingsPanel.module.css';


export default function SiteSettingsPanel() {
    const { user } = useAuth();
    const { siteConfig, saveConfiguration, rollbackConfiguration, refreshConfiguration } = useEventTheme();
    const [draft, setDraft] = useState(siteConfig);
    const [summary, setSummary] = useState('Actualización de contenido y visibilidad');
    const [revisions, setRevisions] = useState([]);
    const [status, setStatus] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setDraft(siteConfig);
    }, [siteConfig]);

    const loadHistory = useCallback(async () => {
        try {
            setRevisions(await listSiteConfigurationRevisions());
        } catch (error) {
            setStatus(error.message);
        }
    }, []);

    useEffect(() => {
        if (user?.role === 'superuser') loadHistory();
    }, [loadHistory, user?.role]);

    if (user?.role !== 'superuser') return null;

    const publish = async () => {
        setSaving(true);
        setStatus('');
        try {
            await saveConfiguration(draft, summary);
            setStatus('Configuración publicada correctamente.');
            await loadHistory();
        } catch (error) {
            setStatus(error.status === 412 ? 'La revisión cambió. Recarga antes de publicar.' : error.message);
        } finally {
            setSaving(false);
        }
    };

    const rollback = async (revision) => {
        if (!window.confirm(`¿Crear una nueva revisión a partir de la versión ${revision}?`)) return;
        try {
            await rollbackConfiguration(revision);
            setStatus(`Se restauró la revisión ${revision} como una nueva versión.`);
            await loadHistory();
        } catch (error) {
            setStatus(error.message);
        }
    };

    return (
        <div className={styles.panel}>
            <GuestCountryPanel />
            <PageCopyPanel event={draft.event} pages={draft.pages} onEventChange={(event) => setDraft((current) => ({ ...current, event }))} onPagesChange={(pages) => setDraft((current) => ({ ...current, pages }))} />
            <BrandAssetsPanel branding={draft.branding} onChange={(branding) => setDraft((current) => ({ ...current, branding }))} />
            <ModuleVisibilityPanel modules={draft.modules} onChange={(modules) => setDraft((current) => ({ ...current, modules }))} />
            <section className={styles.publishBar}>
                <label className={styles.field}><span>Resumen del cambio</span><input value={summary} onChange={(event) => setSummary(event.target.value)} /></label>
                <div className={styles.actions}>
                    <button type="button" className={styles.secondaryButton} onClick={() => refreshConfiguration()}><FiRefreshCw /> Recargar</button>
                    <button type="button" className={styles.primaryButton} onClick={publish} disabled={saving || summary.trim().length < 3}><FiSave /> {saving ? 'Publicando…' : 'Publicar configuración'}</button>
                </div>
                {status && <p role="status">{status}</p>}
            </section>
            <section className={styles.subpanel}>
                <div className={styles.subpanelHeader}><h3><FiClock /> Historial inmutable</h3><p>Un rollback crea otra revisión; nunca sobrescribe el historial.</p></div>
                <div className={styles.history}>
                    {revisions.map((item) => (
                        <article key={item.revision}>
                            <div><strong>v{item.revision}</strong><span>{item.change_summary}</span><small>{new Date(item.created_at).toLocaleString('es-CO')}</small></div>
                            {item.revision !== siteConfig.revision && <button type="button" onClick={() => rollback(item.revision)}>Restaurar</button>}
                        </article>
                    ))}
                </div>
            </section>
        </div>
    );
}
