import styles from '../../styles/components/SiteSettingsPanel.module.css';


function Field({ label, value, onChange, multiline = false, type = 'text' }) {
    return (
        <label className={styles.field}>
            <span>{label}</span>
            {multiline
                ? <textarea rows="4" value={value ?? ''} onChange={(event) => onChange(event.target.value)} />
                : <input type={type} value={value ?? ''} onChange={(event) => onChange(event.target.value)} />}
        </label>
    );
}

export default function PageCopyPanel({ event, pages, onEventChange, onPagesChange }) {
    const setPage = (page, field, value) => onPagesChange({
        ...pages,
        [page]: { ...pages[page], [field]: value },
    });
    return (
        <section className={styles.subpanel}>
            <div className={styles.subpanelHeader}><h3>Textos públicos</h3><p>Estos textos se publican para todos los visitantes. Las fechas se administran en Agenda.</p></div>
            <div className={styles.formGrid}>
                <Field label="Nombre del evento" value={event.title} onChange={(value) => onEventChange({ ...event, title: value })} />
                <Field label="Ubicación" value={event.location_label} onChange={(value) => onEventChange({ ...event, location_label: value })} />
                <Field label="Subtítulo del evento" value={event.subtitle} onChange={(value) => onEventChange({ ...event, subtitle: value })} />
                <Field label="Descripción general" value={event.description} onChange={(value) => onEventChange({ ...event, description: value })} multiline />
                <Field label="Título de inicio" value={pages.home.title} onChange={(value) => setPage('home', 'title', value)} />
                <Field label="Texto de inicio" value={pages.home.subtitle} onChange={(value) => setPage('home', 'subtitle', value)} multiline />
                <Field label="Botón principal" value={pages.home.cta_label} onChange={(value) => setPage('home', 'cta_label', value)} />
                <Field label="Título Acerca de" value={pages.about.title} onChange={(value) => setPage('about', 'title', value)} />
                <Field label="Descripción Acerca de" value={pages.about.description} onChange={(value) => setPage('about', 'description', value)} multiline />
                <Field label="Título Contacto" value={pages.contact.title} onChange={(value) => setPage('contact', 'title', value)} />
                <Field label="Correo" type="email" value={pages.contact.email} onChange={(value) => setPage('contact', 'email', value)} />
                <Field label="Teléfono" value={pages.contact.phone} onChange={(value) => setPage('contact', 'phone', value)} />
                <Field label="Dirección" value={pages.contact.address} onChange={(value) => setPage('contact', 'address', value)} />
                <Field label="Mensaje de contacto" value={pages.contact.message} onChange={(value) => setPage('contact', 'message', value)} multiline />
                <Field label="Título Conferencistas" value={pages.speakers.title} onChange={(value) => setPage('speakers', 'title', value)} />
                <Field label="Texto Conferencistas" value={pages.speakers.subtitle} onChange={(value) => setPage('speakers', 'subtitle', value)} multiline />
                <Field label="Título Agenda" value={pages.agenda.title} onChange={(value) => setPage('agenda', 'title', value)} />
                <Field label="Texto Agenda" value={pages.agenda.subtitle} onChange={(value) => setPage('agenda', 'subtitle', value)} multiline />
            </div>
            <label className={styles.switchRow}><input type="checkbox" checked={pages.speakers.show_organization} onChange={(eventValue) => setPage('speakers', 'show_organization', eventValue.target.checked)} /> Mostrar organización de conferencistas</label>
            <label className={styles.switchRow}><input type="checkbox" checked={pages.agenda.show_filters} onChange={(eventValue) => setPage('agenda', 'show_filters', eventValue.target.checked)} /> Mostrar filtros de agenda</label>
            <label className={styles.field}>
                <span>Columnas de agenda</span>
                <select value={pages.agenda.columns} onChange={(eventValue) => setPage('agenda', 'columns', Number(eventValue.target.value))}>
                    {[1, 2, 3, 4].map((columns) => <option key={columns} value={columns}>{columns}</option>)}
                </select>
            </label>
        </section>
    );
}
