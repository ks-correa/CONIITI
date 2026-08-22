// ============================================================
// Contexto de Autenticación — CONIITI Front-end
// Provee el estado global de autenticación del usuario.
// Al montar la aplicación, consulta /api/auth/me para restaurar
// la sesión desde la cookie HttpOnly si ya existe.
// ============================================================

import { createContext, useState, useEffect, useCallback, useContext } from 'react';
import { getMe, logout as logoutService } from '../services/authService';

let restoreSessionPromise = null;

/**
 * @typedef {Object} AuthUser
 * @property {string}  id
 * @property {string}  full_name
 * @property {string}  email
 * @property {string}  role       - 'superuser' | 'staff' | 'university_community' | 'external'
 * @property {boolean} is_verified
 * @property {boolean} is_active
 */

/** @type {React.Context<{ user: AuthUser|null, isLoading: boolean, setUser: Function, logout: Function }>} */
// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext(null);

/**
 * AuthProvider — envuelve la aplicación y distribución el estado de sesión.
 * Restaura automáticamente la sesión al recargar la página
 * consultando el endpoint /api/auth/me con la cookie HttpOnly.
 */
export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    // Restaura la sesión al montar el componente (ej: al recargar la página)
    useEffect(() => {
        const restoreSession = async () => {
            if (!restoreSessionPromise) {
                restoreSessionPromise = getMe();
            }

            const userData = await restoreSessionPromise;
            setUser(userData);
            setIsLoading(false);
        };
        restoreSession();
    }, []);

    /**
     * Cierra la sesión del usuario.
     * Llama al endpoint del back-end para limpiar las cookies HttpOnly
     * y luego borra el estado local.
     */
    const refreshUser = useCallback(async () => {
        const userData = await getMe({ force: true });
        setUser(userData);
        return userData;
    }, []);

    const logout = useCallback(async () => {
        try {
            await logoutService();
        } finally {
            restoreSessionPromise = null;
            setUser(null);
        }
    }, []);

    return (
        <AuthContext.Provider value={{ user, isLoading, setUser, refreshUser, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);
