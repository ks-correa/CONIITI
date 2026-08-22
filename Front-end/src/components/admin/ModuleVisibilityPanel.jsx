import styles from '../../styles/components/SiteSettingsPanel.module.css';


const PUBLIC_MODULES = [
    ['agenda_visible', 'Agenda'],
    ['gallery_visible', 'Galería'],
    ['speakers_visible', 'Conferencistas'],
    ['memories_visible', 'Memorias'],
    ['authors_visible', 'Autores'],
    ['committee_visible', 'Comité'],
    ['about_visible', 'Acerca de'],
    ['contact_visible', 'Contacto'],
    ['payments_visible', 'Opciones públicas de pago'],
];

export default function ModuleVisibilityPanel({ modules, onChange }) {
    return (
        <section className={styles.subpanel}>
            <div className={styles.subpanelHeader}>
                <h3>Módulos públicos</h3>
                <p>Ocultar afecta navegación y contenido público. Auth, perfiles, administración, métricas y servicios nunca se desactivan aquí.</p>
            </div>
            <div className={styles.moduleGrid}>
                {PUBLIC_MODULES.map(([key, label]) => (
                    <label key={key} className={styles.moduleCard}>
                        <input type="checkbox" checked={modules[key] !== false} onChange={(event) => onChange({ ...modules, [key]: event.target.checked })} />
                        <span><strong>{label}</strong><small>{modules[key] !== false ? 'Visible' : 'Oculto'}</small></span>
                    </label>
                ))}
            </div>
        </section>
    );
}
