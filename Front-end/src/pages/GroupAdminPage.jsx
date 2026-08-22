import { useParams } from 'react-router-dom';

import { GroupWorkspace } from '../components/admin/GroupManager';
import { useAuth } from '../context/AuthContext';
import styles from '../styles/components/AdminManagement.module.css';


export default function GroupAdminPage() {
    const { groupId } = useParams();
    const { user } = useAuth();

    return (
        <main className={styles.section} style={{ width: 'min(1100px, calc(100% - 2rem))', margin: '2rem auto' }}>
            <div className={styles.header}><div><h1>Administración de grupo</h1><p>Este acceso solo permite gestionar el grupo asignado; no habilita el panel de superusuario.</p></div></div>
            <GroupWorkspace groupId={groupId} canGovern={user?.role === 'superuser'} />
        </main>
    );
}
