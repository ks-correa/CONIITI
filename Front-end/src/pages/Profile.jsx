import { useEffect, useState } from 'react';

import { useAuth } from '../context/AuthContext';
import { getOwnProfile, updateOwnProfile } from '../services/userService';
import styles from '../styles/pages/Profile.module.css';


const EMPTY_PROFILE = {
    first_name: '',
    last_name: '',
    institution: '',
    career: '',
    gender: '',
    document: '',
    institutional_code: '',
};


export default function Profile() {
    const { refreshUser } = useAuth();
    const [profile, setProfile] = useState(null);
    const [form, setForm] = useState(EMPTY_PROFILE);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    useEffect(() => {
        let active = true;
        getOwnProfile()
            .then((data) => {
                if (!active) return;
                setProfile(data);
                setForm(Object.fromEntries(
                    Object.keys(EMPTY_PROFILE).map((key) => [key, data[key] ?? '']),
                ));
            })
            .catch((requestError) => active && setError(requestError.message))
            .finally(() => active && setLoading(false));
        return () => { active = false; };
    }, []);

    const handleChange = (event) => {
        const { name, value } = event.target;
        setForm((current) => ({ ...current, [name]: value }));
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        setSaving(true);
        setError('');
        setSuccess('');
        try {
            const payload = Object.fromEntries(
                Object.entries(form).map(([key, value]) => [key, value.trim() || null]),
            );
            const updated = await updateOwnProfile(payload);
            setProfile(updated);
            setForm(Object.fromEntries(
                Object.keys(EMPTY_PROFILE).map((key) => [key, updated[key] ?? '']),
            ));
            await refreshUser();
            setSuccess('Tu perfil se actualizo correctamente.');
        } catch (requestError) {
            setError(requestError.message);
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <main className={styles.page}><div className={styles.container}>Cargando perfil...</div></main>;

    return (
        <main className={styles.page}>
            <div className={styles.container}>
                <h1 className={styles.title}>Mi perfil</h1>
                <p className={styles.intro}>Tu cuenta de Google, Microsoft o CONIITI aporta la identidad básica. Completa aquí tus datos institucionales cuando quieras.</p>
                <form className={styles.card} onSubmit={handleSubmit}>
                    {profile && (
                        <span className={`${styles.completion} ${profile.profile_completed ? styles.complete : ''}`}>
                            {profile.profile_completed ? 'Perfil básico completo' : 'Completa nombre y apellido'}
                        </span>
                    )}
                    {error && <p className={styles.error} role="alert">{error}</p>}
                    {success && <p className={styles.success} role="status">{success}</p>}
                    <div className={styles.grid}>
                        <div className={styles.field}>
                            <label htmlFor="profile-email">Correo de la cuenta</label>
                            <input id="profile-email" value={profile?.email ?? ''} disabled />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-first-name">Nombre</label>
                            <input id="profile-first-name" name="first_name" value={form.first_name} onChange={handleChange} maxLength={120} />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-last-name">Apellido</label>
                            <input id="profile-last-name" name="last_name" value={form.last_name} onChange={handleChange} maxLength={120} />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-institution">Institución</label>
                            <input id="profile-institution" name="institution" value={form.institution} onChange={handleChange} maxLength={255} />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-career">Carrera o programa</label>
                            <input id="profile-career" name="career" value={form.career} onChange={handleChange} maxLength={255} />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-gender">Género (opcional)</label>
                            <input id="profile-gender" name="gender" value={form.gender} onChange={handleChange} maxLength={80} />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-document">Documento</label>
                            <input id="profile-document" name="document" value={form.document} onChange={handleChange} maxLength={100} autoComplete="off" />
                        </div>
                        <div className={styles.field}>
                            <label htmlFor="profile-code">Código institucional</label>
                            <input id="profile-code" name="institutional_code" value={form.institutional_code} onChange={handleChange} maxLength={100} autoComplete="off" />
                        </div>
                    </div>
                    <div className={styles.actions}>
                        <button className={styles.save} type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Guardar perfil'}</button>
                        <span>Rol de cuenta: {profile?.role}</span>
                    </div>
                </form>
            </div>
        </main>
    );
}
