import { useCallback, useEffect, useState } from 'react';
import { FiEdit2, FiRefreshCw, FiX } from 'react-icons/fi';

import { listProfiles, updateProfileAsAdmin } from '../../services/userService';
import styles from '../../styles/components/AdminManagement.module.css';


const ROLE_LABELS = {
    external: 'Externo',
    university_community: 'Comunidad universitaria',
    staff: 'Staff',
    superuser: 'Superusuario',
};


export default function UserAdminPanel() {
    const [filters, setFilters] = useState({ search: '', role: '', isActive: '' });
    const [query, setQuery] = useState(filters);
    const [result, setResult] = useState({ items: [], total: 0, page: 1, pages: 0 });
    const [editing, setEditing] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = useCallback(async (page = 1) => {
        setLoading(true);
        setError('');
        try {
            setResult(await listProfiles({ ...query, page }));
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setLoading(false);
        }
    }, [query]);

    useEffect(() => { load(1); }, [load]);

    const applyFilters = (event) => {
        event.preventDefault();
        setQuery(filters);
    };

    const handleSaved = (updated) => {
        setResult((current) => ({
            ...current,
            items: current.items.map((item) => item.id === updated.id ? updated : item),
        }));
        setEditing(null);
    };

    return (
        <section className={styles.section}>
            <div className={styles.header}>
                <div>
                    <h2>Usuarios</h2>
                    <p>Consulta perfiles, completa datos y administra rol y estado con revocación de sesiones.</p>
                </div>
                <button className={styles.secondaryButton} type="button" onClick={() => load(result.page)}>
                    <FiRefreshCw /> Actualizar
                </button>
            </div>

            <form className={`${styles.toolbar} ${styles.card}`} onSubmit={applyFilters}>
                <input
                    aria-label="Buscar usuarios"
                    placeholder="Nombre, correo, documento o código"
                    value={filters.search}
                    onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
                />
                <select aria-label="Filtrar por rol" value={filters.role} onChange={(event) => setFilters((current) => ({ ...current, role: event.target.value }))}>
                    <option value="">Todos los roles</option>
                    {Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <select aria-label="Filtrar por estado" value={filters.isActive} onChange={(event) => setFilters((current) => ({ ...current, isActive: event.target.value }))}>
                    <option value="">Todos los estados</option>
                    <option value="true">Activos</option>
                    <option value="false">Inactivos</option>
                </select>
                <button className={styles.primaryButton} type="submit">Buscar</button>
            </form>

            {error && <p className={styles.error} role="alert">{error}</p>}
            <div className={styles.card}>
                {loading ? <p className={styles.empty}>Cargando usuarios...</p> : (
                    <div className={styles.tableWrapper}>
                        <table className={styles.table}>
                            <thead><tr><th>Usuario</th><th>Rol</th><th>Institución</th><th>Perfil</th><th>Estado</th><th>Acción</th></tr></thead>
                            <tbody>
                                {result.items.map((user) => (
                                    <tr key={user.id} className={user.is_active ? '' : styles.inactive}>
                                        <td><strong>{user.full_name}</strong><div className={styles.muted}>{user.email}</div></td>
                                        <td><span className={`${styles.badge} ${user.role === 'superuser' ? styles.badgeAdmin : ''}`}>{ROLE_LABELS[user.role] ?? user.role}</span></td>
                                        <td>{user.institution || '-'}<div className={styles.muted}>{user.career || ''}</div></td>
                                        <td>{user.profile_completed ? <span className={styles.badge}>Completo</span> : <span className={`${styles.badge} ${styles.badgeMuted}`}>Pendiente</span>}</td>
                                        <td>{user.is_active ? 'Activo' : 'Inactivo'}</td>
                                        <td><button className={styles.smallButton} type="button" onClick={() => setEditing(user)}><FiEdit2 /> Editar</button></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {!result.items.length && <p className={styles.empty}>No hay perfiles con estos filtros.</p>}
                    </div>
                )}
                <div className={styles.pagination}>
                    <span>{result.total} perfiles</span>
                    <button className={styles.secondaryButton} disabled={result.page <= 1} onClick={() => load(result.page - 1)}>Anterior</button>
                    <span>Página {result.page} de {Math.max(result.pages, 1)}</span>
                    <button className={styles.secondaryButton} disabled={result.page >= result.pages} onClick={() => load(result.page + 1)}>Siguiente</button>
                </div>
            </div>

            {editing && <EditProfileModal user={editing} onClose={() => setEditing(null)} onSaved={handleSaved} />}
        </section>
    );
}


function EditProfileModal({ user, onClose, onSaved }) {
    const [form, setForm] = useState({
        full_name: user.full_name ?? '', first_name: user.first_name ?? '', last_name: user.last_name ?? '',
        institution: user.institution ?? '', career: user.career ?? '', gender: user.gender ?? '',
        document: user.document ?? '', institutional_code: user.institutional_code ?? '',
        role: user.role, is_active: user.is_active,
    });
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const change = (event) => {
        const { name, value, type, checked } = event.target;
        setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
    };
    const submit = async (event) => {
        event.preventDefault(); setSaving(true); setError('');
        if (!form.full_name.trim()) {
            setError('El nombre completo es obligatorio.');
            setSaving(false);
            return;
        }
        try {
            const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, typeof value === 'string' ? value.trim() || null : value]));
            onSaved(await updateProfileAsAdmin(user.id, payload));
        } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
    };

    return (
        <div className={styles.overlay} role="presentation" onMouseDown={onClose}>
            <form className={styles.modal} onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
                <div className={styles.modalHeader}><h3>Editar {user.full_name}</h3><button type="button" className={styles.iconButton} onClick={onClose} aria-label="Cerrar"><FiX /></button></div>
                {error && <p className={styles.error} role="alert">{error}</p>}
                <div className={styles.grid}>
                    <Field label="Nombre completo" name="full_name" value={form.full_name} onChange={change} required />
                    <Field label="Nombre" name="first_name" value={form.first_name} onChange={change} />
                    <Field label="Apellido" name="last_name" value={form.last_name} onChange={change} />
                    <Field label="Institución" name="institution" value={form.institution} onChange={change} />
                    <Field label="Carrera" name="career" value={form.career} onChange={change} />
                    <Field label="Género" name="gender" value={form.gender} onChange={change} />
                    <Field label="Documento" name="document" value={form.document} onChange={change} />
                    <Field label="Código institucional" name="institutional_code" value={form.institutional_code} onChange={change} />
                    <div className={styles.field}><label htmlFor="admin-role">Rol</label><select id="admin-role" name="role" value={form.role} onChange={change}>{Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
                    <div className={styles.field}><label><input type="checkbox" name="is_active" checked={form.is_active} onChange={change} /> Cuenta activa</label></div>
                </div>
                <div className={styles.actions}><button className={styles.secondaryButton} type="button" onClick={onClose}>Cancelar</button><button className={styles.primaryButton} disabled={saving}>{saving ? 'Guardando...' : 'Guardar cambios'}</button></div>
            </form>
        </div>
    );
}


function Field({ label, name, value, onChange, ...inputProps }) {
    return <div className={styles.field}><label htmlFor={`admin-${name}`}>{label}</label><input id={`admin-${name}`} name={name} value={value} onChange={onChange} {...inputProps} /></div>;
}
