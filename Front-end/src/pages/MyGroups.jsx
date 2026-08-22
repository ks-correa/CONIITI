import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { listMyGroups } from '../services/userService';
import styles from '../styles/pages/MyGroups.module.css';


export default function MyGroups() {
    const [groups, setGroups] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        let active = true;
        listMyGroups()
            .then((items) => active && setGroups(Array.isArray(items) ? items : []))
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, []);

    return (
        <main className={styles.page}>
            <div className={styles.header}>
                <span>Participación</span>
                <h1>Mis grupos</h1>
                <p>Consulta los grupos a los que perteneces y administra únicamente aquellos donde te asignaron ese permiso.</p>
            </div>
            {error && <p className={styles.error} role="alert">{error}</p>}
            {loading ? <p className={styles.empty}>Cargando grupos…</p> : (
                <div className={styles.grid}>
                    {groups.map((group) => (
                        <article key={group.id} className={styles.card}>
                            <div>
                                <h2>{group.name}</h2>
                                <p>{group.description || 'Sin descripción.'}</p>
                            </div>
                            <span className={styles.role}>
                                {group.current_membership_role === 'group_admin' ? 'Administrador del grupo' : 'Integrante'}
                            </span>
                            {group.current_membership_role === 'group_admin' && (
                                <Link to={`/mis-grupos/${group.id}/administrar`}>Administrar grupo</Link>
                            )}
                        </article>
                    ))}
                    {!groups.length && <p className={styles.empty}>No perteneces a ningún grupo todavía.</p>}
                </div>
            )}
        </main>
    );
}
