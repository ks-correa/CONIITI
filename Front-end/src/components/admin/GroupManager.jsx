import { useCallback, useEffect, useState } from 'react';
import { FiPlus, FiRefreshCw, FiTrash2 } from 'react-icons/fi';

import {
    addGroupMember,
    createGroup,
    deactivateGroup,
    getGroup,
    listGroupAudit,
    listGroupMembers,
    listGroups,
    removeGroupMember,
    updateGroup,
    updateGroupMember,
} from '../../services/userService';
import styles from '../../styles/components/AdminManagement.module.css';


export default function GroupManager() {
    const [groups, setGroups] = useState([]);
    const [selectedId, setSelectedId] = useState('');
    const [newGroup, setNewGroup] = useState({ name: '', description: '' });
    const [error, setError] = useState('');

    const load = useCallback(async () => {
        try {
            const data = await listGroups();
            setError('');
            setGroups(data.items);
            setSelectedId((current) => current || data.items[0]?.id || '');
        } catch (requestError) { setError(requestError.message); }
    }, []);
    useEffect(() => {
        let active = true;
        listGroups()
            .then((data) => {
                if (!active) return;
                setGroups(data.items);
                setSelectedId((current) => current || data.items[0]?.id || '');
            })
            .catch((requestError) => active && setError(requestError.message));
        return () => { active = false; };
    }, []);

    const submitNew = async (event) => {
        event.preventDefault(); setError('');
        try {
            const created = await createGroup(newGroup);
            setGroups((items) => [created, ...items]);
            setSelectedId(created.id);
            setNewGroup({ name: '', description: '' });
        } catch (requestError) { setError(requestError.message); }
    };

    return (
        <section className={styles.section}>
            <div className={styles.header}><div><h2>Grupos</h2><p>Membresías reales y administradores limitados a su propio grupo.</p></div><button className={styles.secondaryButton} onClick={load}><FiRefreshCw /> Actualizar</button></div>
            {error && <p className={styles.error}>{error}</p>}
            <form className={`${styles.card} ${styles.inlineForm}`} onSubmit={submitNew}>
                <input aria-label="Nombre del grupo" placeholder="Nombre del grupo" required minLength={2} value={newGroup.name} onChange={(event) => setNewGroup((current) => ({ ...current, name: event.target.value }))} />
                <input aria-label="Descripción del grupo" placeholder="Descripción opcional" value={newGroup.description} onChange={(event) => setNewGroup((current) => ({ ...current, description: event.target.value }))} />
                <button className={styles.primaryButton}><FiPlus /> Crear grupo</button>
            </form>
            <div className={styles.split}>
                <aside className={`${styles.card} ${styles.list}`}>
                    {groups.map((group) => <button key={group.id} className={`${styles.listButton} ${selectedId === group.id ? styles.listButtonActive : ''}`} onClick={() => setSelectedId(group.id)}><strong>{group.name}</strong><div className={styles.muted}>{group.member_count} integrantes · {group.is_active ? 'Activo' : 'Inactivo'}</div></button>)}
                    {!groups.length && <p className={styles.empty}>No hay grupos.</p>}
                </aside>
                <div>{selectedId ? <GroupWorkspace groupId={selectedId} canGovern onDeactivated={load} /> : <div className={styles.card}>Selecciona o crea un grupo.</div>}</div>
            </div>
        </section>
    );
}


export function GroupWorkspace({ groupId, canGovern = false, onDeactivated }) {
    const [group, setGroup] = useState(null);
    const [members, setMembers] = useState([]);
    const [audit, setAudit] = useState([]);
    const [form, setForm] = useState({ name: '', description: '' });
    const [invite, setInvite] = useState({ email: '', membership_role: 'member' });
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const load = useCallback(async () => {
        try {
            const [groupData, memberData, auditData] = await Promise.all([
                getGroup(groupId), listGroupMembers(groupId), listGroupAudit(groupId),
            ]);
            setError('');
            setGroup(groupData); setMembers(memberData); setAudit(auditData);
            setForm({ name: groupData.name, description: groupData.description ?? '' });
        } catch (requestError) { setError(requestError.message); }
    }, [groupId]);
    useEffect(() => {
        let active = true;
        Promise.all([getGroup(groupId), listGroupMembers(groupId), listGroupAudit(groupId)])
            .then(([groupData, memberData, auditData]) => {
                if (!active) return;
                setGroup(groupData);
                setMembers(memberData);
                setAudit(auditData);
                setForm({ name: groupData.name, description: groupData.description ?? '' });
            })
            .catch((requestError) => active && setError(requestError.message));
        return () => { active = false; };
    }, [groupId]);

    const saveGroup = async (event) => {
        event.preventDefault(); setError(''); setSuccess('');
        try { const updated = await updateGroup(groupId, form); setGroup(updated); setSuccess('Grupo actualizado.'); await load(); }
        catch (requestError) { setError(requestError.message); }
    };
    const add = async (event) => {
        event.preventDefault(); setError(''); setSuccess('');
        try { await addGroupMember(groupId, invite); setInvite({ email: '', membership_role: 'member' }); setSuccess('Integrante añadido.'); await load(); }
        catch (requestError) { setError(requestError.message); }
    };
    const changeMember = async (member, data) => {
        setError('');
        try { await updateGroupMember(groupId, member.user_id, data); await load(); }
        catch (requestError) { setError(requestError.message); }
    };
    const remove = async (member) => {
        if (!window.confirm(`¿Retirar a ${member.full_name} del grupo?`)) return;
        setError('');
        try { await removeGroupMember(groupId, member.user_id); await load(); }
        catch (requestError) { setError(requestError.message); }
    };
    const deactivate = async () => {
        if (!window.confirm('¿Desactivar este grupo? Sus integrantes perderán el acceso al espacio de administración.')) return;
        try { await deactivateGroup(groupId); if (onDeactivated) onDeactivated(); }
        catch (requestError) { setError(requestError.message); }
    };

    if (!group) return <div className={styles.card}>{error || 'Cargando grupo...'}</div>;
    return (
        <div className={styles.section}>
            {error && <p className={styles.error} role="alert">{error}</p>}
            {success && <p className={styles.success}>{success}</p>}
            <form className={styles.card} onSubmit={saveGroup}>
                <div className={styles.header}><div><h2>{group.name}</h2><p>{group.member_count} integrantes · {group.admin_count} administradores</p></div>{canGovern && <button type="button" className={styles.dangerButton} onClick={deactivate}><FiTrash2 /> Desactivar grupo</button>}</div>
                <div className={styles.grid}>
                    <div className={styles.field}><label htmlFor={`group-name-${groupId}`}>Nombre</label><input id={`group-name-${groupId}`} value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} required /></div>
                    <div className={styles.field}><label htmlFor={`group-desc-${groupId}`}>Descripción</label><textarea id={`group-desc-${groupId}`} value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} /></div>
                </div><button className={styles.primaryButton}>Guardar grupo</button>
            </form>
            <form className={`${styles.card} ${styles.inlineForm}`} onSubmit={add}>
                <input type="email" aria-label="Correo del nuevo integrante" placeholder="correo@ejemplo.com" required value={invite.email} onChange={(event) => setInvite((current) => ({ ...current, email: event.target.value }))} />
                {canGovern && <select aria-label="Rol en el grupo" value={invite.membership_role} onChange={(event) => setInvite((current) => ({ ...current, membership_role: event.target.value }))}><option value="member">Integrante</option><option value="group_admin">Administrador del grupo</option></select>}
                <button className={styles.primaryButton}><FiPlus /> Añadir por correo</button>
            </form>
            <div className={styles.card}>
                <div className={styles.tableWrapper}><table className={styles.table}><thead><tr><th>Integrante</th><th>Rol de grupo</th><th>Estado</th><th>Acciones</th></tr></thead><tbody>{members.map((member) => (
                    <tr key={member.user_id} className={member.is_active ? '' : styles.inactive}>
                        <td><strong>{member.full_name}</strong><div className={styles.muted}>{member.email}</div></td>
                        <td>{canGovern ? <select value={member.membership_role} onChange={(event) => changeMember(member, { membership_role: event.target.value })}><option value="member">Integrante</option><option value="group_admin">Administrador</option></select> : member.membership_role === 'group_admin' ? 'Administrador' : 'Integrante'}</td>
                        <td>{member.is_active ? 'Activo' : 'Inactivo'}</td>
                        <td><div className={styles.actions}>{canGovern && <button className={styles.smallButton} onClick={() => changeMember(member, { is_active: !member.is_active })}>{member.is_active ? 'Desactivar' : 'Activar'}</button>}<button className={styles.dangerButton} onClick={() => remove(member)}>Retirar</button></div></td>
                    </tr>
                ))}</tbody></table></div>
            </div>
            <details className={`${styles.card} ${styles.audit}`}><summary>Auditoría del grupo ({audit.length})</summary>{audit.map((item) => <p key={item.id}><strong>{item.action}</strong> · {new Date(item.occurred_at).toLocaleString()} · actor {item.actor_id}</p>)}</details>
        </div>
    );
}
