import { useCallback, useEffect, useState } from 'react';
import { FiEdit2, FiPlus, FiTrash2, FiX } from 'react-icons/fi';

import {
    createCommitteeMember,
    deleteCommitteeMember,
    listCommitteeMembers,
    updateCommitteeMember,
} from '../../services/userService';
import styles from '../../styles/components/AdminManagement.module.css';


const EMPTY = { nombre: '', cargo: '', institucion: '', foto_url: '', bio: '', orden: 0, activo: true };


export default function CommitteeManager() {
    const [members, setMembers] = useState([]);
    const [editing, setEditing] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        setLoading(true); setError('');
        try { setMembers(await listCommitteeMembers(false)); }
        catch (requestError) { setError(requestError.message); }
        finally { setLoading(false); }
    }, []);
    useEffect(() => { load(); }, [load]);

    const remove = async (member) => {
        if (!window.confirm(`¿Eliminar a ${member.nombre} del comité?`)) return;
        try { await deleteCommitteeMember(member.id); setMembers((items) => items.filter((item) => item.id !== member.id)); }
        catch (requestError) { setError(requestError.message); }
    };

    return (
        <section className={styles.section}>
            <div className={styles.header}>
                <div><h2>Comité</h2><p>Esta es la única fuente de datos de la página pública del comité.</p></div>
                <button className={styles.primaryButton} onClick={() => setEditing(EMPTY)}><FiPlus /> Añadir integrante</button>
            </div>
            {error && <p className={styles.error} role="alert">{error}</p>}
            <div className={styles.card}>
                {loading ? <p className={styles.empty}>Cargando comité...</p> : (
                    <div className={styles.tableWrapper}>
                        <table className={styles.table}>
                            <thead><tr><th>Orden</th><th>Integrante</th><th>Cargo</th><th>Estado</th><th>Acciones</th></tr></thead>
                            <tbody>{members.map((member) => (
                                <tr key={member.id} className={member.activo ? '' : styles.inactive}>
                                    <td>{member.orden}</td><td><strong>{member.nombre}</strong><div className={styles.muted}>{member.institucion || '-'}</div></td>
                                    <td>{member.cargo}</td><td>{member.activo ? 'Visible' : 'Oculto'}</td>
                                    <td><div className={styles.actions}><button className={styles.smallButton} onClick={() => setEditing(member)}><FiEdit2 /> Editar</button><button className={styles.dangerButton} onClick={() => remove(member)}><FiTrash2 /> Eliminar</button></div></td>
                                </tr>
                            ))}</tbody>
                        </table>
                        {!members.length && <p className={styles.empty}>Todavía no hay integrantes.</p>}
                    </div>
                )}
            </div>
            {editing && <CommitteeForm member={editing.id ? editing : null} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
        </section>
    );
}


function CommitteeForm({ member, onClose, onSaved }) {
    const [form, setForm] = useState(member ? { ...EMPTY, ...member } : EMPTY);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const change = (event) => {
        const { name, value, type, checked } = event.target;
        setForm((current) => ({ ...current, [name]: type === 'checkbox' ? checked : value }));
    };
    const submit = async (event) => {
        event.preventDefault(); setSaving(true); setError('');
        const payload = { ...form, orden: Number(form.orden), institucion: form.institucion || null, foto_url: form.foto_url || null, bio: form.bio || null };
        delete payload.id; delete payload.created_at;
        try { if (member) await updateCommitteeMember(member.id, payload); else await createCommitteeMember(payload); onSaved(); }
        catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
    };
    return (
        <div className={styles.overlay} onMouseDown={onClose}>
            <form className={styles.modal} onSubmit={submit} onMouseDown={(event) => event.stopPropagation()}>
                <div className={styles.modalHeader}><h3>{member ? 'Editar integrante' : 'Nuevo integrante'}</h3><button type="button" className={styles.iconButton} onClick={onClose} aria-label="Cerrar"><FiX /></button></div>
                {error && <p className={styles.error}>{error}</p>}
                <div className={styles.grid}>
                    <Field label="Nombre" name="nombre" value={form.nombre} onChange={change} required />
                    <Field label="Cargo" name="cargo" value={form.cargo} onChange={change} required />
                    <Field label="Institución" name="institucion" value={form.institucion} onChange={change} />
                    <Field label="URL de foto" name="foto_url" value={form.foto_url} onChange={change} />
                    <Field label="Orden" name="orden" type="number" min="0" value={form.orden} onChange={change} />
                    <div className={styles.field}><label><input type="checkbox" name="activo" checked={form.activo} onChange={change} /> Visible públicamente</label></div>
                    <div className={styles.field}><label htmlFor="committee-bio">Biografía</label><textarea id="committee-bio" name="bio" value={form.bio} onChange={change} /></div>
                </div>
                <div className={styles.actions}><button type="button" className={styles.secondaryButton} onClick={onClose}>Cancelar</button><button className={styles.primaryButton} disabled={saving}>{saving ? 'Guardando...' : 'Guardar'}</button></div>
            </form>
        </div>
    );
}


function Field({ label, name, value, onChange, ...inputProps }) {
    return <div className={styles.field}><label htmlFor={`committee-${name}`}>{label}</label><input id={`committee-${name}`} name={name} value={value} onChange={onChange} {...inputProps} /></div>;
}
