import { useState, useEffect, useCallback } from 'react';
import { FiPlus, FiEdit2, FiTrash2, FiUser, FiCheckCircle, FiXCircle, FiCalendar, FiUsers, FiSliders, FiGrid, FiAward, FiBookOpen } from 'react-icons/fi';
import { useLocation, useNavigate } from 'react-router-dom';

import { listStaff, createStaff, updateStaff, deleteStaff } from '../services/userService';
import StaffFormModal from '../components/StaffFormModal';
import StaffDashboard from './StaffDashboard';
import SiteSettingsPanel from '../components/admin/SiteSettingsPanel';
import UserAdminPanel from '../components/admin/UserAdminPanel';
import CommitteeManager from '../components/admin/CommitteeManager';
import GroupManager from '../components/admin/GroupManager';
import RaffleManager from '../components/admin/RaffleManager';
import styles from '../styles/pages/SuperuserDashboard.module.css';

export default function SuperuserDashboard() {
    const location = useLocation();
    const navigate = useNavigate();
    const requestedSegment = location.pathname.split('/')[2] || 'admin';
    const requestedTab = requestedSegment === 'sorteos' ? 'raffles' : requestedSegment;
    const activeTab = ['admin', 'customization', 'users', 'groups', 'committee', 'raffles', 'staff'].includes(requestedTab)
        ? requestedTab
        : 'admin';
    const selectTab = (tab) => {
        if (tab === 'admin') navigate('/superusuario');
        else navigate(`/superusuario/${tab === 'raffles' ? 'sorteos' : tab}`);
    };

    return (
        <div>
            <div className={styles.tabs}>
                <button
                    className={`${styles.tab} ${activeTab === 'admin' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('admin')}
                >
                    <FiCalendar style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Operación general
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'customization' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('customization')}
                >
                    <FiSliders style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Personalización
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'users' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('users')}
                >
                    <FiUser style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Usuarios
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'groups' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('groups')}
                >
                    <FiGrid style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Grupos
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'committee' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('committee')}
                >
                    <FiBookOpen style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Comité
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'raffles' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('raffles')}
                >
                    <FiAward style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Sorteos
                </button>
                <button
                    className={`${styles.tab} ${activeTab === 'staff' ? styles.tabActive : ''}`}
                    onClick={() => selectTab('staff')}
                >
                    <FiUsers style={{ marginRight: '0.4rem', verticalAlign: 'middle' }} />
                    Equipo de apoyo
                </button>
            </div>

            {activeTab === 'admin' && <StaffDashboard />}
            {activeTab === 'customization' && (
                <div className={styles.panelStack}>
                    <SiteSettingsPanel />
                </div>
            )}
            {activeTab === 'users' && <UserAdminPanel />}
            {activeTab === 'groups' && <GroupManager />}
            {activeTab === 'committee' && <CommitteeManager />}
            {activeTab === 'raffles' && <RaffleManager />}
            {activeTab === 'staff' && <StaffPanel />}
        </div>
    );
}

function StaffPanel() {
    const [staffList, setStaffList] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [modalOpen, setModalOpen] = useState(false);
    const [staffToEdit, setStaffToEdit] = useState(null);
    const [error, setError] = useState('');

    const fetchStaff = useCallback(async () => {
        setIsLoading(true);
        setError('');

        try {
            const data = await listStaff();
            setStaffList(data);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchStaff();
    }, [fetchStaff]);

    const handleNew = () => {
        setStaffToEdit(null);
        setModalOpen(true);
    };

    const handleEdit = (member) => {
        setStaffToEdit(member);
        setModalOpen(true);
    };

    const handleDelete = async (member) => {
        if (!window.confirm(`¿Deseas eliminar la cuenta de ${member.full_name}? Esta acción no se puede deshacer.`)) return;

        try {
            await deleteStaff(member.id);
            setStaffList((prev) => prev.filter((item) => item.id !== member.id));
        } catch (err) {
            alert(`No se pudo eliminar la cuenta. ${err.message}`);
        }
    };

    const handleToggleActive = async (member) => {
        try {
            const updated = await updateStaff(member.id, { is_active: !member.is_active });
            setStaffList((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        } catch (err) {
            alert(`No se pudo actualizar el estado de la cuenta. ${err.message}`);
        }
    };

    const handleSave = async (data) => {
        try {
            if (staffToEdit) {
                const updated = await updateStaff(staffToEdit.id, data);
                setStaffList((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
            } else {
                const created = await createStaff(data);
                setStaffList((prev) => [created, ...prev]);
            }
            setModalOpen(false);
        } catch (err) {
            alert(`No se pudieron guardar los cambios. ${err.message}`);
        }
    };

    return (
        <div>
            <div className={styles.header}>
                <div className={styles.headerLeft}>
                    <h1>Equipo de apoyo</h1>
                    <p>Administra las cuentas encargadas de la operación del congreso.</p>
                </div>
                <button className={styles.newBtn} onClick={handleNew}>
                    <FiPlus size={16} /> Nueva cuenta
                </button>
            </div>

            {error && <p className={styles.errorBanner}>{error}</p>}

            <div className={styles.card}>
                {isLoading ? (
                    <div className={styles.loading}>Cargando cuentas del equipo...</div>
                ) : staffList.length === 0 ? (
                    <div className={styles.empty}>
                        <FiUser size={40} opacity={0.3} />
                        <p>Aún no hay cuentas del equipo registradas. Crea la primera para comenzar.</p>
                    </div>
                ) : (
                    <div className={styles.tableWrapper}>
                        <table className={styles.table}>
                            <thead>
                                <tr>
                                    <th>Nombre</th>
                                    <th>Correo</th>
                                    <th>Institución</th>
                                    <th>Estado</th>
                                    <th>Acciones</th>
                                </tr>
                            </thead>
                            <tbody>
                                {staffList.map((member) => (
                                    <tr key={member.id} className={!member.is_active ? styles.rowInactive : ''}>
                                        <td><strong>{member.full_name}</strong></td>
                                        <td>{member.email}</td>
                                        <td>{member.institution ?? '-'}</td>
                                        <td>
                                            <span className={`${styles.badge} ${member.is_active ? styles.badgeActive : styles.badgeInactive}`}>
                                                {member.is_active ? 'Activo' : 'Inactivo'}
                                            </span>
                                        </td>
                                        <td>
                                            <div className={styles.actions}>
                                                <button
                                                    className={member.is_active ? styles.deactivateBtn : styles.activateBtn}
                                                    onClick={() => handleToggleActive(member)}
                                                    title={member.is_active ? 'Desactivar' : 'Activar'}
                                                >
                                                    {member.is_active ? <FiXCircle size={13} /> : <FiCheckCircle size={13} />}
                                                    {member.is_active ? 'Desactivar' : 'Activar'}
                                                </button>
                                                <button className={styles.editBtn} onClick={() => handleEdit(member)} title="Editar">
                                                    <FiEdit2 size={13} /> Editar
                                                </button>
                                                <button className={styles.deleteBtn} onClick={() => handleDelete(member)} title="Eliminar">
                                                    <FiTrash2 size={13} /> Eliminar
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                <div className={styles.count}>
                    {staffList.length} {staffList.length === 1 ? 'cuenta del equipo' : 'cuentas del equipo'} en total
                </div>
            </div>

            {modalOpen && (
                <StaffFormModal
                    staffMember={staffToEdit}
                    onSave={handleSave}
                    onClose={() => setModalOpen(false)}
                />
            )}
        </div>
    );
}
